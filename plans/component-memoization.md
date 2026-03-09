# Component Memoization Plan

## Context

Counterweight re-executes **every** component function on **every** render cycle. When `set_state` is called anywhere, a `StateSet` event triggers a full tree re-render — every component from root to leaf runs again, even if its inputs are unchanged. Profiling shows this costs ~1–2.5ms/cycle (12–17% of render time) depending on workload. For the dashboard workload, 12 `metric_card` components re-run unchanged every frame.

This is analogous to React's default behavior before `React.memo`. The goal is to add an opt-in memoization mechanism so unchanged subtrees can be skipped entirely.

## How React Does It (and Why It's Not Automatic)

### React.memo
Wraps a component; on re-render, performs **shallow equality** (`Object.is`) on props. If all props match, the component and its entire subtree are skipped — no re-render, no reconciliation of children.

### Why React doesn't auto-memo every component
1. **Shallow comparison cost vs re-render cost.** For cheap components (a `<div>` with a string), the comparison costs more than just re-rendering. Auto-memo adds overhead to every component, most of which are cheap.
2. **JavaScript reference equality defeats it.** In JS, `{}  === {}` is `false`. Every render that passes an inline object, array, or function as a prop creates a new reference, failing the shallow check. Auto-memo would almost never skip anything without also wrapping every value in `useMemo`/`useCallback`, adding boilerplate everywhere.
3. **Correctness risk.** Components with side effects, context consumption, or other implicit dependencies beyond props would silently break if memoized incorrectly.
4. **React Compiler (React Forget)** is actually moving toward auto-memoization, but it uses **static analysis at compile time** to determine which values need stabilization — something a runtime-only framework can't do.

### Counterweight's situation is different
- Python uses `==` (value equality) by default, not reference equality. `(1, 2) == (1, 2)` is `True`. Frozen dataclasses compare by value. This makes shallow comparison far more useful without needing `use_callback`/`use_memo` wrappers.
- The main failure case is **lambdas/closures passed as args** — `lambda: set_x(1)` creates a new object every render, so `==` fails. But in counterweight, event handlers are typically attached to elements (`Div(on_key=...)`) not passed as component args, making this less of an issue.
- Counterweight components are generally more expensive than React components (Python vs JS speed), so the comparison-to-render cost ratio favors memoization more often.

**Conclusion:** Opt-in `@component(memo=True)` is the right default. Auto-memoization is not justified — some components (those receiving lambdas/closures, or extremely cheap ones) would pay overhead for no benefit.

## Design

### Two layers of optimization

**Layer 1 — Dirty tracking:** Skip entire clean branches. When no `set_state` was called anywhere in a subtree since the last render, the subtree's output is guaranteed unchanged. Propagate `subtree_dirty` flags bottom-up before each render.

**Layer 2 — Memo (prop comparison):** Within a dirty subtree, a re-rendered parent might pass the same props to children. `@component(memo=True)` lets those children skip re-execution if their args match and their own state hasn't changed.

These complement each other:
- Dirty tracking handles "unrelated state change in another part of the tree" (most common case)
- Memo handles "parent re-rendered but my props didn't change" (optimization within dirty subtrees)

### How React compares

React re-renders starting from the dirty component downward, not from root. Ancestors aren't re-rendered. Counterweight always calls `update_shadow(screen(), shadow)` from root — changing this would require a fundamental architecture change (bottom-up navigation to dirty nodes). Instead, we achieve similar efficiency with the top-down approach: walk from root, but skip clean branches via `subtree_dirty` and skip unchanged children via memo. The net effect is the same — only dirty components and their descendants re-execute.

### API: `@component(memo=True)`

```python
@component(memo=True)
def metric_card(label: str, value: int) -> Div:
    return Div(children=[Text(content=f"{label}: {value}")])
```

The `Component` dataclass gains a `memo: bool = False` field.

### Dirty flag on `Hooks`

Add `dirty: bool = False` to the `Hooks` dataclass. In `set_state`'s closure, set `hooks.dirty = True` alongside enqueuing `StateSet`. In `update_shadow`, after executing a component, reset `hooks.dirty = False`.

### `subtree_dirty` on `ShadowNode`

Add `subtree_dirty: bool = False` to `ShadowNode`. Before each `update_shadow` call in app.py, run a bottom-up propagation pass:

```python
def propagate_dirty(node: ShadowNode) -> bool:
    any_child_dirty = any(propagate_dirty(child) for child in node.children)
    node.subtree_dirty = node.hooks.dirty or any_child_dirty
    return node.subtree_dirty
```

This is O(n) — negligible cost (~60µs based on profiling data for framework overhead).

### Decision matrix in `update_shadow` (first match arm: component matches previous)

| memo? | subtree_dirty? | hooks.dirty? | args match? | Action |
|-------|---------------|-------------|------------|--------|
| any | False | False | — | **SKIP**: return previous ShadowNode entirely |
| True | True | False | True | **PASS-THROUGH**: don't execute, recurse into children using previous element's children |
| True | True | False | False | **RE-EXECUTE**: props changed, must re-render |
| True | True | True | — | **RE-EXECUTE**: own state changed |
| False | True | — | — | **RE-EXECUTE**: no memo, current behavior |

The first row (subtree_dirty=False) applies regardless of memo — if nothing in the subtree changed, skip it. This gives non-memo components the benefit of dirty tracking too.

**PASS-THROUGH (row 2)** is the critical case: a memo component whose own props and state are unchanged, but a descendant has dirty state. We must not skip the subtree, but we also don't need to re-execute this component. Instead:
- Reuse the previous element
- Recurse into `previous.element.children` vs `previous.children` to find and update dirty descendants
- Return a new ShadowNode with the previous element but potentially updated children

### Effects when skipped

When a component is skipped, its `ShadowNode` (including all hooks) is reused as-is. `handle_effects` still walks the full tree via `shadow.walk()`:
- `deps=()` effects: `deps == new_deps` → won't re-run. Correct.
- `deps=(x,)` effects: `deps == new_deps` (unchanged since last execution) → won't re-run. Correct.
- `deps=None` effects: `new_deps is None` → will re-run with stale closure. Acceptable — if args and state are unchanged, the closure captures the same values.

### Interaction with `use_mouse` / `use_hovered`

These hooks use `use_state` internally. When mouse state changes, `set_state` is called, which sets `hooks.dirty = True`. The component will re-render on the next cycle. Correct.

### Interaction with `use_rects`

`use_rects` reads `hooks.dims`, which is written by the layout step (not by component execution). If a component is skipped, `dims` still gets updated by layout on the reused `ShadowNode.hooks`. On the next render, `use_rects` reads the updated value. This could cause a subtle issue: the component was skipped, so it rendered with old dims, but dims actually changed. However, resize triggers a full re-render via `TerminalResized` event.

**Decision:** Accept that skipped components may be one frame behind on rect updates after resize. Matches React's behavior with layout effects.

## Implementation Steps

### 1. Add `memo` to `Component` and `@component` decorator
**File:** `src/counterweight/components.py`
- Add `memo: bool = False` field to `Component`
- Add `memo: bool = False` parameter to `component()` decorator, pass through to `Component(...)`

### 2. Add `dirty` flag to `Hooks`
**File:** `src/counterweight/hooks/impls.py`
- Add `dirty: bool = False` field to `Hooks`
- In `set_state` closure: after `hook.value = value`, set `self.dirty = True`
  - The closure currently captures `hook` (the `UseState`), not `self` (the `Hooks`). Need to also capture `self` in the closure. Since `use_state` is a method on `Hooks`, `self` is available.

### 3. Add `subtree_dirty` to `ShadowNode` and propagation function
**File:** `src/counterweight/shadow.py`
- Add `subtree_dirty: bool = False` field to `ShadowNode`
- Add `propagate_dirty(node: ShadowNode) -> bool` function that walks bottom-up, setting `node.subtree_dirty = node.hooks.dirty or any(propagate_dirty(child) for child in node.children)`, returning the result

### 4. Add skip/pass-through logic to `update_shadow`
**File:** `src/counterweight/shadow.py`
- In the first match arm (component matches previous), after extracting args/key/hooks, before executing:

```python
# Layer 1: dirty tracking — skip entire clean subtrees
if not previous.subtree_dirty:
    return previous, 0

# Layer 2: memo — skip unchanged components, pass through to dirty descendants
if next_component.memo and not previous_hooks.dirty:
    if next_args == previous_component.args and next_kwargs == previous_component.kwargs:
        # Pass-through: don't execute, but recurse into children
        children = []
        for new_child, previous_child in zip_longest(previous.element.children, previous.children):
            if new_child is None:
                continue
            child_node, child_ns = update_shadow(new_child, previous_child)
            children.append(child_node)
            user_ns += child_ns
        return ShadowNode(
            component=next_component,
            element=previous.element,
            children=children,
            hooks=previous_hooks,
        ), user_ns
```

- After executing the component (not skipped/pass-through), reset: `previous_hooks.dirty = False`

### 5. Call `propagate_dirty` before `update_shadow` in app.py
**File:** `src/counterweight/app.py`
- Before each `update_shadow(screen(), shadow)` call, add `propagate_dirty(shadow)`

### 6. Tests
**File:** `tests/test_memo.py`

Dirty tracking tests:
- Non-memo component in clean subtree is skipped (track call count via side effect)
- Non-memo component with dirty state re-renders
- Non-memo component in dirty subtree (sibling has dirty state) — only dirty sibling re-renders, clean sibling skipped

Memo tests:
- Memo component with stable args is skipped
- Memo component with changed args re-renders
- Memo component with `set_state` re-renders despite stable args
- Memo parent with stable args + dirty child: parent skipped, child re-renders (pass-through)
- Memo component with `use_effect(deps=())` — effect doesn't re-run when skipped

### 7. (Future) `use_memo` and `use_callback` hooks
Not in scope. Useful for stabilizing computed values and callbacks passed as args to memoized children. Can be added if callback-as-arg patterns become common.

## Files to Modify

| File | Change |
|---|---|
| `src/counterweight/components.py` | Add `memo` param to decorator and `Component` |
| `src/counterweight/hooks/impls.py` | Add `dirty` flag to `Hooks`, set in `set_state` |
| `src/counterweight/shadow.py` | Add `subtree_dirty` field, `propagate_dirty()`, skip/pass-through logic |
| `src/counterweight/app.py` | Call `propagate_dirty` before `update_shadow` |
| `tests/test_memo.py` | New test file |

## Verification

1. `just test` — all existing tests pass
2. Write `tests/test_memo.py` with the cases listed above
3. Run `profiling/dashboard.py` — observe `Updated shadow tree` time decrease (12 metric_cards should be skipped, only the frame counter component re-renders)
4. Run `profiling/canvas.py` — verify no regression (canvas components are not memoized)
