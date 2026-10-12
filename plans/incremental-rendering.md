# Plan: Incremental Rendering

This plan covers how a frame finds out what changed:
one retained tree that owns every piece of per-node state, reconciliation as a pure function
whose output is applied to taffy in one place, re-running only the components whose state or
arguments changed, and letting the unchanged subtrees that produces skip layout work by identity.
It doesn't cover moving the cell buffer into native code, painting only dirty regions,
throttling the frame rate, or a `use_callback` hook; see [Out of scope](#out-of-scope).

## Goals, ranked

1. **Confine mutation.** Per-node state lives in one tree, each render phase owns what it
   writes, and no phase writes into another phase's structures.
2. **Pay for what changed.** A frame where one component's state changed calls components and
   reconciles layout for about that component's subtree, not the whole tree.
   The passes that stay whole-tree (one walk to find dirty paths, taffy's own traversal,
   reading layouts back, paint) call no user code.
3. **Change nothing observable** in the steps that only restructure (1 to 3): every test,
   docs screenshot and benchmark last frame stays identical.

Goal 1 outranks goal 2: a step that makes frames faster by adding another place that has to be
kept in sync by hand doesn't qualify, however much it saves.

## Where things stand

Compared with the frameworks counterweight borrows from:

| | Keeps a tree across frames | Re-runs per frame | Finds out what changed by |
|---|---|---|---|
| ratatui | No | Every widget, into a cell buffer | Diffing the buffer against the last one |
| React | Yes (fibers, mutable, double-buffered) | Only components with pending updates, and their non-`memo` descendants | `setState` marking the fiber; `memo` comparing props; bailing out on an identical element |
| Ink | Yes (React's, plus a Yoga node per element) | As React | As React, plus Yoga's dirty flags |
| Counterweight | Yes (shadow tree and `LayoutTree`) | Every component | Hashing values at every stage |

Counterweight pays for retained trees the way React does, but re-runs everything the way
ratatui does, so it gets neither React's skipped work nor ratatui's lack of bookkeeping.
The `Paint` buffer and its diff already follow ratatui, and stay as they are.

The problems, concretely:

- **Two retained trees kept in sync by hand.** `LayoutTree` (`layout.py:42`) holds a
  `TaffyTree` plus three dicts (`texts`, `children`, `shadows`) mirroring what the shadow tree
  held last frame, so `_update_node` can tell what changed. The previous shadow tree already
  holds that information.
- **Layout writes into earlier stages.** `_update_node` stores the taffy node on the shadow
  node (`shadow.layout_node`, `layout.py:125`), and `compute` writes each node's layout into
  its component's hooks (`hooks.dims`, `layout.py:71` and `layout.py:128`), which `use_rects`
  reads on the next render.
- **Change information is discarded at its source.** `set_state` knows exactly which
  component changed, but enqueues a bare `StateSet` (`hooks/impls.py:51`). The render loop
  turns that into one `should_render` flag and re-runs every component from a new `screen()`
  (`app.py:288`). Every later stage then rediscovers what changed by hashing values:
  `resolve_style`, `layout_style`, `text_cells`, `text_lines`, `edge_fills`, `border_fills`,
  `_resolve_layout`, and `LayoutTree`'s comparisons. Interning (`@flyweight`) exists to make
  those comparisons cheap.
- **Output size depends on interning.** `paint_to_instructions` starts a new SGR sequence
  whenever a cell's style is a different object from the previous cell's (`output.py:109`),
  so equal styles that are separate instances re-send their SGR sequence.
  Run 14 in `plans/performance-analysis.md` measured output growing by 49% on
  `top` and 126% on `agent` with `ResolvedCellStyle` interning off.
- **The benchmarks can't show skipped work.** The workloads already compose `@component`
  functions that take slices of the model (`metric_card`, `process_row`, `message_view`),
  but every model lives in the harness's root component, so the root and therefore every
  component below it re-runs every frame. No workload changes state below the root, and the
  harness times a frame as the interval between two renders of the root
  (`benchmarks/harness.py`), which stops working once the root can be skipped.

## Steps

Each step is its own commit and leaves the system working.
Steps 1 to 3 change nothing observable; check that with `just test`,
the docs screenshots (`uv run python -m docs.examples.generate_screenshots`, no diff),
and every benchmark's `profiles/<name>.txt` against a run from before the step.

### 1. Make output independent of interning

Compare styles by identity first and by equality only when they differ:

```python
if cell.style is not style and cell.style != style:
```

Identity remains the fast path, and interning becomes an optimization nothing depends on.

Verify with run 14's method: output bytes over 100 frames, with `ResolvedCellStyle` interning
on and off, should match each other and run 14's "on" column. Then repeat run 14's frame-time
sweep for `ResolvedCellStyle` alone, and drop its `@flyweight` if it's within the
round-to-round spread. Record the result as a new run in the performance log.

### 2. Make the benchmarks able to show skipped work

**Time frames from the key handler.** The harness's root attaches an `on_key` to the view's
root element that appends the time to `render_starts`, in place of appending it when the root
renders. The autopilot presses one key per frame and every element's `on_key` is called
whether or not its component re-ran, so the interval still covers one whole loop iteration.
Re-baseline every workload's frame times, since the measured interval shifts slightly.

**Add `dashboard-local`.** The same view as `dashboard`, but `frame_counter` holds its tick
in its own `use_state` and steps it from its own `on_key`, so after step 4 the root renders
once and the counter alone re-runs per frame. It's a `Runnable` but not a `Workload`, since its
model isn't held by the root. Its last frame must equal `dashboard`'s, which checks it renders
the same thing.

Until step 4 it exercises the same code as `dashboard`; record its frame times now, so steps
4 to 7 have a baseline. The `memo` variants wait for step 5, which adds `memo`.

### 3. Own all per-node state in the shadow tree, and reconcile layout as a pure function

**Node identity.** Give each mounted node a `NodeKey` (an `int` from a counter), assigned
when its `Hooks` is created and carried across frames wherever `update_shadow` carries its
hooks today. Store it on `Hooks`, since `Hooks` is already the per-node object that survives
across frames. `Hooks.use_state` also passes it into each `UseState` it creates, beside the
`MountStatus` it already shares, so the setter can name its node (step 4 needs that).

**Reconciliation.** Replace `LayoutTree._update_node` with a pure function that compares the
previous shadow tree with the next and returns the changes as values:

```python
def layout_changes(previous: ShadowNode | None, next: ShadowNode) -> list[LayoutChange]: ...
```

`LayoutChange` is a union of frozen dataclasses keyed by `NodeKey`:
create a leaf (with its style and `TextSource`), create a container, set a style,
set or clear a text, set the children, and remove.
The comparisons `_update_node` makes against `texts` and `children` become comparisons
against the previous node's element and children, and a style change is
`layout_style(previous) != layout_style(next)`.

- A node whose element changes kind under the same key keeps its taffy node, as now:
  `Text` to `Div` clears its text and sets its children, and `Div` to `Text` sets its text,
  with its old children removed.
- Removal covers every node of an unmounted subtree, as `update` does now, because taffy's
  `remove` detaches a node's children rather than removing them.
- The list is in the order `update` acts today: children before their parents, removals last.

**Commit.** `LayoutTree` shrinks to the `TaffyTree` and one `dict[NodeKey, waxy.NodeId]`,
which only the commit step reads or writes. It applies a list of changes, computes,
and returns layouts as a value:

```python
@dataclass(frozen=True, slots=True)
class Layouts:
    in_paint_order: tuple[tuple[AnyElement, ResolvedLayout], ...]
    by_key: Mapping[NodeKey, ResolvedLayout]
```

`absolute_layouts` yields taffy nodes, so the commit also takes the next shadow tree and
builds a local `NodeId → ShadowNode` map from it to find each node's element and key.
Unlike today's `shadows`, the map lives only for the call.

**`use_rects` reads the previous frame's `Layouts`.** `update_shadow` takes it as an argument,
and `call_component` exposes it to `use_rects` through a context variable, as it does hook
state. `use_rects` looks up its node's key, defaulting to `INITIAL_RESOLVED_LAYOUT` for a node
that was hidden or not yet mounted (as `layout.py:128` does now). `Hooks.dims` and
`ShadowNode.layout_node` are deleted, so layout writes into nothing but its own `TaffyTree`.

**Freeze `ShadowNode`.** With `layout_node` gone nothing writes a shadow node after it's built,
so make it `frozen=True` with `children` a tuple. Step 4 shares nodes between frames, which is
only safe once that's enforced. `Hooks` stays mutable.

**Tests.** `layout_changes` is pure, so its cases are plain assertions on lists of changes,
without taffy: an unchanged frame produces none, a changed text produces one `SetText`,
a moved child produces one `SetChildren`, a `Text` becoming a `Div` keeps its key,
and an unmounted subtree removes every node in it.
`tests/test_layout_tree.py`'s dirty-node tests keep running against the committed tree,
looking nodes up through its key map instead of `tree.shadows`, and `tests/test_layout.py`'s
hidden-subtree tests assert on `Layouts.by_key` instead of `hooks.dims`.

### 4. Re-run only components whose state changed

**Record what changed, as a value.** `set_state` enqueues `StateSet(key=...)` with its
node's key. The render loop collects each frame's keys into a `frozenset[NodeKey]`, and a pure
function walks the previous tree once and returns the keys on a path from the root to any
dirty node:

```python
def dirty_paths(tree: ShadowNode, dirty: frozenset[NodeKey], layouts: Layouts) -> frozenset[NodeKey]: ...
```

It writes no flags onto nodes.

A component that calls `use_rects` also has to re-run when its layout moves, or it would keep
the layout from whenever it last ran. Today every component re-runs every frame,
so `use_rects` always returns the previous frame's layout; to keep that meaning,
`use_rects` records the layout it returned on `Hooks`, and `dirty_paths` counts a node as
dirty when its recorded layout differs from its entry in `layouts`, in the same walk.

**When a component re-runs.** `update_shadow` re-runs a component when either holds:

- its key is in `dirty`;
- its `Component` is not the previous one (`next is not previous.component`).

The second rule is React's bailout on an identical element. A parent that didn't re-run hands
its children the same `Component` objects as last frame, and a parent that did re-run builds
new ones, so identity says whether the arguments may have changed, with no flag passed down.

**Otherwise it is reused.** If it doesn't re-run and its key isn't in `dirty_paths`,
`update_shadow` returns the previous `ShadowNode` object, whole subtree included.
If its key is in `dirty_paths`, it keeps its previous element and reconciles its children
against the previous element's children, which are the same objects as last frame, so only
the dirty paths below it re-run. Element nodes follow the same rule with
`next is previous.element`.

**Whole-tree renders.** The render loop holds one root `Component` across frames and builds a
new one, re-running every component as now, for the warmup render, the first painted frame,
a resize and a resume from `Suspend`. The first painted frame has to be one: the warmup runs
no effects, so a component the first frame reused would never start its effects.
`screen()` takes `screen_style` as an argument rather than reading it from the render loop's
scope, so its `Component` records what it renders with.
A frame with no state change (`ToggleBorderHealing`, an autopilot control) re-runs nothing
and reuses the whole tree.

**Effects follow renders.** `update_shadow` also returns the hooks of the components it ran
and of the nodes it unmounted, as values alongside the tree. `handle_effects` compares deps
only for the ones that ran, cancels every task of the unmounted ones, and leaves reused ones'
tasks running, so it no longer walks the tree or keeps an `active_effects` set.
This matches React, where an effect without deps runs after every render of its component,
not after every frame.

**Tests,** with call counts recorded by a side effect in each component:

- A sibling's state change doesn't re-run a component.
- A parent's state change re-runs its children.
- A grandchild's state change re-runs the grandchild only, and its ancestors are passed through.
- A `Component` object reused by its parent across renders isn't re-run.
- A reused component's `use_effect` with `deps=None` doesn't re-run.
- An unmounted component's effects are cancelled when its parent re-runs without it.
- A component's effects start on the first painted frame.
- A component calling `use_rects` re-runs when its layout moved, and is reused when it didn't.
- A resize re-runs every component.
- `dirty_paths` matches a brute-force walk, as a property test.

Docs: `docs/ecosystem.md`'s comparison with Ink stops saying Counterweight renders every
component on every render.

### 5. Add `@component(memo=True)`

A `memo` component whose `Component` isn't the previous one is treated as if it were when it
equals last frame's, so step 4's rules then reuse it, pass through it to a dirty descendant,
or re-run it because its own key is in `dirty`:

```python
same = next is previous.component or (next.memo and next == previous.component)
```

`Component`'s generated `__eq__` already compares `func`, `args`, `kwargs` and `key`, and tuple
and dict equality check each element by identity before `==`, so no comparison function is
needed. `Component` gains `memo: bool = field(default=False, compare=False)`: it's a property
of `func`, which is already compared.

**Whole-tree renders mark every node dirty.** Step 4 forced them by building a new root
`Component`, which a `memo` component below an unchanged parent would compare equal through,
so the first painted frame would reuse it and never start its effects.
Instead the render loop adds every key in the previous tree to `dirty`, which re-runs every
component through step 4's first rule, and builds a new root only when `screen_style` changes.

**The decorator.** `component` takes both forms, `@component` and `@component(memo=True)`,
through two `typing.overload` signatures, with `func` positional-only so `memo` must be passed
by keyword. A scratch probe confirmed that mypy keeps the wrapped signature through both forms
and still rejects wrong arguments and a non-element return. Pin that in a type-level test:
`assert_type` on a decorated function in each form, and the rejected calls under
`if TYPE_CHECKING:` with exact `# type: ignore[code]` markers.

Memoization stays opt-in, as React's does:

- Comparing arguments costs more than re-running a cheap component, and `==` on a large
  argument walks all of it unless its elements are shared by identity.
- A lambda passed as an argument is a new object every render, so it never compares equal.
- A `memo` component that reads anything besides its arguments and its own hooks
  (a module-level value, or an object it is passed and that is mutated) goes stale silently.

**Checking purity.** `app` gains `check_purity: bool = False`. When it's on, every component
that step 4 or this step reuses is also called, and the element it returns is compared with the
reused one; a difference raises `ImpureComponent`, naming the component.
It's named for the rule a user breaks (React's docs call it keeping components pure) rather
than for reuse, which is an internal mechanism, or after React's `StrictMode`, which calls
every component twice without comparing, and whose name reads as a setting for production.

Handlers (`on_key`, `on_mouse`) can't be compared with `==`, because a re-run builds new
closures that never equal the old ones, and they can't be skipped either: a handler the
component builds can capture a value it read while rendering, such as a module-level
setting, and that capture is exactly the staleness the check is for.
So two handlers count as the same when they share a `__code__` object, have equal
`__defaults__`, and their closure cells hold the same values (`is`, then `==`), comparing a
captured function by the same rule and a `functools.partial` by its `func`, `args` and
`keywords`. A pair already being compared counts as the same, so a closure that refers to
itself terminates. Every other callable compares with `==`.
A handler passed in as an argument needs nothing extra: a new one fails the argument
comparison, so the component re-runs instead of being reused, and the same one is called
as itself at event time. A scratch probe confirmed the rule: a re-run with nothing changed
compares equal, and a re-run after the captured setting changed doesn't.

Child `Component`s compare field by field under the same rule, not by expanding them, so each
reused descendant gets its own check. Their own `__eq__` would fail a component that passes a
child an inline lambda, which a re-run rebuilds. The extra call runs against a copy of the component's hooks
whose `UseEffect`s are copies, since `use_effect` overwrites `setup` and `new_deps` on the
hook it's given. It schedules no effects, and the copy is discarded.
The test suite, the docs screenshot generator and the benchmarks' last-frame tests run with
it on. It doesn't catch a component that mutates a `Ref` while rendering.

Add `dashboard-memo`, `top-memo` and `agent-memo`: the same model, step and view as their
twins, with the per-item components (`metric_card`, `process_row`, `message_view`) declared
`memo`. Each one's last frame must equal its twin's. `canvas` gets none, since its one large
component changes every frame. Expect the three to differ:

- `metric_card` reads the constant `METRICS`, so every card is reused every frame.
- `message_view` is unkeyed, but messages are appended, so earlier ones keep their index and
  only the streaming one re-runs.
- `process_row` is unkeyed over `busiest`, which is re-sorted every frame, so whenever the order
  changes each index compares against a different process and memo misses.
  Keying rows by pid fixes the pairing but not `selected`, which is computed from the index.
  A memo component in a list that reorders needs keys.

Tests: a `memo` component with equal arguments is reused, with changed arguments re-runs,
and with its own state changed re-runs. With `check_purity` on, a `memo` component that
reads a module-level value changed between frames raises `ImpureComponent`, a reused component
with an inline `on_key` lambda doesn't, one whose `on_key` captured that value does, and the
check's call leaves the component's effect hooks unchanged.

Docs: a `memo` section in `docs/components/index.md`, and `docs/ecosystem.md`'s comparison
with Ink stops saying Counterweight has no `memo`.

### 6. Add `use_memo`

`memo=True` covers per-item components, but some reuse it can't express: an expensive value
derived from arguments (a sort or a filter), a large unchanging part of a component next to a
part that changes, and a handler that has to stay the same object so a `memo` child it's
passed to can hit.

```python
def use_memo[T](compute: Getter[T], deps: tuple[object, ...]) -> T: ...
```

`Hooks.use_memo` stores a `UseMemo` hook holding the value and its deps, calls `compute` on
the first render and whenever `deps != previous deps` (the comparison `handle_effects` makes),
and otherwise returns the stored value. Unlike `use_effect`'s, `deps` can't be `None`:
recomputing every render is what not calling the hook does. `deps=()` computes once.
`compute` runs during render, not after it.

It composes with step 4 with no new rule. A cached element returned from a component is the
previous element, so `next is previous.element` reuses its subtree, and a cached `Component`
is reused by identity whether or not it's `memo`. Memoizing per item can't be done from the
parent, since hooks can't be called in a loop: a changed item count already raises
`InconsistentHookExecution`, and an unchanged count with reordered items pairs each slot with
a different item. Per-item caching goes in the item's component, as `use_memo` or `memo=True`.
A stable handler is `use_memo(lambda: handler, deps)`, so there's no `use_callback`.

**`check_purity` covers it.** On a hit, `compute` also runs and its result is compared with
the stored value by step 5's comparison, handlers included, and a difference raises
`StaleMemo`, naming the component and the hook's index. That catches the two bugs `memo=True`
can't have: a dependency left out of `deps`, and a cached handler that captured state that
has since changed.

Tests: equal deps return the same object, changed deps recompute, `deps=()` computes once,
and a component returning a cached element doesn't re-run the components below it.
With `check_purity` on, a `compute` that reads a value missing from `deps` raises
`StaleMemo`, and so does a cached handler that captured state missing from `deps`, while a
cached handler with complete deps doesn't. No workload gets a variant: none of them derives
an expensive value that survives from one frame to the next.

Docs: `docs/hooks/use_memo.md`, in the hooks nav after `use_ref`.

### 7. Skip layout work for reused subtrees

Since step 4 reuses whole subtrees as the same objects, `layout_changes` can return no changes
for a subtree when `next is previous`, without descending into it. Reconciling layout then
costs about as much as the changed paths do.

Leave the rest alone and measure first:

- Taffy still visits every node in `compute_layout`. Its own cache answers for unchanged
  nodes, so it isn't reconciliation work.
- Reading layouts back still walks every node in `absolute_layouts`, and the commit's
  `NodeId → ShadowNode` map still walks the tree, because a reused subtree can still move when
  a sibling grows. `_resolve_layout`'s cache absorbs most of the cost.
- Paint still repaints the whole buffer and diffs it, as ratatui does. Text and border caches
  are keyed by value.

### 8. Profile, and revisit interning

Profile every workload with `just profile`, against a run from before step 1, and record a
new run in `plans/performance-analysis.md`.

- **The original four workloads** hold their model in the root and declare no `memo`, so
  nothing below the root is skipped and they measure overhead: the `dirty_paths` walk,
  `NodeKey` bookkeeping and `Layouts` construction. Each should be within the round-to-round
  spread of its baseline.
- **`dashboard-local`** should show `update_shadow` and layout reconciliation nearly vanishing,
  since one leaf changes per frame.
- **The `memo` variants** should show `update_shadow` and layout reconciliation shrinking in
  proportion to the share of cards, rows or messages that change per frame.

Then rerun run 13's interning sweep (each of `Cell`, `CellStyle`, `StyledChar` off) on every
workload. Reused subtrees construct fewer values per frame, so interning may stop paying
where it paid before; drop any `@flyweight` that's within the spread on every workload.

### 9. Write a performance guide

Add `docs/performance.md`, after the Cookbook in the nav, for a user whose app feels slow.
It's written last so it can describe what steps 4 to 6 shipped and what step 8 measured,
without quoting frame times. Each section is a question:

1. **Where does my frame's time go?** Profile with Python's sampling profiler
   (`python -m profiling.sampling run app.py`) and read the devlog.
2. **Which components run in a frame?** Step 4's three outcomes (re-run, pass through,
   reuse), drawn as the `dashboard` trees: a component re-runs when its own state changed or
   its parent re-ran. Moving state down to the component that uses it, as `dashboard-local`
   does, is the first fix, and needs no new API.
3. **How do I skip a component whose arguments didn't change?** `memo=True`, with
   `process_row` as the example, and why a list that reorders needs keys.
4. **How do I cache a value?** `use_memo` for derived values, unchanging subtrees and stable
   handlers, and why per-item caching goes in the item's component.
5. **What goes wrong?** Each failure mode as wrong code, its symptom, and its fix:
   - `memo=True`: a callback argument (always misses), an argument mutated in place (stale),
     a hidden input such as a module-level setting (stale), an unkeyed list that reorders
     (misses), a large argument rebuilt every frame (slow hits).
   - `use_memo`: a missing dependency (stale), a cached handler that captured state (stale
     behavior; prefer a functional update such as `set_sort_column(next_column)`), a dependency
     that's new every render (always misses), a hook in a loop (raises), caching something
     cheap (costs more than it saves).
   - A table of both, with which failures `check_purity` catches.
6. **How do I catch stale output?** `check_purity` in tests, what it compares, and what
   gets past it (a `Ref` mutated while rendering).

Runnable examples live in `docs/examples/` and are included with `--8<--` markers, as the other
pages' are. Wrong code is shown in inline fences, since it can't render correctly by design,
but each failure mode the page claims has a test that demonstrates it: a call count for a miss,
and `ImpureComponent` or `StaleMemo` for staleness. A change that stops a failure mode from failing
then breaks a test rather than leaving the page wrong.

## What this costs

- **More concepts.** `NodeKey`, `LayoutChange`, `Layouts` and `dirty_paths` are new names for a
  reader to learn, and the render loop passes one more value from frame to frame.
- **Reuse can hide bugs that full re-renders mask.** A component that depends on something
  outside its arguments and hooks renders correctly today because it re-runs every frame.
  After step 4 it can go stale. `memo` widens that to the component's arguments, and
  `use_memo` adds dependency lists that can be incomplete.
  `check_purity` (steps 5 and 6) turns most of that staleness into an error during tests,
  at the cost of one more call per reused component or cached value when it's on.
- **Elements are trusted not to change after they're returned.** `Div.children` accepts any
  `Sequence`, lists included, and step 4 reuses elements by identity, so code that mutates a
  returned element's children list changes a reused subtree without re-rendering it.
- **Hooks remain mutable.** They are the state store, as in React; this plan confines what
  writes them (the component running, `use_rects` recording what it returned, and `set_state`)
  rather than removing that mutation.

## Out of scope

- **A native cell buffer.** Moving fill, diff and output into Rust would compare cells by
  value cheaply and remove the need for `Cell` interning. Revisit if paint is the largest stage
  after step 8.
- **Rendering from dirty components upward**, as React does, instead of walking from the root.
  The walk from the root costs one pass over the tree; revisit if step 8 shows it.
- **Painting only dirty regions**, as Textual and browsers do. Full repaint and diff is simpler
  and cheap now.
- **Frame rate throttling**, as Ink's `maxFps`. Bursts of events already coalesce into one
  frame when the event queue is drained.
- **`use_callback`.** `use_memo(lambda: handler, deps)` returns a stable handler; add a
  dedicated hook only if that reads badly in practice.
