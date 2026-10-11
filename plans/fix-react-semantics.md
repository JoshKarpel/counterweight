# Plan: Fix React Semantics

This plan covers the places where counterweight's reconciler and hooks diverge from React
in ways that make component behavior surprising:
state and effects outliving their component, effect cleanup ordering, keyed children,
setter identity, and hook-count checks.
New features (reducers, event routing, context, and what an Elm-style structure needs from
the runtime) are in `plans/react-features.md`.
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

## Not in scope

- **Error boundaries.** An exception in an effect fails the `TaskGroup` and stops the app,
  and the `finally` in `app()` restores the terminal on the way out. That loud failure is the
  intended behavior; rendering fallback UI over a broken component would hide it.
- **Re-rendering only from the changed component.** Covered by
  `plans/component-memoization.md`.
- **Concurrent rendering, transitions, and Suspense.** A terminal UI has no use for
  interruptible renders.
