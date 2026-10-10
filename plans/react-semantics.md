# Plan: React Semantics

This plan covers the places where counterweight's reconciler, hooks, and event dispatch
diverge from React in ways that make component behavior surprising:
state and effects outliving their component, effect cleanup ordering, keyed children,
setter identity, hook-count checks, key and mouse event routing, and context.
It also adds `use_reducer`, and on top of it an Elm-style app structure
(one model, a pure `view`, messages in) that shares the same runtime.
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

  React guarantees cleanup runs before the next setup, which matters for anything exclusive
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
  mismatch at a slot raises `InconsistentHookExecution`.
- **Every key press reaches every `on_key` handler** (`app.py:401`), and every mouse event
  reaches every element under the pointer (`app.py:407`). There is no focus, no bubbling, and
  no way to stop propagation, so two text inputs on screen both receive typing.
- **No context.** Values needed deep in the tree have to be passed through every component in
  between.
- **No reducer-shaped state.** State that changes in response to messages has to be written
  as a hand-rolled `set_state` updater, and there is no way to structure an app as one model
  with a pure view, which is the shape the Elm architecture (and many ratatui apps) use.
  A prototype `elm_app(init, update, view)` built as a single root component over
  `use_state` runs a counter headless (keys `a`, `b`, `q`) and renders:

  ```text
  models rendered: [0, 0, 1, 2]
  ```

  The first two are the warm-up and the first visible frame, then one render per message,
  and `q` quits through a `Quit()` returned from `update`.
  The prototype calls `update` on the model captured at render time, so two messages
  handled in one batch both see the same model and one update is lost.

## Steps

Each step leaves the test suite passing and is a separate PR.
Reconciler tests go in a new `tests/test_shadow.py` that drives `update_shadow` and
`handle_effects` directly, recording effect start and stop into a list, rather than through
the app loop.

### 1. Start fresh hooks when a component becomes an element

**Status:** Not started

Restrict the `element, ShadowNode(...)` arm to previous nodes with `component is None`.
A previous component node falls through to the `element, None` arm, which builds fresh
`Hooks` and fresh children, so `handle_effects` sees the old effects disappear and cancels
them.

Tests: component replaced by a `Div` stops its effect; a nested component under the replaced
component starts with its initial state; a `use_mouse` listener is removed from
`use_mouse_listeners` after the replacement.

### 2. Cancel stale effects before starting new ones

**Status:** Not started

Split `handle_effects` into two passes over the tree.
The first decides, per effect, whether it keeps its task or reruns, without creating
anything.
Then await cancellation of every active task that isn't kept (reruns and unmounts alike),
and only then create tasks for the reruns.

Tests: a rerun effect logs `stop` before the next `start`; an unmounted effect is stopped
before a sibling's rerun starts.

### 3. Match keyed children by key

**Status:** Not started

When reconciling children, index the previous keyed children by key and match each new
keyed child against that map instead of by position.
Unkeyed children keep matching by position among the unkeyed, as in React.
Only `Component` carries a key, so elements stay positional.
Duplicate keys among siblings raise rather than silently picking one.

Tests: reordering keyed children keeps each child's state and doesn't restart its effects;
removing a keyed child from the middle keeps the state of the ones after it;
inserting at the front mounts only the new child; duplicate sibling keys raise.

### 4. Make setters stable

**Status:** Not started

Create the setter once, when the `UseState` slot is created, and store it on the slot.
It already closes over the slot rather than the value, so a stable setter reads and writes
the same state as today's per-render one.

Tests: the setter returned on the second render is the same object as on the first;
an effect with the setter in its `deps` runs once across several renders.

### 5. Make a setter called after unmount a no-op

**Status:** Not started

Give `Hooks` an `is_mounted` flag.
After `update_shadow`, set it false on every `Hooks` reachable from the previous tree but not
from the new one, the same set difference `handle_effects` uses for tasks.
`set_state` returns without enqueuing `StateSet` when its `Hooks` is unmounted.

Do this after step 4, so the stable setter is the one that checks the flag.

Tests: calling a captured setter after its component unmounts enqueues nothing.

### 6. Raise when the hook count changes between renders

**Status:** Not started

Record `len(hooks.data)` before re-running a component, and raise
`InconsistentHookExecution` if the hook index afterwards differs from it.
A first render has nothing to compare against and is exempt.

Tests: a component that conditionally skips its last hook raises; one that conditionally
adds a hook raises; one that calls the same hooks every render doesn't.

### 7. Add `use_reducer`

**Status:** Not started

`use_reducer(reducer, initial_value)` returns the current state and a `dispatch` function,
where `reducer(state, action)` returns the next state.
`dispatch` applies the reducer to the _latest_ state, not the state captured at render time,
so several dispatches in one batch compose.
Build it on the `UseState` slot and its updater form rather than as a separate slot type,
and keep `dispatch` stable across renders the way step 4 makes setters stable.
Like React's, `dispatch` returns nothing; reducers stay pure and don't produce controls.

Add `docs/hooks/use_reducer.md` to the hooks section of `mkdocs.yml`, and a changelog entry.

Tests: two dispatches from one handler both apply; `dispatch` is the same object across
renders; a reducer that returns an equal state doesn't trigger a render; the initial value
can be lazy, like `use_state`'s.

### 8. Add an Elm-style app structure

**Status:** Not started

`elm_app(init, update, view)` returns a root component for `app()`.
`update(msg, model)` returns the next model and an optional command; `view(model, dispatch)`
returns an element tree whose handlers call `dispatch(msg)`.

A command is one of:

- A control (`Quit()`, `Bell()`, ...). `dispatch` returns it, so a handler written as
  `on_key=lambda e: dispatch(...)` hands it to the app loop the same way a React-style
  handler does.
  This needs the control computed from the latest model inside `dispatch`, so `elm_app`
  uses the `UseState` updater directly rather than `use_reducer`, whose `dispatch` returns
  nothing.
- A coroutine that resolves to a message, for I/O. It runs in the app's `TaskGroup` and
  its message is dispatched when it finishes.

Two questions to settle before writing this step:

- How a command coroutine reaches the `TaskGroup`. The candidates are a new control that
  the app loop spawns (handlers already return controls, and the loop owns the group),
  or a `use_effect` in the root component that drains a queue of pending commands.
  The control is the smaller change.
- Where a control goes when a command coroutine's message produces one. No handler is
  waiting to return it, so it has to go through the event queue.

A view can still contain React-style components, since everything goes through the same
reconciler. That's useful for widgets with their own presentational state (a text input's
cursor), which Elm itself handles awkwardly.
The docs page for `elm_app` states the convention: app state lives in the model,
and only state no other part of the app reads lives in components.

Add `examples/elm.py` and a docs page for the structure, and a changelog entry.

Tests: the counter above, as a test; `update` returning `Quit()` quits the app;
a command coroutine's message is dispatched and the next render shows its effect;
two messages handled in one batch both apply.

### 9. Route key and mouse events

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

### 10. Add context

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
