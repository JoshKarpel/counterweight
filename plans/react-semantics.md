# Plan: React Semantics

This plan covers the places where counterweight's reconciler, hooks, and event dispatch
diverge from React in ways that make component behavior surprising:
state and effects outliving their component, effect cleanup ordering, keyed children,
setter identity, hook-count checks, key and mouse event routing, and context.
It also adds `use_reducer`, a way to send controls from outside an event handler,
and a way to start a tracked task from a handler.
Those last two are what an Elm-style app structure (one model, a pure `update`,
commands as data) needs from the runtime, so the plan ends that thread with a cookbook
recipe for the structure rather than a library API.
It doesn't cover skipping unchanged components; that is `plans/component-memoization.md`.

## What already matches React

These are deliberate and stay as they are:

- Hooks are an ordered list of slots per component instance (`hooks/impls.py`), with a type
  check per slot that plays the role of React's "hook order changed" error.
- `use_state` has lazy initializers, the updater form, and skips the update on an equal value.
- The app loop drains every queued event before rendering once, which is React 18's automatic
  batching.
- Component identity is `(func, key)` at a position, so a component defined inside another
  remounts every render, as in React.
- Effects run after paint, like `useEffect`; `use_rects` plus the warm-up render covers what
  `useLayoutEffect` is usually for.

Two choices are better than a direct port and should be kept through every step below:
effects are coroutines whose cancellation is their cleanup, under a `TaskGroup`;
and event handlers return controls rather than performing them.

## Problems

- **A component replaced by a plain element keeps its hooks.** The `element, ShadowNode(...)`
  arm of `update_shadow` (`shadow.py:106`) reuses `previous_hooks` even when the previous node
  was a component, and reconciles the new element's children against the old component's
  children. The old component's effects keep running, and nested component state survives
  what should be an unmount. A probe that renders `Div(child("A"))` and then `Div(Div())`:

  ```text
  after replacing component with Div: ['start A'] | active effects: 1
  ```

  `start A` is never followed by `stop A`. A `use_mouse` listener stays registered the same
  way, and a `deps=None` effect keeps rerunning with a stale closure every render.
- **A rerun effect starts before the previous run is cancelled.** `handle_effects`
  (`app.py:460`) creates the new tasks, then awaits cancellation of the stale ones, so the new
  tasks are scheduled first. Reordering two keyed children logs:

  ```text
  ['start x', 'start y', 'start y', 'start x', 'stop y', 'stop x']
  ```

  React runs every cleanup in a commit before any setup, which matters for anything exclusive
  (a subscription, a file lock, a terminal mode).
- **Keys don't move state.** Children are paired by position with `zip_longest`
  (`shadow.py:58`, `shadow.py:111`), and a key is only compared with whatever sat at the same
  index last render. The reorder above remounts both children instead of moving them.
- **Setters are a new closure every render** (`impls.py:55`). React's setter is stable, so
  it's safe to omit from deps; here a setter in `deps` reruns the effect every render.
- **A setter called after unmount** mutates an orphaned slot and enqueues `StateSet`, causing
  a render that changes nothing.
- **Hook count changes go undetected.** A render that calls fewer hooks than the last one
  passes silently, and one that calls more appends new slots (`impls.py:51`). Only a type
  mismatch at a slot raises `InconsistentHookExecution`. A skipped trailing `use_effect`
  keeps running, because `handle_effects` walks every slot in `hooks.data`.
- **Every key press reaches every `on_key` handler** (`app.py:401`), and every mouse event
  reaches every element under the pointer (`app.py:407`). There is no focus, no bubbling, and
  no way to stop propagation, so two text inputs on screen both receive typing.
- **No context.** Values needed deep in the tree have to be passed through every component in
  between.
- **No reducer-shaped state.** State that changes in response to messages has to be written
  as a hand-rolled `set_state` updater at every call site.
- **Only an event handler can issue a control.** `handle_control` is reached from handler
  return values and the autopilot (`app.py:403`, `app.py:411`, `app.py:371`), so an effect
  can't `Quit()` when a timer expires or `Bell()` when a background job fails.
- **A handler can't start tracked work.** A handler that calls `asyncio.create_task` gets a
  task outside the app's `TaskGroup`: its exception is only logged when the task is collected,
  and quitting doesn't cancel it. Starting I/O from a key press means routing it through
  state and an effect.

The last two are what blocks an Elm-style structure.
A prototype `elm_app(init, update, view)` built as a single root component over
`use_state` runs a counter headless (keys `a`, `b`, `q`) and renders:

```text
models rendered: [0, 0, 1, 2]
```

The first two are the warm-up and the first visible frame, then one render per message,
and `q` quits through a `Quit()` returned from `update`.
The model-and-view half works on today's hooks.
What the prototype can't express is a command whose result arrives later (a fetch, a timer),
or a control produced by a message that no handler is waiting to return.

## Steps

Each step leaves the test suite passing and is a separate PR.
Reconciler tests go in a new `tests/test_shadow.py` that drives `update_shadow` and
`handle_effects` directly, recording effect start and stop into a list, rather than through
the app loop.

### 1. Start fresh hooks when a component becomes an element

**Status:** Done

Restrict the `element, ShadowNode(...)` arm to previous nodes with `component is None`,
and widen the `element, None` arm to `element, None | ShadowNode()`.
`None` in a `case` is a literal pattern, so without the widening a previous component node
would skip both element arms and reach `case _: raise Exception("Unreachable!")`.
The widened arm names both shapes rather than using `_`, so the unreachable case still
catches an unexpected `previous`.
The widened arm builds fresh `Hooks` and fresh children, so `handle_effects` sees the old
effects disappear and cancels them.

Tests: component replaced by a `Div` stops its effect; a nested component under the replaced
component starts with its initial state; a `use_mouse` listener is removed from
`use_mouse_listeners` after the replacement.

### 2. Cancel stale effects before starting new ones

**Status:** Done

Split `handle_effects` into two passes over the tree.
The first decides, per effect, whether it keeps its task or reruns, without creating
anything.
Then cancel every active task that isn't kept (reruns and unmounts alike) concurrently,
wait for all of them to finish, and only then create tasks for the reruns.

Tests: a rerun effect logs `stop` before the next `start`; an unmounted effect is stopped
before a sibling's rerun starts.

### 3. Match keyed children by key

**Status:** Done

Follow React's child reconciliation: put the previous children in a map under their key, or
under their index in the child list when they have none, and look each new child up by its
key, or by its own index when it has none.
An unkeyed child therefore matches exactly what it matches today, the previous child at the
same index, provided that child was also unkeyed.
Keyed and unkeyed children go in separate maps, since a key can be an `int` and would
otherwise collide with an index.
Only `Component` carries a key, so elements always match by index.
A key match with a different `func` still remounts, through the existing guard on the
reuse arm.

Duplicate keys among siblings raise rather than silently picking one.
React only warns here; raising is a deliberate divergence, in line with failing loudly on a
broken contract.

Tests: reordering keyed children keeps each child's state and doesn't restart its effects;
removing a keyed child from the middle keeps the state of the ones after it;
inserting at the front mounts only the new child; an unkeyed child after a removed keyed
sibling remounts, as in React; duplicate sibling keys raise.

### 4. Make setters stable

**Status:** Done

Create the setter once, when the `UseState` slot is created, and store it on the slot.
It already closes over the slot rather than the value, so a stable setter reads and writes
the same state as today's per-render one.

Tests: the setter returned on the second render is the same object as on the first;
an effect with the setter in its `deps` runs once across several renders.

### 5. Make a setter called after unmount a no-op

**Status:** Done

Give `Hooks` a `MountStatus` cell holding an `is_mounted` flag, and share the same cell with
each `UseState` slot it creates, so the setter can check it without a reference back to the
`Hooks` that holds the slot.
After `update_shadow`, set it false on every `Hooks` reachable from the previous tree but not
from the new one.
`Hooks` is a mutable dataclass with generated `__eq__`, so it is unhashable; compare the two
trees by `id()`.
The app loop currently overwrites `shadow` with the new tree, so it has to hold the previous
one until the comparison is done.
`set_state` returns without enqueuing `StateSet` when its cell says unmounted.

Do this after step 4, so the stable setter is the one that checks the flag.

Tests: calling a captured setter after its component unmounts enqueues nothing.

### 6. Raise when the hook count changes between renders

**Status:** Done

Record `len(hooks.data)` before re-running a component, and raise
`InconsistentHookExecution` if the hook index afterwards differs from it.
A first render has nothing to compare against and is exempt.
Reset the hook context vars in a `finally` around the component call, so a component that
raises doesn't leave its `Hooks` installed for whatever runs next in that context.

Tests: a component that conditionally skips its last hook raises; one that conditionally
adds a hook raises; one that calls the same hooks every render doesn't;
the hook context is restored after a component raises, on mount and on rerender.

### 7. Add `use_reducer`

**Status:** Not started

`use_reducer(reducer, initial_value)` returns the current state and a `dispatch` function,
where `reducer(state, action)` returns the next state.
`dispatch` applies the reducer to the _latest_ state, not the state captured at render time,
so several dispatches in one batch compose.
Like React's, `dispatch` returns nothing; reducers stay pure and don't produce controls.

`dispatch` is stable across renders, but it applies the reducer from the _latest_ render,
not the first: a reducer defined inside the component that reads a prop has to see the
current prop.
So the slot holds both the state and the most recent reducer, and each render replaces the
reducer.
That is a dedicated `UseReducer` slot type rather than `UseState`, which holds only a value.
It shares the component's `MountStatus` like `UseState` does, so `dispatch` after unmount is a
no-op too.

Add `docs/hooks/use_reducer.md` to the hooks section of `mkdocs.yml`, and a changelog entry.

Tests: two dispatches from one handler both apply; `dispatch` is the same object across
renders; a reducer that reads a prop applies the prop from the latest render;
a reducer that returns an equal state doesn't trigger a render; the initial value can be
lazy, like `use_state`'s.

### 8. Send controls through the event queue

**Status:** Not started

Add a `ControlSent(control)` event that the app loop passes to `handle_control`, and a
`use_send_control()` hook that returns a stable function enqueuing one.
The drain loop at `app.py:426` already pulls events enqueued while it handles a batch,
so a control sent from a handler or an effect takes effect in the same render cycle as the
event that caused it.
The autopilot's `handle_control` plus `Dummy()` can then become a single `ControlSent`.

The hook returns the function rather than the module exposing it, so a component that sends
controls says so in its own body, the same way `use_state` surfaces the setter.

Add the hook to `docs/hooks/` and the controls page, and a changelog entry.

Tests: an effect that sends `Quit()` quits the app; a `Screenshot` sent from an effect calls
its handler; the function is the same object across renders.

### 9. Start tracked tasks from handlers

**Status:** Not started

Add a `Spawn(run)` control, where `run` is a zero-argument async function returning
`AnyControl | None`.
The app loop starts it in the `TaskGroup`, so its exception fails the group the way an
effect's does, and quitting cancels it.
The control it returns goes through the `ControlSent` event from step 8, since no handler is
waiting for it by the time it finishes.
`handle_control` is defined outside the `async with TaskGroup()` block, so it needs the group
passed in or the definition moved inside.

A spawned task isn't tied to a component: it outlives an unmount, like a promise started in a
React event handler. An effect is the tool for work that should stop when its component
goes away; the docs page for `Spawn` says so.

Add it to the controls page, and a changelog entry.

Tests: a spawned task runs and its state change renders; a returned `Quit()` quits the app;
an exception in a spawned task stops the app; quitting cancels a spawned task that is still
running.

### 10. Add an Elm architecture recipe

**Status:** Not started

A cookbook page, `docs/cookbook/elm-architecture.md`, and `examples/elm.py`, rather than an
`elm_app` library function.
With steps 4, 8, and 9 in place, the adapter is about 25 lines on public APIs, and its open
choices (the command type, batching, how subscriptions look) are opinions a library API would
freeze before a second app has tried them.
Promote it to the library once a second app copies the recipe.
The cost is that each Elm-style app carries its own copy, tested only by its own tests.

The recipe's shape:

- `update(msg, model)` returns the next model and a command. `view(model, dispatch)` returns
  an element tree whose handlers call `dispatch(msg)`.
- A command is data, so `update` stays a pure function that tests can compare against:
  `assert update(Load(), model) == (loading, Perform(fetch, (url,), Loaded))`.
  It is one of a control, a `Perform(run, args, to_msg)` (a frozen dataclass naming an async
  function, its arguments, and the message constructor for its result), a tuple of commands,
  or `None`.
  Equality holds only when `run` and `to_msg` are named functions, not lambdas;
  the page says so.
- The root component holds the model in a `use_ref`, which is the place Elm's runtime keeps
  it, and a `use_state` counter it bumps to force a render.
  `dispatch` runs `update` on `ref.current`, stores the result, bumps the counter when the
  model changed, and sends each command through `use_send_control()`: a control as itself,
  and a `Perform` as a `Spawn` whose task awaits `run(*args)` and dispatches `to_msg` of the
  result.
  Every command goes through the queue, so `dispatch` returns nothing and two messages in one
  batch both see the latest model.
- `dispatch` is built once from the stable ref, setter, and send function, so it's stable too.
- Elm's subscriptions are components in the view that render nothing and run an effect that
  dispatches (a `ticker(interval, msg, dispatch)` that dispatches every interval).

The page states the convention: app state lives in the model, and only state no other part of
the app reads lives in components.
A view can still contain React-style components, since everything goes through the same
reconciler, which suits widgets with their own presentational state (a text input's cursor),
something Elm itself handles awkwardly.

Add the page to the cookbook section of `mkdocs.yml`.

Tests, in `tests/test_elm_example.py` driving `examples/elm.py` headless:
the counter above renders `[0, 0, 1, 2]`;
`update` returning `Quit()` quits the app;
a `Perform` result is dispatched and the next render shows it;
two messages handled in one batch both apply;
a ticker subscription dispatches until its component is removed from the view.

### 11. Route key and mouse events

**Status:** Needs design

This changes how every example that passes `on_key=` handles keys, so it starts with a short
design doc rather than code.
The shape to evaluate, taken from the DOM:

- A notion of focus: which element receives keys. Candidates are a `focusable` attribute on
  elements plus a `use_focus` hook, or focus held in app state and set by controls.
- Keys dispatch to the focused element, then bubble to its ancestors.
  Mouse events dispatch to the topmost element under the pointer, then bubble.
- A handler stops propagation through its return value, which fits the existing "handlers
  return controls" design better than a method on the event.

Questions the design has to answer:

- What receives keys when nothing is focused? Dispatching to the root and bubbling nowhere
  would keep today's global handlers working only if they sit on the root.
- How does focus move (Tab order, mouse click, explicit control), and is that in scope for
  the first version?
- Whether to keep a migration path where unfocused apps behave as they do today.
- How the Elm recipe's keyboard handling survives. It puts one `on_key` on the root element,
  which acts as Elm's global keyboard subscription only if keys bubble to the root whenever
  the focused element doesn't stop them.

### 12. Add context

**Status:** Not started

A provider component and a `use_context` hook.
`update_shadow` already recurses top-down, so a provider can set a `ContextVar` holding an
immutable mapping of context values for the duration of its children's reconciliation, and
`use_context` reads from it.

This interacts with `plans/component-memoization.md`: a skipped subtree won't see a changed
context value, so a provider whose value changed has to mark its consumers dirty.
Whichever of the two lands second handles that.

Tests: a consumer reads the nearest provider's value; a nested provider shadows an outer one;
a consumer with no provider gets the context's default; changing the provided value
re-renders the consumer.

## Not in scope

- **Error boundaries.** An exception in an effect fails the `TaskGroup` and stops the app,
  and the `finally` in `app()` restores the terminal on the way out. That loud failure is the
  intended behavior; rendering fallback UI over a broken component would hide it.
- **Re-rendering only from the changed component.** Covered by
  `plans/component-memoization.md`.
- **Concurrent rendering, transitions, and Suspense.** A terminal UI has no use for
  interruptible renders.
- **An `elm_app` library API.** Step 10 ships the structure as a recipe until a second app
  shows which of its choices hold.
