# Plan: Diagram Engine

Artifact: https://claude.ai/code/artifact/489f87f6-2449-4761-a827-335f68301645

This plan covers laying out boxes and arrows in the terminal,
the way dot lays out graphs for SVG,
with taffy (through waxy) still doing the box layout.
It covers how a diagram engine splits into separable features,
where placement plugs into the render loop,
what the graph core computes,
how diagrams nest clusters,
a working prototype and what it established,
and the prior art it draws on.
It settles one piece of public API, the `Path` element that draws lines,
and leaves the rest open.
The decisions its steps rest on are listed before the steps.

The use cases are an ASCII diagram editor,
and diagrams whose layout is decoupled from their content:
an LLM or a person writes the nodes and edges,
and the engine fits them to whatever screen they land on.

## Three features, not one

A diagram engine is three features, each useful without the others:

- **Placement** decides where the boxes go.
  Layered (Sugiyama) placement, like dot's, is the only one of the three that is graph layout.
- **Routing** draws edges after layout, on the character grid, around other boxes.
  It works on any layout (flex, grid, absolute), not only on placed graphs.
- **Glyphs** turn routed paths into box-drawing characters:
  junctions, arrowheads, and crossings.
  Effects such as drop shadows sit beside them,
  and counterweight's existing border styles already draw those.

Keeping them apart serves both use cases.
An editor wants manual placement with automatic routing,
the way Monodraw keeps lines attached to shapes as they move.
A responsive diagram wants automatic placement.
Neither should pay for the other.

## The prototype

The probe at the end of this plan runs the whole pipeline:

- Graph input: nodes named only by edges join the node list in edge order,
  as Mermaid's `A --> B` declares them.
  Self-loops are rejected.
- Cycle breaking: a depth-first search in input order finds the edges that close a cycle,
  and they're laid out reversed, then drawn upward with the arrowhead under the node they point at.
  Edges between the same two nodes share one line, with an arrowhead for each direction.
- Ranking and ordering: longest-path ranks, then barycenter ordering over four sweeps.
  Long edges pass through 1-cell dummy nodes.
- Coordinate assignment: each node is pulled toward the nodes it connects to,
  minimizing the total horizontal distance along edges
  while keeping each rank's order and a 2-cell gap.
  Edges are weighted 1, 2, or 8 by how many of their ends are dummies, as dot does,
  so long edges straighten first.
  Each rank is solved exactly with pool-adjacent-violators over weighted medians,
  in alternating sweeps.
- Ports: an edge arrives where it already is if that's over the target's interior,
  with arrowheads two cells apart.
  A box grows wider when its label alone leaves too little room for its arrowheads.
  A source with one outgoing edge leaves from wherever that edge lands,
  when that column is within the source's own border.
  An edge with an arrowhead at its source leaves from its own port beside the shared exit.
- Channel tracks: each source's outgoing edges share one horizontal track.
  An edge whose run passes another edge's source column must sit below it,
  and one that passes another's arrival column must sit above it.
  Tracks are assigned in that order.
  Two edges that each must sit below the other cross whatever the order,
  and a longer cycle of these constraints is broken at its leftmost edge,
  a heuristic that can leave a crossing a different break would avoid.
- Layout: the ranks compile into a waxy tree, a column of flex rows,
  and taffy lays it out once.
  Each node's left margin moves it to its assigned x,
  fixed-height spacers between rows hold the edge channels,
  and nodes don't shrink, so a diagram wider than the screen overflows rather than squashing its boxes.
- Drawing: every cell stores up, down, left, and right bits,
  and the glyph comes from their combination.

The probe centers each diagram in the width it's given;
the figures here are trimmed to the diagram.

A request pipeline:

```text
     ╭─────────╮
     │ request │
     ╰────┬────╯
          │
     ╭────┴────╮
     ▼         ▼
 ╭──────╮  ╭───────╮
 │ auth │  │ cache │
 ╰───┬──╯  ╰───┬───╯
     │         │
     │    ╭────┤
     ▼    ▼    │
  ╭────────╮   │
  │ router │   │
  ╰────┬───╯   │
       │       │
       ▼       │
  ╭─────────╮  │
  │ handler │  │
  ╰────┬────╯  │
       │       │
   ╭───┴╮      │
   ▼    │      │
╭────╮  │      │
│ db │  │      │
╰───┬╯  │      │
    │   │      │
    ▼   ▼      │
   ╭────────╮  │
   │ render │  │
   ╰──────┬─╯  │
          │    │
          ▼    ▼
         ╭──────────╮
         │ response │
         ╰──────────╯
```

A CI pipeline, with a wide fan-out and fan-in:

```text
                          ╭──────────╮
                          │ checkout │
                          ╰─────┬────╯
                                │
    ╭───────────┬───────────────┼───────────────┬────────────────╮
    ▼           ▼               ▼               ▼                ▼
╭──────╮  ╭───────────╮  ╭────────────╮  ╭─────────────╮  ╭────────────╮
│ lint │  │ typecheck │  │ unit tests │  │ build wheel │  │ build docs │
╰───┬──╯  ╰─────┬─────╯  ╰────┬───────╯  ╰──┬──────────╯  ╰──┬─────────╯
    │           │             │             │                │
    │           ╰─────╮       │             │                │
    ╰───────────╮     │       │             │                │
                │     │       │             ▼                │
                │     │       │  ╭─────────────╮             │
                │     │       │  │ integration │             │
                │     │       │  ╰──────┬──────╯             │
                │     │       │         │                    │
                │     ╰──╮   ╭╯         │                    │
                ╰──────╮ │   │ ╭────────╯                    │
                       ▼ ▼   ▼ ▼                             │
                      ╭─────────╮                            │
                      │ publish │                            │
                      ╰────┬────╯                            │
                           │                                 │
                           ╰───────────────────────────╮     │
                                                       ▼     ▼
                                                      ╭─────────────╮
                                                      │ deploy docs │
                                                      ╰─────────────╯
```

A job queue, with cycles.
`worker` and `queue` point at each other, so they share a line with an arrowhead at each end,
and `wait` closes a longer loop back to `submit`, whose `▲` has its own port.
`ok` grows past its label to fit four arrowheads:

```text
                          ╭────────╮
                          │ submit │
                          ╰┬───┬───╯
                           ▲   │
        ╭──────────────────╯   ├──────╮
        │                      ▼      │
        │                  ╭───────╮  │
        │                  │ queue │  │
        │                  ╰┬──┬───╯  │
        │                   ▲  │      │
        │                   │  ╰───╮  │
        │                   ▼      │  │
        │              ╭────────╮  │  │
        │              │ worker │  │  │
        │              ╰────┬───╯  │  │
        │                   │      │  │
        │      ╭──────────┬─┴───╮  │  │
        │      ▼          ▼     │  │  │
        │  ╭───────╮  ╭──────╮  │  │  │
        │  │ retry │  │ fail │  │  │  │
        │  ╰───┬───╯  ╰───┬──╯  │  │  │
        │      │          │     │  │  │
        │ ╭────╯          │     ╰─╮│  │
        │ │               ╰─────╮ │╰╮ │
        │ ▼                     ▼ ▼ ▼ ▼
    ╭───┴──╮                   ╭───────╮
    │ wait │                   │  ok   │
    ╰──────╯                   ╰───────╯
```

What it established:

- Coordinate assignment is what makes the output acceptable.
  Without it, the obvious stand-in (flex `space-evenly`)
  spreads every rank across the full width
  and sends long edges down the far side of the screen.
- Coordinate assignment needs every node's width _before_ taffy lays the diagram out.
  The probe knows widths from its labels;
  counterweight would have to measure them first.
- Channel heights are known before layout,
  because they depend only on the ordering and the x positions,
  so once widths are known, taffy still sizes everything in one pass.
  The probe computes x positions, ports, and tracks first,
  then builds and lays out the tree once.
- Edges merge into node borders as `┬` and `┴`,
  the same direction-bits idea `_border_healing.py` uses.

Known weaknesses:

- Crowded targets: arrowheads two cells apart push edges off their straight line,
  so they kink just above a busy box (`publish` above),
  and a box with more inputs than its label is wide grows (`ok` above).
  Taking edges on a box's sides would avoid both.
- Long horizontal runs: `publish` to `deploy docs` runs a long way right,
  because the long edge from `build docs` holds the right-hand column.
  Better ordering heuristics would help.
- Ordering keeps whatever its last sweep produced.
  dot keeps the ordering with the fewest crossings across its sweeps,
  and follows each sweep with transpose, swapping neighbours wherever that removes crossings.
- Coordinate assignment pulls node centers together, not ports,
  so an edge that lands off-center (spread among a busy box's arrivals) pulls its source toward the wrong column.
- Off-center exits: an edge can leave a box off-center (`db`, `render`)
  when that keeps it straight.
- Top to bottom only, and no edge labels.
- Cycle breaking follows input order, not a minimum feedback set,
  so some graphs get more upward edges than they need.
  Finding the fewest edges to reverse is NP-hard, so dot and ELK use heuristics too.
- Self-loops need a route around a box's side, which the probe doesn't have.
- Overflow: a diagram wider than the screen runs off its right edge,
  until fitting (below) narrows it or a scroll container holds it.

## Where placement plugs into taffy

### A: compile to a taffy tree

Pure Python turns the graph into flex rows or grid tracks using only ranks and order,
and taffy sizes and spaces them.
It needs one layout pass and no measuring.
It has no coordinate assignment, though,
so nodes don't line up with what they connect to.

### B: a custom display mode in waxy

waxy implements taffy's
[`LayoutPartialTree`](https://doc.servo.org/taffy/trait.LayoutPartialTree.html),
whose `compute_child_layout` sends a custom display mode to a Python layout function
that can measure its children,
and sends every other mode to taffy's built-in algorithms.
That gives proper coordinate assignment on real sizes, inside taffy's own pass,
and a general extension point for masonry, radial, and other custom layouts.
The cost is in waxy.
It wraps `taffy::TaffyTree` and lays out through `compute_layout_with_measure`,
so becoming a `LayoutPartialTree` implementor means owning its node storage
and implementing taffy's cache traits itself, a rewrite of its core rather than a new hook.
On top of that, Python calling back into Rust to lay out a child,
from inside a layout, is the hard part in pyo3.

The prior art for B is the
[CSS Layout API](https://drafts.css-houdini.org/css-layout-api/)
(`registerLayout` with `intrinsicSizes()` and `layout(children, edges, constraints)`),
SwiftUI's `Layout` protocol, and Flutter's `MultiChildLayoutDelegate`.

### C: measure, then place

Measure each node with taffy, run the pure graph core on those sizes,
then compile positions into the taffy tree as margins or insets.
This is the [React Flow](https://reactflow.dev/learn/layouting/layouting) + dagre/ELK pattern,
and what the probe does with sizes it already knows.
It needs no engine changes, gets real coordinate assignment,
and keeps the graph core pure and cacheable on structure plus sizes.
It costs a measuring pass before the layout pass,
which has to happen within one frame (across frames, through `use_rects`, it would flicker),
and a node that wraps text needs a chosen width to measure at.

The render loop already has this shape.
When focus moves, `_app.py` re-renders the components whose focus changed and lays the tree out again,
all before painting, and raises `UnsettledFocus` if the second pass doesn't settle.
A graph container can follow it: lay out, run the core on the measured sizes,
re-render the container with its positions, and lay out again.

The second pass is needed only when the sizes the core ran on are stale.
A node's size doesn't depend on where it's placed,
as long as it's laid out at max-content width or at a width the engine sets.
Taffy gives an absolutely positioned child with auto width the containing block's full width,
whatever its inset, and the container's width comes from the core's extent,
so an auto-width node would be measured against a width that its own size helps decide.
A pass that places every node where the last frame put it (or at the origin, for a new node)
therefore measures each one correctly.
The container keeps the sizes its positions came from,
and re-renders only when a measured size differs,
as focus settling re-renders only the components whose focus changed.
A frame where nothing in the diagram changed size takes one pass;
a frame that adds a node or edits a label takes two.

`LayoutTree` keeps one taffy tree across frames so taffy reuses the layouts it cached
for unchanged nodes.
The first pass lays each node out at the size the second gives it, so those entries survive.
Whether moving absolutely positioned children invalidates the container's cached layout,
and what the second pass costs when it runs, needs measuring with `just profile`.

### Choice

C, with the graph core written as pure functions
(graph and node sizes in, positions and routes out),
and the measuring done inside the frame.
It costs a second layout pass in every frame where a node in a graph container changes size.

Positions compile into absolute insets, as the shadow probe places its nodes,
rather than the layout probe's flex margins.
Margins need one flex row per rank, which clusters and left-to-right diagrams don't have;
insets are just each node's x and y.
React Flow places its nodes the same way, absolutely within the flow's pane.
Absolutely positioned children don't contribute to their parent's size,
so the container sets its own width and height from the core's extent.
Scroll containers still count them
(taffy's scroll width and height include absolutely positioned descendants),
so a diagram in a `scroll_area` scrolls to its full size.

B is where that core moves if counterweight wants custom layouts in general,
and keeping the core pure keeps that move cheap, but nothing waits on it.
A is ruled out: it skips coordinate assignment.

## The graph core

The core runs the probe's phases as pure functions, in two groups by what they read:

- Structure: cycle breaking, ranking, and ordering read only the nodes and edges.
- Geometry: coordinate assignment, ports, and channel tracks read node sizes and direction too.

The split is what caching and clusters (below) build on.
Each node is given as its outer size plus the part of its border edges may attach to,
the probe's `interior`.
The two differ when a node draws something beside its border, such as a drop shadow:
the core spaces the outer box, and edges attach to the border.

### Ordering

Ordering keeps the sweep with the fewest crossings, as dot does,
and follows each sweep with transpose,
swapping neighbours in a rank wherever that removes crossings.

### Ports

Coordinate assignment pulls ports toward each other, not node centers.
The order of a node's arrivals is known after ordering
(their sources all sit in the rank above, long edges through their dummies),
so each edge's offset along its node's border is known before coordinate assignment,
as ELK layered fixes port order before it places nodes.
An arrival can still slide within its node's interior afterwards
to land where its edge already is, as the probe's do.

### Edge labels

An edge label is a dummy node, sized to its text, in a rank of its own between the edge's ends.
The edge runs into the label and out the other side,
so the label sits on the line, and coordinate assignment keeps room for it as for any node.
dagre, which lays out Mermaid's flowcharts, places labels this way,
but doubles every edge's minimum length and halves the rank gap to make the room.
Counterweight gives only labelled edges a minimum length of 2,
since a rank is at least one row and can't be halved,
so a diagram with one labelled edge isn't twice as tall.

### Direction

The core lays out in two axes, along ranks and across them,
and every direction (top to bottom, bottom to top, left to right, right to left)
maps onto those, as dagre lays out `LR` by swapping each node's width and height
and `BT` by reversing the rank axis.
Each axis takes its own gap, because a cell is about twice as tall as it is wide:
neighbours a column apart in a row read as touching, and neighbours a row apart in a column don't.
Across ranks, arrowheads are two cells apart in either direction,
so in a left-to-right diagram, a box with more arrivals than its height holds grows taller.
Arrowheads point the way their edges flow (`▼`, `▲`, `▶`, `◀`).

## Clusters

A diagram can nest clusters (Mermaid's subgraphs) with edges into their insides.
The engines that do this disagree on how:

- [dot](https://graphviz.org/pdf/dotguide.pdf) lays clusters out with the rest of the graph,
  each in its own rectangle.
  Edges join real nodes only;
  `compound=true` with `lhead` or `ltail` clips an edge at a cluster's border,
  so it reads as pointing at the cluster.
  Its original ranking is recursive on clusters,
  which is why ranking a node inside a cluster level with one outside needs `newrank`.
- [ELK](https://eclipse.dev/elk/reference/options/org-eclipse-elk-hierarchyHandling.html)
  offers both through `hierarchyHandling`:
  by default each compound node gets its own layout run (`SEPARATE_CHILDREN`),
  and `INCLUDE_CHILDREN` lays a node and all its descendants out in one run.
- [Mermaid](https://mermaid.js.org/syntax/flowchart.html) shows the cost of the first:
  "If any of a subgraph's nodes are linked to the outside, subgraph direction will be ignored",
  because a linked subgraph is laid out with its parent and inherits its direction.

Counterweight lays clusters out recursively, in two passes over the cluster tree:
the structure phases from the outermost cluster in, then the geometry phases from the innermost out.

- Each cluster's run sees its own nodes plus one node per child cluster,
  so every level is the flat core the probe already runs.
  Structure needs nothing from the children,
  and a child's geometry gives its node in the parent a size.
  This is also plan C at each level: a laid-out cluster is one more measured node.
- An edge between nodes in different clusters is split at each cluster border it crosses.
  Inside a cluster, its half runs to or from a port on the border,
  on the side facing the edge's other end in the parent's ranking:
  the top if the parent ranks that end above the cluster, the bottom if below.
  The inner run places the port as a dummy node above its first rank or below its last,
  in the order the parent's ordering gives the edges' other ends,
  and the parent's geometry treats it as a fixed port on the cluster's box.
- A cycle through a border is why the side comes from the parent's ranking, not from the edge's direction.
  If `a` inside cluster `C` points at `b` outside it, and `b` points back at `a2` inside `C`,
  the parent sees a cycle between `C` and `b` and reverses one edge.
  Then both edges meet `C` on the side facing `b`,
  and the one pointing into `C` runs up or down to `a2` as a reversed edge, arrowhead and all.
  Structure going outermost first is what makes the parent's ranking known when the inner run places its ports.
- An edge may name a cluster as its end, as dot's `lhead` does,
  and then stops at the parent's level.
- One graph container holds the whole cluster tree,
  so the core sees every crossing edge and the container draws the cluster boxes.

What recursion costs:
the two halves of a crossing edge are placed by separate runs,
so the edge can kink where it crosses the border,
and a cluster's nodes never share a rank with nodes outside it.
A global layout, as dot's, fixes both by changing every phase:
ordering keeps each cluster's members contiguous within each rank,
and coordinate assignment keeps cluster boxes apart.
It takes the same input, a tree of clusters and edges between nodes at any depth,
so it can replace the recursive core later without changing the container.
Recursion would also let a cluster lay out in its own direction,
but then a crossing edge's port no longer sits on the side the cluster's ranks flow from,
so that waits for a design.

## Routing

Connectors between any two elements, drawn after layout, work in every layout mode.
That is the piece the editor case needs most.

- Where it runs: a pass after layout that reads `Layouts.by_key`,
  as border healing reads the paint.
  It needs a module name other than `routing`:
  `counterweight._routing` routes input events to handlers.
- How it draws: onto the same line canvas the graph container draws `Path`s on.
  A connector can be a `Path` its component re-renders once it has its endpoints' rects
  (one more settling pass, like the graph container's),
  or a pass at paint time that writes to the canvas directly.
  Both designs are plausible, and step 7 chooses between them.
- Clipping and scrolling: `by_key` holds each node's rects on screen, already moved by the scroll containers above it,
  with its `clip` and `visible` region, and has no entry for a hidden node.
  Routing in those screen coordinates lets a connector join elements in different containers at no extra cost.
  A connector has to decide what it draws when an endpoint is scrolled out of view, partly clipped, or hidden,
  and a connector between two nodes in one scroll container should scroll with them.
- Path search: A* over cells, scored by length plus a penalty per bend.
  Earlier edges are soft obstacles (termaid charges +2 per cell),
  so later edges avoid them without being blocked.
- Shared channels: Wybrow, Marriott and Stuckey's ordering and nudging,
  so parallel edges never overlap.
  Overlapping edges are mermaid-ascii's most-complained-about flaw.
- Ports: spread edges that land on the same side of a box,
  and leave a straight run before each arrowhead.
- Naming endpoints: an `ElementHandle`, which names an element as a React ref names a DOM node.
  A component creates one with `use_state(ElementHandle)` and passes it to an element's `handle`,
  and `Layouts.handles` maps it to the node's key, so a connector finds its endpoints' rects through `by_key`.
  Inside a graph container, ids local to that container are simpler for the author,
  and the container can turn them into handles itself.

## Glyphs and effects

- Draw lines with a `Path` element, as SVG draws them with `<polyline>`.
  Its points are in its parent's content box,
  it takes no space in layout (like an absolutely positioned overlay),
  its style gives the line's weight, color, and z,
  and arrowheads at either end take the place of SVG's `marker-start` and `marker-end`.
  The graph container draws its edges as `Path`s, and node borders join the same canvas.
- Merge by z: lines merge only with lines at the same z,
  and anything at a higher z covers the cells below it, as stacking does on the web,
  so a popup over a diagram never joins its border to the edges underneath.
  Within one z, a junction takes the style of the line painted last,
  so an edge drawn after the boxes colors the tee where it meets one.
  Healing today compares only graphemes,
  with a TODO in `_border_healing.py` for styles and z.
- Dashes: a dashed line (Mermaid's `-.->`, SVG's `stroke-dasharray`)
  draws its straight runs with `┄`/`┆` (light) or `┅`/`┇` (heavy).
  Box drawing has no dashed corners, junctions, or double lines,
  so those cells stay solid.
- Generalize border healing:
  each cell stores direction bits plus a line weight per direction.
  termaid merges with bits but every junction comes out light,
  so heavy, double, and rounded styles vanish where lines meet.
  `JoinedBorderParts` already knows the four weights,
  and connectors need them mixed:
  a light edge leaving a heavy border is `┯`, neither `┬` nor `┳`.
- Heal along whole edges, not only corners.
  `border_fills` emits healing hints for a border's four corners only,
  so an edge meeting the middle of a border never becomes a tee.
- Protect node borders: an edge may add a tee to a border (`├`) but never overwrite it.
- Respect clips: paint drops a healing hint for a corner outside the element's clip,
  because healing only checks that the cell under a hint is a border character
  and would rewrite another element's border there.
  Line-canvas bits outside a clip need the same rule.
- Tell crossings from merges: `┼` alone can't say whether two edges cross or join.
  Routing should penalize crossings at junctions,
  and merging needs to know which edge each bit came from.

### Drop shadows

Drop shadows need no new feature.
An outer `Div` whose only borders are right and bottom,
contracted by one cell so they start one cell in from the top and left,
draws a shadow behind whatever it wraps.
This is how the slides in
[python-concurrency-and-parallelism](https://github.com/JoshKarpel/python-concurrency-and-parallelism)
draw theirs:

```python
def drop_shadow(*children: Text | Div) -> Div:
    shadow = border_lightshade | border_color("gray", 400)
    return Div(
        style=border_right | border_bottom | border_contract(1) | shadow,
        children=list(children),
    )
```

Any border kind works as the shadow.
The shade kinds give `░`, `▒`, and `▓`,
and `border_thick` gives a thinner half-block shadow with a `▟` corner.

The second probe at the end of this plan draws the request pipeline with counterweight elements,
in the slides' style:
each node is a heavy-bordered `Text` inside a shadow `Div`, placed absolutely,
and the edges are absolutely placed runs of text drawn above the nodes.

```text
      ┏━━━━━━━━━┓
      ┃ request ┃░
      ┗━━━━┯━━━━┛░
       ░░░░│░░░░░░
      ╭────┴─────╮
      ▼          ▼
  ┏━━━━━━┓   ┏━━━━━━━┓
  ┃ auth ┃░  ┃ cache ┃░
  ┗━━━┯━━┛░  ┗━━━┯━━━┛░
   ░░░│░░░░   ░░░│░░░░░
      │    ╭─────┤
      ▼    ▼     │
   ┏━━━━━━━━┓    │
   ┃ router ┃░   │
   ┗━━━━┯━━━┛░   │
    ░░░░│░░░░░   │
        ▼        │
   ┏━━━━━━━━━┓   │
   ┃ handler ┃░  │
   ┗━━━━┯━━━━┛░  │
    ░░░░│░░░░░░  │
   ╭────┴╮       │
   ▼     │       │
┏━━━━┓   │       │
┃ db ┃░  │       │
┗━━┯━┛░  │       │
 ░░│░░░  │       │
   ╰─╮   │       │
     ▼   ▼       │
    ┏━━━━━━━━┓   │
    ┃ render ┃░  │
    ┗━━━━━━━┯┛░  │
     ░░░░░░░│░░  │
            ▼    ▼
           ┏━━━━━━━━━━┓
           ┃ response ┃░
           ┗━━━━━━━━━━┛░
            ░░░░░░░░░░░░
```

What it showed:

- The gap between neighbours grows by one cell for the shadow (2 to 3 in the probe),
  so the router has to count shadow cells as part of the space a node takes up.
  Widening the gap adds that cell on the left of every node too, where there's no shadow.
  The core's outer box does it exactly:
  the shadow wrapper is the node, and it names its bordered child, with an `ElementHandle`,
  as what edges attach to, as a React Flow custom node places its own `<Handle>`s.
  An edge crosses the shadow row as the first row of its channel, as in the probe.
- An edge leaves through the shadow row below its box,
  so edges draw above shadows and cut through them (`░░│░░`).
- Healing joins only corners, so the probe draws each exit tee itself,
  matched to the border's weight (`┯`).

## Fitting the screen and staying put

Counterweight's text measurement already wraps a label at a given width,
so the engine can narrow a box by choosing the width it measures that node at,
before coordinate assignment.
`MeasurableText` answers that for a `Text` node without a layout pass,
and keeps each width it was asked about, so trying several widths is cheap.
A node that is any other element would need a layout pass per width tried,
so fitting narrows `Text` nodes only, and the rest keep their max-content size.
Narrowing those is deferred as expensive.
Boxes must not shrink during layout itself:
taffy's default `flex_shrink` squeezes them below the size the router drew around,
which is why the probe's nodes don't shrink.
On top of narrowing boxes, the engine can shrink gaps
(mermaid-ascii's `--max-width` and termaid's auto-fit both do)
and flip direction from down to right by aspect ratio.
Direction is an argument to the geometry phases only,
so flipping it reuses the structure phases' result.
A diagram that still doesn't fit can sit in a scroll container (`scroll_area`),
as a wide SVG sits in a scrolling `div` on the web, instead of running off the screen's edge.

Stability matters for an editor and for reactive re-renders alike:

- No randomness.
  TALA tries three seeds and keeps the best,
  and says "adding one node can change the whole diagram".
- Input order breaks ties,
  a lesson from ELK's retrospective, where users said drawings change unexpectedly.
  That rules out iterating over sets of node names,
  whose order changes between runs with Python's hash seed.
- Pinning: some nodes keep fixed positions,
  as in ELK's `semiInteractive` mode and TALA's partial positions.
- Caching: key each group of phases on what it reads,
  the structure phases on the graph alone and the geometry phases on its sizes and direction too.
  Editing a label then moves boxes along their rank but never reorders them,
  which tests can hold the core to.

Parsing a subset of Mermaid's flowchart syntax splits the work cleanly for LLM output:
the model writes the nodes and edges, and the engine lays them out.

## Decisions

The use cases rank diagrams above the editor.

1. The graph core comes first.
   It's pure and depends on nothing, it's the riskiest part,
   and building it first shows what the graph container needs from the line canvas
   before the canvas is designed.
   The line canvas follows, because both features draw on it.
   It's all they share: the graph container draws its edges from the core's ports and channel tracks,
   not with the connectors' A*.
   The rest of the diagram steps follow, then connectors,
   so the least explored part (A*, nudging, and the rules for clipped endpoints) is proven last,
   and the editor waits for it.
2. Edges cross container boundaries in both features:
   connectors in screen space (see [Routing](#routing)),
   and graph edges into recursively laid-out clusters (see [Clusters](#clusters)).
3. Placement measures, then places (C), compiling positions into absolute insets.
   A custom display mode in waxy (B) stays open for custom layouts in general,
   and nothing here waits on it.
4. Lines are drawn with a public `Path` element.
   They merge only with lines at the same z,
   and a junction takes the style of the line painted last
   (see [Glyphs and effects](#glyphs-and-effects)).
5. An edge label is a dummy node in a rank of its own, as in dagre,
   and only labelled edges are lengthened to make room for it
   (see [Edge labels](#edge-labels)).

## Proposed steps

1. Graph core: pure functions for the structure phases (cycle breaking, ranking,
   and ordering that keeps its best sweep and transposes)
   and the geometry phases (coordinate assignment pulling port to port, ports, and channel tracks),
   with edge labels as dummy nodes, in all four directions, tested directly on plain data.
   Then clusters: structure from the outermost cluster in, geometry from the innermost out,
   with crossing edges split at border ports on the side facing their other end.
   Each node is an outer size plus the part of its border edges attach to,
   and each axis takes its own gap as an argument.
   Tests cover cycles, sinks above the last rank, isolated nodes,
   boxes with more inputs than their label is wide, labelled edges, each direction,
   edges into, out of, and between clusters, or naming a cluster as their end,
   cycles through a cluster's border,
   and that changing a node's size never changes the ordering.
2. Line canvas: per-cell direction bits with a weight per direction, and dashes on straight runs,
   drawn with a public `Path` element and resolved to glyphs at paint time.
   Lines merge only within one z, a junction takes the style of the line painted last,
   node borders are protected, and clips are respected.
   Border healing moves onto it, healing along whole edges rather than only corners.
3. Graph container: lay nodes out at max-content width, run the core on their sizes,
   compile positions into absolute insets and the container's size from the core's extent,
   and draw nodes, cluster boxes, and edges (as `Path`s) onto the line canvas.
   A frame lays out a second time, as focus settling does,
   only when a node's size differs from the one its position came from.
4. Fitting: narrow `Text` nodes, shrink gaps, then flip direction, when the diagram doesn't fit.
5. Drop shadows: document the wrapper pattern (a cookbook page),
   and have the wrapper name its bordered child as what edges attach to,
   so the core spaces the shadow and edges meet the border.
6. Mermaid subset: flowchart syntax in every direction (`TD`/`TB`, `BT`, `LR`, `RL`),
   edge labels (`-->|text|`), dotted and thick edges (`-.->`, `==>`) as dashes and heavy lines,
   and subgraphs, parsed into the graph container,
   with nodes declared by the edges that name them.
   Self-loops need routing around a box's side before they can be accepted.
7. Connectors: a post-layout pass between elements named by `ElementHandle`, in any containers,
   drawn onto the line canvas,
   with A* using bend and soft-obstacle costs, port spreading, and arrowheads,
   then ordering and nudging in shared channels,
   and a rule for endpoints that are scrolled away, clipped, or hidden.

## Prior art

- [termaid](https://github.com/fasouto/termaid):
  pure Python with a Textual widget, and the closest match.
  A coarse grid with content-sized tracks (effectively CSS grid),
  gaps widened where edges need room, and direction-bit junction merging.
- [mermaid-ascii](https://github.com/AlexanderGrooff/mermaid-ascii) and
  [beautiful-mermaid](https://github.com/lukilabs/beautiful-mermaid):
  a grid plus A*, no crossing reduction, overlapping edges.
  beautiful-mermaid uses ELK for SVG but kept the grid engine for ASCII.
- [D2's ASCII renderer](https://d2lang.com/blog/ascii/):
  scales down an ELK layout computed in pixels, which leaves lopsided boxes.
  Lay out on the character grid directly instead.
- [dagre](https://github.com/dagrejs/dagre):
  the layered layout behind Mermaid's flowcharts,
  and the model for edge labels as dummy nodes and for laying out every direction in one.
- [React Flow](https://reactflow.dev/):
  nodes placed absolutely in a pane, with `<Handle>`s inside a custom node for edges to attach to.
- [ELK layered](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)
  and its [retrospective](https://arxiv.org/abs/2311.00533):
  the reference design for phases and ports.
- [libavoid](https://www.adaptagrams.org/documentation/libavoid.html) and
  [Wybrow, Marriott and Stuckey](https://users.monash.edu/~mwybrow/papers/wybrow-gd-2009.pdf):
  orthogonal routing for interactive editors,
  with ordering and nudging of shared channels.
- [Sapling renderdag](https://docs.rs/sapling-renderdag/latest/renderdag/):
  a lane model, far simpler for mostly linear graphs,
  that leaves the choice of line characters to the renderer.
- [Graph::Easy](https://metacpan.org/pod/Graph::Easy),
  [ascii-dag](https://github.com/AshutoshMahala/ascii-dag),
  and [Monodraw](https://monodraw.helftone.com/):
  the classic DOT-to-box-art converter, a Rust Sugiyama renderer for text,
  and a manual editor whose lines stay attached to shapes.
- The CSS Layout API
  ([explainer](https://github.com/w3c/css-houdini-drafts/blob/main/css-layout-api/EXPLAINER.md))
  and taffy's [`compute`](https://doc.servo.org/taffy/compute/index.html) module:
  custom-layout extension points.

## Prototype source

These probes produced every diagram in this plan.
Both are exploration code (untyped, untested),
written to answer whether the approach holds up, not a starting point to ship.

### Layout and routing

Save it as `layered.py` and run it from this repository, which provides waxy:
`uv run python layered.py ci 80`.
It takes a graph name (`request`, `ci`, or `retry`) and an available width.

```python
"""
Throwaway probe of a layered (Sugiyama-style) diagram engine for counterweight.

Ranks, orders and x-coordinates are computed in Python, compiled into a waxy/taffy tree of flex rows
(each node pushed to its x by a left margin, channel spacers between rows), laid out by taffy in one pass,
then edges are routed in the inter-rank channels and drawn with box-drawing characters.

Run from the counterweight repo, which provides waxy: `uv run python layered.py [request|ci|retry] [width]`.
"""

import sys
from collections import defaultdict, deque

import waxy

GRAPHS = {
    "request": (
        ["request", "auth", "cache", "router", "handler", "db", "render", "response"],
        [
            ("request", "auth"),
            ("request", "cache"),
            ("auth", "router"),
            ("cache", "router"),
            ("cache", "response"),
            ("router", "handler"),
            ("handler", "db"),
            ("handler", "render"),
            ("db", "render"),
            ("render", "response"),
        ],
    ),
    "ci": (
        [
            "checkout",
            "lint",
            "typecheck",
            "unit tests",
            "build wheel",
            "build docs",
            "integration",
            "publish",
            "deploy docs",
        ],
        [
            ("checkout", "lint"),
            ("checkout", "typecheck"),
            ("checkout", "unit tests"),
            ("checkout", "build wheel"),
            ("checkout", "build docs"),
            ("build wheel", "integration"),
            ("lint", "publish"),
            ("typecheck", "publish"),
            ("unit tests", "publish"),
            ("integration", "publish"),
            ("build docs", "deploy docs"),
            ("publish", "deploy docs"),
        ],
    ),
    # Nodes named only by edges, a two-node cycle, a longer cycle, and a box with more inputs than its label is wide.
    "retry": (
        [],
        [
            ("submit", "queue"),
            ("queue", "worker"),
            ("worker", "queue"),
            ("worker", "ok"),
            ("worker", "retry"),
            ("retry", "wait"),
            ("wait", "submit"),
            ("submit", "ok"),
            ("worker", "fail"),
            ("fail", "ok"),
            ("queue", "ok"),
        ],
    ),
}


def acyclic(nodes, edges):
    """
    The edges that close a cycle: each one points back to a node still on the stack of a depth-first search,
    which visits nodes and edges in input order so the same graph always breaks at the same edges.
    Reversing them leaves the graph acyclic.
    """
    succs = defaultdict(list)
    for s, t in edges:
        succs[s].append(t)
    on_stack, done, back = set(), set(), set()
    for root in nodes:
        if root in done:
            continue
        on_stack.add(root)
        stack = [(root, iter(succs[root]))]
        while stack:
            n, untried = stack[-1]
            for t in untried:
                if t in on_stack:
                    back.add((n, t))
                elif t not in done:
                    on_stack.add(t)
                    stack.append((t, iter(succs[t])))
                    break
            else:
                on_stack.discard(n)
                done.add(n)
                stack.pop()
    return back


def layers(nodes, edges):
    """Longest-path layering, visiting nodes in topological order so long chains don't recurse."""
    preds, succs = defaultdict(list), defaultdict(list)
    for s, t in edges:
        preds[t].append(s)
        succs[s].append(t)
    waiting = {n: len(preds[n]) for n in nodes}
    ready = deque(n for n in nodes if not waiting[n])
    rank = {}
    while ready:
        n = ready.popleft()
        rank[n] = 1 + max((rank[p] for p in preds[n]), default=-1)
        for t in succs[n]:
            waiting[t] -= 1
            if not waiting[t]:
                ready.append(t)
    return rank


def add_dummies(nodes, edges, rank):
    """
    Split edges spanning several ranks into chains through 1-cell-wide dummy nodes.
    Also returns the edge each piece of a chain came from.
    """
    nodes = list(nodes)
    rank = dict(rank)
    out = []
    chain = {}
    for s, t in edges:
        prev = s
        for k in range(rank[s] + 1, rank[t]):
            d = f"~{s}>{t}#{k}"
            nodes.append(d)
            rank[d] = k
            out.append((prev, d))
            chain[(prev, d)] = (s, t)
            prev = d
        out.append((prev, t))
        chain[(prev, t)] = (s, t)
    return nodes, out, chain, rank


def order(nodes, edges, rank, sweeps=4):
    """
    Barycenter crossing reduction, alternating down and up sweeps.
    A node with no neighbours in the reference rank keeps its current position as its key.
    """
    by_rank = defaultdict(list)
    for n in nodes:
        by_rank[rank[n]].append(n)
    preds, succs = defaultdict(list), defaultdict(list)
    for s, t in edges:
        preds[t].append(s)
        succs[s].append(t)
    depth = max(by_rank) + 1
    for i in range(sweeps):
        down = i % 2 == 0
        for r in range(1, depth) if down else range(depth - 2, -1, -1):
            ref = by_rank[r - 1] if down else by_rank[r + 1]
            pos = {n: j for j, n in enumerate(ref)}
            nbrs = preds if down else succs
            # Read positions before sorting: CPython empties a list while sorting it, so `.index` would fail.
            current = {n: j for j, n in enumerate(by_rank[r])}

            def bary(n):
                ps = [pos[p] for p in nbrs[n] if p in pos]
                return sum(ps) / len(ps) if ps else current[n]

            by_rank[r].sort(key=bary)
    return [by_rank[r] for r in range(depth)]


def channel_tracks(ranked, edges, bundle, xs_out, xs_in):
    """
    One horizontal track per bundle in each inter-rank gap, stacked so bundles don't cross where
    the ordering constraints between them agree, and packed so bundles that don't overlap share a track.
    Returns each bundle's track and each gap's track count.
    """
    rank_of = {n: r for r, ns in enumerate(ranked) for n in ns}
    bundles_by_gap = defaultdict(lambda: defaultdict(list))
    for e in edges:
        bundles_by_gap[rank_of[e[0]]][bundle[e]].append(e)
    tracks = {}
    heights = []
    for r in range(len(ranked) - 1):
        nets = {}
        for b, es in bundles_by_gap[r].items():
            bottoms = [xs_in[e] for e in es]
            xs = [xs_out[b], *bottoms]
            if min(xs) != max(xs):
                nets[b] = (min(xs), max(xs), xs_out[b], bottoms)

        # A net whose horizontal run passes another's source column must sit below it,
        # and one that passes another's arrival column must sit above it; otherwise they cross.
        below = defaultdict(set)
        for a, (alo, ahi, _, _) in nets.items():
            for b, (_, _, btop, bbottoms) in nets.items():
                if a == b:
                    continue
                if alo <= btop <= ahi:
                    below[b].add(a)
                if any(alo <= x <= ahi for x in bbottoms):
                    below[a].add(b)
        for a in nets:  # Contradictory pairs cross whatever we do, so drop both constraints.
            for b in list(below[a]):
                if a in below[b]:
                    below[a].discard(b)
                    below[b].discard(a)
        above = defaultdict(set)
        for a, bs in below.items():
            for b in bs:
                above[b].add(a)

        placed: dict[int, list[tuple[int, int]]] = defaultdict(list)
        remaining = dict.fromkeys(nets)  # Ordered, so ties break the same way on every run.
        while remaining:
            ready = [n for n in remaining if not above[n] & remaining.keys()]
            # A longer cycle can't be satisfied either. Breaking it at the leftmost net is a heuristic:
            # a different break might violate fewer constraints.
            n = min(ready or remaining, key=lambda n: nets[n][:2])
            del remaining[n]
            lo, hi = nets[n][:2]
            k = 1 + max((tracks[p] for p in above[n] if p in tracks), default=-1)
            while any(not (hi < plo - 1 or lo > phi + 1) for plo, phi in placed[k]):
                k += 1
            tracks[n] = k
            placed[k].append((lo, hi))
        heights.append(1 + max(placed, default=-1))
    return tracks, heights


def node_sizes(nodes, ports):
    """
    Each node's (width, height). A dummy is one cell wide.
    A box fits its label, and grows so the ports on its busier side fit two cells apart within its border.
    """
    return {n: (1, 3) if n.startswith("~") else (max(len(n) + 4, 2 * ports[n] + 1), 3) for n in nodes}


def spread(wants, lo, hi):
    """
    Ports for edges that want the given columns, in order, kept within [lo, hi] and two cells apart
    so arrowheads don't touch: pushed right, then back left.
    The range must be wide enough to hold them all, or the push left passes `lo`.
    """
    ports = [min(max(x, lo), hi) for x in wants]
    for k in range(1, len(ports)):
        ports[k] = max(ports[k], ports[k - 1] + 2)
    ports[-1] = min(ports[-1], hi)
    for k in range(len(ports) - 2, -1, -1):
        ports[k] = min(ports[k], ports[k + 1] - 2)
    return ports


def weighted_median(points):
    """The L1-optimal position for weighted (value, weight) points, taking the midpoint of a flat optimum."""
    points = sorted(points)
    total = sum(w for _, w in points)
    acc = 0.0
    for i, (v, w) in enumerate(points):
        acc += w
        if acc > total / 2 + 1e-9:
            return v
        if abs(acc - total / 2) < 1e-9:
            return (v + points[i + 1][0]) // 2
    return points[-1][0]


def place_rank(ns, targets, sizes, gap):
    """
    Left x for each node of one rank, minimizing the weighted distance of each node's center from its targets
    subject to keeping the rank's order with at least `gap` between neighbours:
    pool-adjacent-violators with weighted medians, which is exact for this L1 objective.
    """
    blocks = []  # [members [(node, offset)], extent, points [(value, weight)], pos]
    for n in ns:
        w = sizes[n][0]
        points = [(c - w // 2, wt) for c, wt in targets[n]]
        block = [[(n, 0)], w, points, weighted_median(points)]
        blocks.append(block)
        while len(blocks) > 1 and blocks[-2][3] + blocks[-2][1] + gap > blocks[-1][3]:
            b2 = blocks.pop()
            b1 = blocks.pop()
            shift = b1[1] + gap
            members = b1[0] + [(m, off + shift) for m, off in b2[0]]
            points = b1[2] + [(v - shift, wt) for v, wt in b2[2]]
            blocks.append([members, shift + b2[1], points, weighted_median(points)])
    return {m: b[3] + off for b in blocks for m, off in b[0]}


def assign_x(ranked, edges, sizes, gap):
    """
    Coordinate assignment in the style of dot's: pull every edge vertical, weighting edges by how many of
    their ends are dummies (1, 2, 8) so long edges straighten first. Gauss-Seidel sweeps over the ranks.
    """
    nbrs = defaultdict(list)
    for s, t in edges:
        wt = (1, 2, 8)[s.startswith("~") + t.startswith("~")]
        nbrs[s].append((t, wt, "down"))
        nbrs[t].append((s, wt, "up"))
    xs = {}
    for ns in ranked:
        x = 0
        for n in ns:
            xs[n] = x
            x += sizes[n][0] + gap

    def center(n):
        return xs[n] + sizes[n][0] // 2

    for sweep in range(12):
        down = sweep % 2 == 0
        order_ = ranked if down else ranked[::-1]
        for ns in order_:
            targets = {}
            for n in ns:
                use = [(center(m), wt) for m, wt, side in nbrs[n] if sweep >= 2 or side == ("up" if down else "down")]
                targets[n] = use or [(center(n), 0.01)]
            xs.update(place_rank(ns, targets, sizes, gap))
    lo = min(xs.values())
    return {n: x - lo for n, x in xs.items()}


def layout(ranked, xs, sizes, width, channel_heights):
    """
    Lay out the ranks as a column of flex rows with fixed-height channel spacers between them,
    each node pushed to its assigned x by its left margin.
    Nodes don't shrink: a diagram wider than `width` overflows rather than squashing its boxes.
    """
    tree = waxy.TaffyTree()
    names = {}
    rows = []
    for r, ns in enumerate(ranked):
        kids = []
        right = 0
        for n in ns:
            w, h = sizes[n]
            leaf = tree.new_leaf(
                waxy.Style(
                    size_width=waxy.Length(w),
                    size_height=waxy.Length(h),
                    margin_left=waxy.Length(xs[n] - right),
                    flex_shrink=0.0,
                )
            )
            names[leaf] = n
            right = xs[n] + w
            kids.append(leaf)
        rows.append(
            tree.new_with_children(
                waxy.Style(flex_direction=waxy.FlexDirection.Row, align_items=waxy.AlignItems.Center),
                kids,
            )
        )
        if r < len(ranked) - 1:
            # +2: one row to leave the source, one for the arrowhead.
            rows.append(tree.new_leaf(waxy.Style(size_height=waxy.Length(channel_heights[r] + 2))))
    root = tree.new_with_children(
        waxy.Style(flex_direction=waxy.FlexDirection.Column, size_width=waxy.Length(width)), rows
    )
    tree.compute_layout(root, waxy.AvailableSize(width=waxy.Definite(width), height=waxy.MaxContent()))
    rects = {
        names[node]: (int(pos.x), int(pos.y), int(lay.size.width), int(lay.size.height))
        for node, pos, lay in tree.absolute_layouts(root)
        if node in names
    }
    return rects, int(tree.layout(root).size.height)


U, D, L, R = 1, 2, 4, 8
GLYPH = {
    U | D: "│",
    L | R: "─",
    D | R: "╭",
    D | L: "╮",
    U | R: "╰",
    U | L: "╯",
    U | D | R: "├",
    U | D | L: "┤",
    D | L | R: "┬",
    U | L | R: "┴",
    U | D | L | R: "┼",
    U: "│",
    D: "│",
    L: "─",
    R: "─",
}


def interior(x, w):
    """The columns of a box an edge may attach to: all of a 1-cell dummy, or a box's border minus its corners."""
    return (x, x) if w == 1 else (x + 1, x + w - 2)


def render(nodes, edges, width):
    _, width, height, cells = draw(nodes, edges, width)
    return "\n".join("".join(cells.get((x, y), " ") for x in range(width)).rstrip() for y in range(height))


def draw(nodes, edges, width, gap=2, boxes=True):
    """
    Each real node's rect, the drawing's width and height, and its non-blank cells by position:
    edges and arrowheads, plus boxes and labels if `boxes`.
    The drawing is `width` wide, or wider if the diagram doesn't fit.

    Nodes named only by edges are added after `nodes`, in edge order.
    Edges that close a cycle are drawn upward, with the arrowhead under the node they point at.
    Edges between the same two nodes share one line, with an arrowhead for each direction.
    """
    if loops := [s for s, t in edges if s == t]:
        raise ValueError(f"self-loops aren't supported: {loops}")
    nodes = list(dict.fromkeys([*nodes, *(n for e in edges for n in e)]))
    back = acyclic(nodes, edges)
    heads = defaultdict(set)  # Which ends of each downward edge carry an arrowhead.
    for s, t in edges:
        if (s, t) in back:
            heads[(t, s)].add("up")
        else:
            heads[(s, t)].add("down")
    rank = layers(nodes, list(heads))
    all_nodes, split, chain, rank = add_dummies(nodes, list(heads), rank)
    ranked = order(all_nodes, split, rank)

    outgoing, incoming = defaultdict(list), defaultdict(list)
    for s, t in split:
        outgoing[s].append(t)
        incoming[t].append(s)
    # Edges leave a source together, sharing one exit column and one channel track,
    # except that an edge with an arrowhead at its source leaves on its own when the source has other edges.
    bundle = {(s, t): (s, t) if "up" in heads[chain[(s, t)]] and len(outgoing[s]) > 1 else s for s, t in split}
    exits = defaultdict(list)
    for (s, _), b in bundle.items():
        if b not in exits[s]:
            exits[s].append(b)
    sizes = node_sizes(all_nodes, {n: max(len(incoming.get(n, ())), len(exits.get(n, ()))) for n in all_nodes})

    xs = assign_x(ranked, split, sizes, gap)
    extent = max(xs[n] + sizes[n][0] for n in xs)
    width = max(width, extent)
    xs = {n: x + (width - extent) // 2 for n, x in xs.items()}
    xs_out = {b: xs[s] + sizes[s][0] // 2 for (s, _), b in bundle.items()}
    xs_in = {}
    # Land each edge where it already is when that's over the box.
    for t, ss in incoming.items():
        x, w = xs[t], sizes[t][0]
        if len(ss) == 1:
            xs_in[(ss[0], t)] = x + w // 2
            continue
        ss = sorted(ss, key=lambda s: xs_out[bundle[(s, t)]])
        for s, p in zip(ss, spread([xs_out[bundle[(s, t)]] for s in ss], x + 1, x + w - 2)):
            xs_in[(s, t)] = p
    # Leave each upward edge toward where it lands, beside the source's shared exit.
    for s, bs in exits.items():
        if len(bs) == 1:
            continue
        want = {b: xs_out[b] if b == s else xs_in[b] for b in bs}
        bs = sorted(bs, key=want.__getitem__)
        for b, p in zip(bs, spread([want[b] for b in bs], xs[s] + 1, xs[s] + sizes[s][0] - 2)):
            xs_out[b] = p
    for s, t in split:
        if len(outgoing[s]) != 1 or len(incoming[t]) != 1:
            continue
        (slo, shi), (tlo, thi) = interior(xs[s], sizes[s][0]), interior(xs[t], sizes[t][0])
        lo, hi = max(slo, tlo), min(shi, thi)
        if lo <= hi:
            x = xs_out[s] if lo <= xs_out[s] <= hi else xs_in[(s, t)] if lo <= xs_in[(s, t)] <= hi else (lo + hi) // 2
            xs_out[s] = xs_in[(s, t)] = x
    # A source with one outgoing edge can leave from wherever that edge lands, if that's over its own interior.
    for s, (t,) in ((s, ts) for s, ts in outgoing.items() if len(ts) == 1):
        sx, sw = xs[s], sizes[s][0]
        if sw >= 3 and sx + 1 <= xs_in[(s, t)] <= sx + sw - 2:
            xs_out[s] = xs_in[(s, t)]
    tracks, heights = channel_tracks(ranked, split, bundle, xs_out, xs_in)
    rects, height = layout(ranked, xs, sizes, width, heights)

    bits = defaultdict(int)
    text = {}

    def seg(x0, y0, x1, y1):
        if x0 == x1:
            for y in range(min(y0, y1), max(y0, y1)):
                bits[(x0, y)] |= D
                bits[(x0, y + 1)] |= U
        else:
            for x in range(min(x0, x1), max(x0, x1)):
                bits[(x, y0)] |= R
                bits[(x + 1, y0)] |= L

    for n, (x, y, w, h) in rects.items():
        if n.startswith("~"):
            seg(x, y, x, y + h - 1)
            continue
        if not boxes:
            continue
        seg(x, y, x + w - 1, y)
        seg(x, y + h - 1, x + w - 1, y + h - 1)
        seg(x, y, x, y + h - 1)
        seg(x + w - 1, y, x + w - 1, y + h - 1)
        for i, c in enumerate(n):
            text[(x + (w - len(n)) // 2 + i, y + 1)] = c

    arrows = {}
    for s, t in split:
        sx, sy, sw, sh = rects[s]
        tx, ty, tw, th = rects[t]
        x0, x1 = xs_out[bundle[(s, t)]], xs_in[(s, t)]
        bottom = sy + sh - 1
        top = ty
        if t.startswith("~"):
            x1 = tx
        ends = heads[chain[(s, t)]]
        arrive = t.startswith("~") or "down" in ends
        # Without an arrowhead, an edge runs on into the target's border to join it as a tee.
        end = top - 1 if arrive else top
        if x0 == x1:
            seg(x0, bottom, x0, end)
        else:
            ty_track = bottom + 1 + tracks[bundle[(s, t)]] + 1
            seg(x0, bottom, x0, ty_track)
            seg(x0, ty_track, x1, ty_track)
            seg(x1, ty_track, x1, end)
        if not t.startswith("~") and "down" in ends:
            arrows[(x1, top - 1)] = "▼"
        if not s.startswith("~") and "up" in ends:
            arrows[(x0, bottom + 1)] = "▲"
        if not boxes:
            # Without boxes to merge with, a cell where an edge meets a box carries the border it sits on,
            # so it reads as a tee.
            if not s.startswith("~"):
                bits[(x0, bottom)] |= L | R
            if not arrive:
                bits[(x1, top)] |= L | R

    cells = {p: GLYPH[b] for p, b in bits.items() if b} | text | arrows
    real = {n: r for n, r in rects.items() if not n.startswith("~")}
    return real, width, height, cells


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "request"
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    print(render(*GRAPHS[name], width))
```

### Drop shadows

Save it as `cw_shadows.py` beside `layered.py` and run it from this repository:
`uv run python cw_shadows.py`.
It renders the shadow swatches and both diagrams headless,
and writes each render beside itself as `.txt` and `.svg`.

```python
"""
Throwaway probe: drop shadows as an outer Div with right and bottom borders contracted by one cell,
on their own and on the nodes of a diagram laid out by `layered.py`, rendered headless by counterweight.

Run from the counterweight repo with `layered.py` beside it: `uv run python cw_shadows.py`.
It writes each render beside itself as `.txt` and `.svg`.
"""

import asyncio
import functools
import sys
from pathlib import Path

from counterweight import app
from counterweight.components import Component, component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.paint import Frame
from counterweight.styles import Style
from counterweight.styles.utilities import *

import layered

OUT = Path(__file__).parent


def drop_shadow(kind: Style, color: Style) -> Style:
    """A wrapper style that draws a shadow one cell right of and one cell below its child, as its own borders."""
    return border_right | border_bottom | kind | border_contract(1) | color


@component
def swatches() -> Div:
    kinds = {
        "border_lightshade": border_lightshade,
        "border_mediumshade": border_mediumshade,
        "border_heavyshade": border_heavyshade,
        "border_thick": border_thick,
    }
    return Div(
        style=row | gap(3) | pad(1) | align_children_start,
        children=[
            Div(
                style=drop_shadow(kind, border_color("slate", 600)),
                children=[Text(content=name, style=border | border_lightrounded | pad_x(1))],
            )
            for name, kind in kinds.items()
        ],
    )


GAP = 3  # One more cell between neighbours than the plain diagram, for the shadow.


@component
def diagram(graph: str, columns: int, shadow: Style, node: Style, tee: str) -> Div:
    """
    The prototype's layout drawn with counterweight elements: shadowed nodes placed absolutely,
    with the edges as runs of text above both.
    Edges touch a node only at the border cell they leave from, which the router draws as a tee
    (`tee`, to match the node's border weight), because border healing only joins corners.
    """
    rects, _, _, cells = layered.draw(*layered.GRAPHS[graph], columns, gap=GAP, boxes=False)
    exits = {(x, y + h - 1) for x0, y, w, h in rects.values() for x in range(x0, x0 + w)}
    cells = {p: tee if p in exits and c == "┬" else c for p, c in cells.items()}
    nodes = [
        Div(
            style=position_absolute | inset_left(x) | inset_top(y) | shadow | z(0),
            children=[Text(content=name, style=border | node | width(w) | text_justify_center | z(2))],
        )
        for name, (x, y, w, h) in rects.items()
    ]
    runs = []
    for y in sorted({y for _, y in cells}):
        xs = sorted(x for x, cy in cells if cy == y)
        start = previous = xs[0]
        for x in [*xs[1:], None]:
            if x == previous + 1:
                previous = x
                continue
            runs.append(
                Text(
                    content="".join(cells[(c, y)] for c in range(start, previous + 1)),
                    style=position_absolute | inset_left(start) | inset_top(y) | text_color("sky", 400) | z(3),
                )
            )
            if x is not None:
                start = previous = x
    return Div(children=[*runs, *nodes])


def save(name: str, frame: Frame) -> None:
    (OUT / f"{name}.txt").write_text(frame.text(ansi=False) + "\n")
    (OUT / f"{name}.svg").write_text(frame.svg() + "\n")


async def shoot(root: Component, name: str, dimensions: tuple[int, int]) -> None:
    await app(
        root,
        headless=True,
        dimensions=dimensions,
        autopilot=[Screenshot(handler=functools.partial(save, name)), Quit()],
    )


STYLES = {
    # The slides in JoshKarpel/python-concurrency-and-parallelism: light-shade shadows behind heavy borders.
    "slides": (
        drop_shadow(border_lightshade, border_color("gray", 400)),
        border_heavy | border_color("gray", 200),
        "┯",
    ),
    "thick": (drop_shadow(border_thick, border_color("slate", 500)), border_lightrounded, "┬"),
}


async def main() -> None:
    await shoot(swatches(), "swatches", (100, 6))
    for graph, columns in [("request", 44), ("ci", 90)]:
        _, columns, height, _ = layered.draw(*layered.GRAPHS[graph], columns, gap=GAP)
        for name, (shadow, node, tee) in STYLES.items():
            await shoot(diagram(graph, columns, shadow, node, tee), f"{graph}-{name}", (columns, height + 1))


if __name__ == "__main__":
    asyncio.run(main())
    for name in ["swatches", "request-slides"]:
        sys.stdout.write(f"== {name}\n" + (OUT / f"{name}.txt").read_text())
```
