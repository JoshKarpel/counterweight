# Plan: Incremental Rendering

This plan covers how a frame finds out what changed:
one retained tree that owns every piece of per-node state, reconciliation as a pure function
whose output is applied to taffy in one place, re-running only the components whose state or
arguments changed, and letting the unchanged subtrees that produces skip layout work by identity.
It doesn't cover moving the cell buffer into native code, painting only dirty regions,
throttling the frame rate, or `use_memo`/`use_callback` hooks; see [Out of scope](#out-of-scope).

## Goals, ranked

1. **Confine mutation.** Per-node state lives in one tree, each render phase owns what it
   writes, and no phase writes into another phase's structures.
2. **Pay for what changed.** A frame where one component's state changed costs about what
   that component's subtree costs, not what the whole tree costs.
3. **Change nothing observable** in the steps that only restructure (1 and 3): every test,
   docs screenshot and benchmark last frame stays identical.

Goal 1 outranks goal 2: a step that makes frames faster by adding another place that has to be
kept in sync by hand doesn't qualify, however much it saves.

## Where things stand

Compared with the frameworks counterweight borrows from:

| | Keeps a tree across frames | Re-runs per frame | Finds out what changed by |
|---|---|---|---|
| ratatui | No | Every widget, into a cell buffer | Diffing the buffer against the last one |
| React | Yes (fibers, mutable, double-buffered) | Only components with pending updates, and their non-`memo` descendants | `setState` marking the fiber; `memo` comparing props |
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
  component changed, but enqueues a bare `StateSet` (`hooks/impls.py:61`). The render loop
  turns that into one `should_render` flag and re-runs every component from `screen()`
  (`app.py:288`). Every later stage then rediscovers what changed by hashing values:
  `resolve_style`, `layout_style`, `text_cells`, `text_lines`, `edge_fills`, `border_fills`,
  `_resolve_layout`, and `LayoutTree`'s comparisons. Interning (`@flyweight`) exists to make
  those comparisons cheap.
- **Output size depends on interning.** `paint_to_instructions` starts a new SGR sequence
  whenever a cell's style is a different object from the previous cell's (`output.py:109`),
  so equal styles that are separate instances re-send their SGR sequence.
  Run 14 in `plans/performance-analysis-2026-03-07.md` measured output growing by 49% on
  `top` and 126% on `agent` with `ResolvedCellStyle` interning off.
- **The benchmarks can't show skipped work.** Each workload's model lives in one root
  component, and its `view` is a plain function returning elements (`benchmarks/harness.py`),
  so the root changes every frame and there are no inner components to skip.

## Steps

Each step is its own commit and leaves the system working.
Steps 1 and 3 change nothing observable; check that with `just test`,
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

### 2. Add benchmark workloads built from components

Add a component-structured variant of `dashboard` and of `agent`, named
`dashboard-components` and `agent-components`. Each uses the same model and step as its plain
twin, but its view composes `@component` functions that take slices of the model as arguments:
one per metric card, one per message. A variant's last frame must equal its twin's, which
checks the variant renders the same thing.

Until step 5, the variants exercise the same code as their twins plus component overhead.
Record their frame times now, so steps 4 to 6 have a baseline.

### 3. Own all per-node state in the shadow tree, and reconcile layout as a pure function

**Node identity.** Give each mounted node a `NodeKey` (an `int` from a counter), assigned
when it mounts and carried across frames wherever `update_shadow` carries its hooks today.
Store it on `Hooks`, since `Hooks` is already the per-node object that survives across
frames, and `set_state`'s closure already has it (step 4 needs that).

**Reconciliation.** Replace `LayoutTree._update_node` with a pure function that compares the
previous shadow tree with the next and returns the changes as values:

```python
def layout_changes(previous: ShadowNode | None, next: ShadowNode) -> list[LayoutChange]: ...
```

`LayoutChange` is a union of frozen dataclasses keyed by `NodeKey`:
create a leaf (with its style and `TextSource`), create a container, set a style,
set a text, set the children, and remove. The comparisons `_update_node` makes against
`texts` and `children` become comparisons against the previous node's element and children.
Removal covers every node of an unmounted subtree, as `update` does now, because taffy's
`remove` detaches a node's children rather than removing them.

**Commit.** `LayoutTree` shrinks to the `TaffyTree` and one `dict[NodeKey, waxy.NodeId]`,
which only the commit step reads or writes. It applies a list of changes, computes,
and returns layouts as a value:

```python
@dataclass(frozen=True, slots=True)
class Layouts:
    in_paint_order: tuple[tuple[AnyElement, ResolvedLayout], ...]
    by_key: Mapping[NodeKey, ResolvedLayout]
```

**`use_rects` reads the previous frame's `Layouts`.** The render loop passes it into
`update_shadow` through a context variable, as it passes hook state today, and `use_rects`
looks up its node's key, defaulting to `INITIAL_RESOLVED_LAYOUT` for a node that was hidden
or not yet mounted (as `layout.py:128` does now). `Hooks.dims` and `ShadowNode.layout_node`
are deleted, so layout writes into nothing but its own `TaffyTree`.

**Tests.** `layout_changes` is pure, so its cases are plain assertions on lists of changes,
without taffy: an unchanged frame produces none, a changed text produces one `SetText`,
a moved child produces one `SetChildren`, and an unmounted subtree removes every node in it.
`tests/test_layout_tree.py`'s dirty-node tests keep running against the committed tree.

### 4. Re-run only components whose state changed

**Record what changed, as a value.** `set_state` enqueues `StateSet(key=hooks.key)`.
The render loop collects each frame's keys into a `frozenset[NodeKey]`, and a pure function
computes the keys on a path from the root to any of them:

```python
def dirty_paths(tree: ShadowNode, dirty: frozenset[NodeKey]) -> frozenset[NodeKey]: ...
```

This walks the tree once per frame. It writes no flags onto nodes.

**When a component re-runs.** A component re-runs when any of these holds:

- its key is in `dirty`;
- the component whose returned element contains it re-ran this frame,
  so its arguments may have changed.

A component that calls `use_rects` also has to re-run when its layout moves, or it would keep
the layout from whenever it last ran. Today every component re-runs every frame,
so `use_rects` always returns the previous frame's layout; to keep that meaning,
`use_rects` records the layout it returned on `Hooks`, and before computing `dirty_paths`
the render loop adds to `dirty` every key whose recorded layout differs from its entry in the
previous frame's `Layouts`.

**Otherwise it is reused.** If its key isn't in `dirty_paths`, `update_shadow` returns the
previous `ShadowNode` object, whole subtree included. If its key is in `dirty_paths`, it keeps
its previous element and reconciles its children against the previous element's children,
which carry the same `Component` arguments as last frame, so only the dirty paths below it
re-run.

The same holds for element nodes: an element whose component didn't re-run is the previous
element object, and its subtree is reused unless it's on a dirty path.

**Whole-tree renders.** A resize and resuming from `Suspend` change `screen_style`,
which `screen()` reads from the render loop rather than from an argument, so both re-run
every component, as now. So does the first frame.

**Effects follow renders.** `update_shadow` also returns the keys of the components it ran.
`handle_effects` compares deps only for those components, and keeps the tasks of reused ones
as they are. This matches React, where an effect without deps runs after every render of its
component, not after every frame.

**Tests,** with call counts recorded by a side effect in each component:

- A sibling's state change doesn't re-run a component.
- A parent's state change re-runs its non-`memo` children.
- A grandchild's state change re-runs the grandchild only, and its ancestors are passed through.
- A reused component's `use_effect` with `deps=None` doesn't re-run.
- A component calling `use_rects` re-runs when its layout moved, and is reused when it didn't.
- A resize re-runs every component.
- The new keys in `dirty_paths` match a brute-force walk, as a property test.

### 5. Add `@component(memo=True)`

A `memo` component that would re-run only because its parent re-ran is reused instead
when its arguments equal last frame's (`is` first, then `==`).
`Component` gains a `memo: bool` field, and `component` accepts `memo` as a keyword argument.

Memoization stays opt-in, as React's does:

- Comparing arguments costs more than re-running a cheap component.
- A lambda passed as an argument is a new object every render, so it never compares equal.
- A `memo` component that reads anything besides its arguments and its own hooks
  (a module-level value, or an object it is passed and that is mutated) goes stale silently.

Use it in the step 2 variants' cards and messages, and add tests: a `memo` component with equal
arguments is reused, with changed arguments re-runs, and with its own state changed re-runs.

### 6. Skip layout work for reused subtrees

Since step 4 reuses whole subtrees as the same objects, `layout_changes` can return no changes
for a subtree when `next is previous`, without descending into it. Reconciling layout then
costs about as much as the changed paths do.

Leave the rest alone and measure first:

- Taffy still visits every node in `compute_layout`. Its own cache answers for unchanged
  nodes, so it isn't reconciliation work.
- Reading layouts back still walks every node in `absolute_layouts`, because a reused
  subtree can still move when a sibling grows. `_resolve_layout`'s cache absorbs the cost.
- Paint still repaints the whole buffer and diffs it, as ratatui does. Text and border caches
  are keyed by value.

### 7. Profile, and revisit interning

Profile each workload and each step 2 variant with `just profile`, against a run from before
step 1, and record a new run in `plans/performance-analysis-2026-03-07.md`.

- **Plain workloads** can't skip anything, so they measure overhead: the `dirty_paths` walk,
  `NodeKey` bookkeeping and `Layouts` construction. Each should be within the round-to-round
  spread of its baseline.
- **Component variants** should show `update_shadow` and layout reconciliation shrinking in
  proportion to the share of cards or messages that change per frame.

Then rerun run 13's interning sweep (each of `Cell`, `CellStyle`, `StyledChar` off) on all
eight workloads. Reused subtrees construct fewer values per frame, so interning may stop paying
where it paid before; drop any `@flyweight` that's within the spread on every workload.

## What this costs

- **More concepts.** `NodeKey`, `LayoutChange`, `Layouts` and `dirty_paths` are new names for a
  reader to learn, and the render loop passes one more value from frame to frame.
- **Reuse can hide bugs that full re-renders mask.** A component that depends on something
  outside its arguments and hooks renders correctly today because it re-runs every frame.
  After step 4 it can go stale. `memo` widens that to the component's arguments.
- **Hooks remain mutable.** They are the state store, as in React; this plan confines what
  writes them (the component running, and `set_state`) rather than removing that mutation.

## Out of scope

- **A native cell buffer.** Moving fill, diff and output into Rust would compare cells by
  value cheaply and remove the need for `Cell` interning. Revisit if paint is the largest stage
  after step 7.
- **Rendering from dirty components upward**, as React does, instead of walking from the root.
  The walk from the root costs one pass over the tree; revisit if step 7 shows it.
- **Painting only dirty regions**, as Textual and browsers do. Full repaint and diff is simpler
  and cheap now.
- **Frame rate throttling**, as Ink's `maxFps`. Bursts of events already coalesce into one
  frame when the event queue is drained.
- **`use_memo` and `use_callback`.** Add them if `memo` components need stable callbacks.
