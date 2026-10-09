# Plan: React Semantics

This plan covers the places where counterweight's reconciler, hooks, and event dispatch
diverge from React in ways that make component behavior surprising:
state and effects outliving their component, effect cleanup ordering, keyed children,
setter identity, hook-count checks, key and mouse event routing, and context.
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
  (`app.py:458`) creates the new tasks, then awaits cancellation of the stale ones, so the new
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
  reaches every element under the pointer (`app.py:405`). There is no focus, no bubbling, and
  no way to stop propagation, so two text inputs on screen both receive typing.
- **No context.** Values needed deep in the tree have to be passed through every component in
  between.

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

### 7. Route key and mouse events

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

### 8. Add context

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
