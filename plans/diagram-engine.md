# Plan: Diagram Engine

This plan covers laying out boxes and arrows in the terminal,
the way dot lays out graphs for SVG,
with taffy (through waxy) still doing the box layout.
It covers how a diagram engine splits into separable features,
where placement plugs into the render loop,
a working prototype and what it established,
and the prior art it draws on.
It does not settle the public API,
and its implementation steps depend on the open questions at the end.

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

A request pipeline at 44 columns:

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

A CI pipeline at 80 columns, with a wide fan-out and fan-in:

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

A job queue at 44 columns, with cycles.
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
  the same direction-bits idea `border_healing.py` uses.

Known weaknesses:

- Crowded targets: arrowheads two cells apart push edges off their straight line,
  so they kink just above a busy box (`publish` above),
  and a box with more inputs than its label is wide grows (`ok` above).
  Taking edges on a box's sides would avoid both.
- Long horizontal runs: `publish` to `deploy docs` runs a long way right,
  because the long edge from `build docs` holds the right-hand column.
  Better ordering heuristics would help.
- Off-center exits: an edge can leave a box off-center (`db`, `render`)
  when that keeps it straight.
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
The cost is in waxy:
it becomes a `LayoutPartialTree` implementor,
and Python calling back into Rust to lay out a child,
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
When focus moves, `app.py` re-renders the components whose focus changed and lays the tree out again,
all before painting, and raises `UnsettledFocus` if the second pass doesn't settle.
A graph container can follow it: lay out, run the core on the measured sizes,
re-render the container with its positions, and lay out again, at the cost of a second layout pass.
`LayoutTree` keeps one taffy tree across frames so taffy reuses the layouts it cached
for unchanged nodes.
Measuring nodes inside that tree at sizes other than the ones the final layout gives them
may evict those entries, or a scratch tree may be cheaper; that needs measuring with `just profile`.

### Recommendation

C, with the graph core written as pure functions
(graph and node sizes in, positions and routes out),
and the measuring done inside the frame.
B is where that core moves if counterweight wants custom layouts in general.
A is ruled out: it skips coordinate assignment.

## Routing

Connectors between any two elements, drawn after layout, work in every layout mode.
That is the piece the editor case needs most.

- Where it runs: a pass after layout that reads `Layouts.by_key`,
  as border healing reads the paint.
  It needs a module name other than `routing`:
  `counterweight.routing` routes input events to handlers.
- Clipping and scrolling: `by_key` holds each node's rects on screen, already moved by the scroll containers above it,
  with its `clip` and `visible` region, and has no entry for a hidden node.
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
- An edge leaves through the shadow row below its box,
  so edges draw above shadows and cut through them (`░░│░░`).
- Healing joins only corners, so the probe draws each exit tee itself,
  matched to the border's weight (`┯`).

## Fitting the screen and staying put

Counterweight's text measurement already wraps a label at a given width,
so the engine can narrow a box by choosing the width it measures that node at,
before coordinate assignment.
Boxes must not shrink during layout itself:
taffy's default `flex_shrink` squeezes them below the size the router drew around,
which is why the probe's nodes don't shrink.
On top of narrowing boxes, the engine can shrink gaps
(mermaid-ascii's `--max-width` and termaid's auto-fit both do)
and flip direction from down to right by aspect ratio.
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
- Caching: key the layout on graph structure plus node sizes,
  as text measurement is cached.

Parsing a subset of Mermaid's flowchart syntax splits the work cleanly for LLM output:
the model writes the nodes and edges, and the engine lays them out.

## Open questions

1. Which comes first:
   routing between arbitrary elements (editor first),
   or the graph container (diagrams first)?
   Routing first is the better default, since the graph container uses it too,
   and `ElementHandle` already names its endpoints.
2. Can edges cross container boundaries,
   as in nested diagrams with edges between their insides?
   Every engine below struggles there;
   ruling it out at first keeps the core simple.
3. Is a custom display mode in waxy on the table?
   That decides whether placement ends up inside taffy's pass (B)
   or stays a measure-then-place step (C).

## Proposed steps

These depend on the open questions; the order assumes routing first.

1. Line canvas: per-cell direction bits with a weight per direction,
   resolved to glyphs at paint time, with node borders protected and clips respected.
   Border healing moves onto it, healing along whole edges rather than only corners.
2. Connectors: a post-layout pass between elements named by `ElementHandle`,
   with A* using bend and soft-obstacle costs, port spreading, and arrowheads,
   then ordering and nudging in shared channels,
   and a rule for endpoints that are scrolled away, clipped, or hidden.
3. Graph core: pure functions for cycle breaking, ranking, ordering, coordinate assignment,
   ports, and channel tracks, tested directly on plain data.
   Each takes its spacing (the gap between neighbours) as an argument.
   Tests cover cycles, sinks above the last rank, isolated nodes,
   and boxes with more inputs than their label is wide.
4. Graph container: measure nodes, run the core,
   compile positions into the taffy tree, and route through step 2's channels,
   with a second layout pass in the frame, as focus settling already does.
5. Fitting: narrow boxes, shrink gaps, then flip direction, when the diagram doesn't fit.
6. Drop shadows: document the wrapper pattern (a cookbook page),
   and have the graph container leave room for a node's shadow by passing a wider gap to the core.
7. Mermaid subset: flowchart syntax parsed into the graph container,
   with nodes declared by the edges that name them.
   Self-loops need routing around a box's side before they can be accepted.

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
        ["checkout", "lint", "typecheck", "unit tests", "build wheel", "build docs", "integration", "publish", "deploy docs"],
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
    U | D: "│", L | R: "─", D | R: "╭", D | L: "╮", U | R: "╰", U | L: "╯",
    U | D | R: "├", U | D | L: "┤", D | L | R: "┬", U | L | R: "┴", U | D | L | R: "┼",
    U: "│", D: "│", L: "─", R: "─",
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

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.output import Frame
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
