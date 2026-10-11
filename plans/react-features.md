# Plan: React Features

This plan covers React features counterweight lacks: reducer-shaped state, key and mouse
event routing, and context.
It also adds a way to send controls from outside an event handler, and a way to start a
tracked task from a handler.
Those two are what an Elm-style app structure (one model, a pure `update`, commands as data)
needs from the runtime, so the plan ends that thread with a cookbook recipe for the structure
rather than a library API.
It builds on `plans/fix-react-semantics.md`, which fixed the reconciler and hooks divergences
(stable setters, keyed children, setters that no-op after unmount, hook-count checks).
It doesn't cover skipping unchanged components; that is `plans/component-memoization.md`.

## Problems

- **No reducer-shaped state.** State that changes in response to messages has to be written
  as a hand-rolled `set_state` updater at every call site.
- **Only an event handler can issue a control.** `handle_control` is reached from handler
  return values and the autopilot (`app.py:405`, `app.py:413`, `app.py:373`), so an effect
  can't `Quit()` when a timer expires or `Bell()` when a background job fails.
- **A handler can't start tracked work.** A handler that calls `asyncio.create_task` gets a
  task outside the app's `TaskGroup`: its exception is only logged when the task is collected,
  and quitting doesn't cancel it. Starting I/O from a key press means routing it through
  state and an effect.
- **Every key press reaches every `on_key` handler** (`app.py:403`), and every mouse event
  reaches every element under the pointer (`app.py:409`). There is no focus, no bubbling, and
  no way to stop propagation, so two text inputs on screen both receive typing.
- **No context.** Values needed deep in the tree have to be passed through every component in
  between.

The second and third are what block an Elm-style structure.
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
Reconciler and hook tests go in `tests/test_shadow.py`, which drives `update_shadow` and
`handle_effects` directly rather than through the app loop.

### 1. Add `use_reducer`

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

### 2. Send controls through the event queue

**Status:** Not started

Add a `ControlSent(control)` event that the app loop passes to `handle_control`, and a
`use_send_control()` hook that returns a stable function enqueuing one.
The drain loop at `app.py:428` already pulls events enqueued while it handles a batch,
so a control sent from a handler or an effect takes effect in the same render cycle as the
event that caused it.
The autopilot's `handle_control` plus `Dummy()` can then become a single `ControlSent`.

The hook returns the function rather than the module exposing it, so a component that sends
controls says so in its own body, the same way `use_state` surfaces the setter.

Add the hook to `docs/hooks/` and the controls page, and a changelog entry.

Tests: an effect that sends `Quit()` quits the app; a `Screenshot` sent from an effect calls
its handler; the function is the same object across renders.

### 3. Start tracked tasks from handlers

**Status:** Not started

Add a `Spawn(run)` control, where `run` is a zero-argument async function returning
`AnyControl | None`.
The app loop starts it in the `TaskGroup`, so its exception fails the group the way an
effect's does, and quitting cancels it.
The control it returns goes through the `ControlSent` event from step 2, since no handler is
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

### 4. Add an Elm architecture recipe

**Status:** Not started

A cookbook page, `docs/cookbook/elm-architecture.md`, and `examples/elm.py`, rather than an
`elm_app` library function.
With stable setters and steps 2 and 3 in place, the adapter is about 25 lines on public APIs,
and its open choices (the command type, batching, how subscriptions look) are opinions a
library API would freeze before a second app has tried them.
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

### 5. Route key and mouse events

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

### 6. Add context

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
- **Concurrent rendering, transitions, and Suspense.** A terminal UI has no use for
  interruptible renders.
- **An `elm_app` library API.** Step 4 ships the structure as a recipe until a second app
  shows which of its choices hold.
