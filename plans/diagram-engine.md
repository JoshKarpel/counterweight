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

- Ranking and ordering: longest-path ranks, then barycenter ordering over four sweeps.
  Long edges pass through 1-cell dummy nodes.
- Coordinate assignment: each node is pulled toward the nodes it connects to,
  minimizing the total horizontal distance along edges
  while keeping each rank's order and a 2-cell gap.
  Edges are weighted 1, 2, or 8 by how many of their ends are dummies, as dot does,
  so long edges straighten first.
  Each rank is solved exactly with pool-adjacent-violators over weighted medians,
  in alternating sweeps.
- Layout: the ranks compile into a waxy tree, a column of flex rows.
  Each node's left margin moves it to its assigned x,
  and fixed-height spacers between rows hold the edge channels.
- Ports: an edge arrives where it already is if that's over the target's interior,
  with arrowheads two cells apart.
  A source with one outgoing edge leaves from wherever that edge lands.
- Channel tracks: each source's outgoing edges share one horizontal track.
  An edge whose run passes another edge's source column must sit below it,
  and one that passes another's arrival column must sit above it.
  Tracks are assigned in that order,
  which avoids every crossing that stacking can avoid.
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
- Edges merge into node borders as `┬` and `┴`,
  the same direction-bits idea `border_healing.py` uses.

Known weaknesses:

- Crowded targets: a narrow box with many inputs forces small kinks (`publish` above).
  A node could grow to fit its ports, or take edges on its sides.
- Long horizontal runs: `publish` to `deploy docs` runs a long way right,
  because the long edge from `build docs` holds the right-hand column.
  Better ordering heuristics would help.
- Off-center exits: an edge can leave a box off-center (`db`, `render`)
  when that keeps it straight.

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
- Path search: A* over cells, scored by length plus a penalty per bend.
  Earlier edges are soft obstacles (termaid charges +2 per cell),
  so later edges avoid them without being blocked.
- Shared channels: Wybrow, Marriott and Stuckey's ordering and nudging,
  so parallel edges never overlap.
  Overlapping edges are mermaid-ascii's most-complained-about flaw.
- Ports: spread edges that land on the same side of a box,
  and leave a straight run before each arrowhead.
- Naming endpoints (open): inside a graph container,
  ids local to that container are simple.
  Connectors anywhere in the tree need an element-reference mechanism
  counterweight doesn't have; a hook like `use_anchor()` is one possible shape.

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

Taffy already wraps node text into narrower boxes.
On top of that, the engine can shrink gaps
(mermaid-ascii's `--max-width` and termaid's auto-fit both do)
and flip direction from down to right by aspect ratio.

Stability matters for an editor and for reactive re-renders alike:

- No randomness.
  TALA tries three seeds and keeps the best,
  and says "adding one node can change the whole diagram".
- Input order breaks ties,
  a lesson from ELK's retrospective, where users said drawings change unexpectedly.
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
   Routing first is the better default, since the graph container uses it too.
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
   resolved to glyphs at paint time, with node borders protected.
   Border healing moves onto it, healing along whole edges rather than only corners.
2. Connectors: a post-layout routing pass,
   with A* using bend and soft-obstacle costs, port spreading, and arrowheads,
   then ordering and nudging in shared channels.
3. Graph core: pure functions for ranking, ordering, coordinate assignment,
   ports, and channel tracks, tested directly on plain data.
4. Graph container: measure nodes, run the core,
   compile positions into the taffy tree, and route through step 2's channels.
5. Fitting: shrink gaps, then flip direction, when the diagram doesn't fit.
6. Drop shadows: document the wrapper pattern (a cookbook page),
   and have the graph container leave room for a node's shadow.
7. Mermaid subset: flowchart syntax parsed into the graph container.

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
It takes a graph name (`request` or `ci`) and an available width.

```python
"""
Throwaway probe of a layered (Sugiyama-style) diagram engine for counterweight.

Ranks, orders and x-coordinates are computed in Python, compiled into a waxy/taffy tree of flex rows
(each node pushed to its x by a left margin, channel spacers between rows), laid out by taffy,
then edges are routed in the inter-rank channels and drawn with box-drawing characters.

Run from the counterweight repo, which provides waxy: `uv run python layered.py [request|ci] [width]`.
"""

import sys
from collections import defaultdict

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
}


def layers(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering."""
    preds = defaultdict(list)
    for s, t in edges:
        preds[t].append(s)
    rank: dict[str, int] = {}

    def r(n: str) -> int:
        if n not in rank:
            rank[n] = 1 + max((r(p) for p in preds[n]), default=-1)
        return rank[n]

    for n in nodes:
        r(n)
    return rank


def add_dummies(nodes, edges, rank):
    """Split edges spanning several ranks into chains through 1-cell-wide dummy nodes."""
    nodes = list(nodes)
    rank = dict(rank)
    out = []
    for s, t in edges:
        prev = s
        for k in range(rank[s] + 1, rank[t]):
            d = f"~{s}>{t}#{k}"
            nodes.append(d)
            rank[d] = k
            out.append((prev, d))
            prev = d
        out.append((prev, t))
    return nodes, out, rank


def order(nodes, edges, rank, sweeps=4):
    """Barycenter crossing reduction, alternating down and up sweeps."""
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

            def bary(n):
                ps = [pos[p] for p in nbrs[n] if p in pos]
                return sum(ps) / len(ps) if ps else by_rank[r].index(n)

            by_rank[r].sort(key=bary)
    return [by_rank[r] for r in range(depth)]


def channel_tracks(ranked, edges, xs_out, xs_in):
    """
    One horizontal track per source bundle in each inter-rank gap, stacked so bundles don't cross where
    stacking can prevent it, and packed so bundles that don't overlap share a track.
    Returns each bundle's track and each gap's track count.
    """
    tracks = {}
    heights = []
    rank_of = {n: r for r, ns in enumerate(ranked) for n in ns}
    for r in range(len(ranked) - 1):
        bundles = defaultdict(list)
        for s, t in edges:
            if rank_of[s] == r:
                bundles[s].append(t)
        nets = {}
        for s, ts in bundles.items():
            bottoms = [xs_in[(s, t)] for t in ts]
            xs = [xs_out[s], *bottoms]
            if min(xs) != max(xs):
                nets[s] = (min(xs), max(xs), xs_out[s], bottoms)

        # A net whose horizontal run passes another's source column must sit below it,
        # and one that passes another's arrival column must sit above it; otherwise they cross.
        above = defaultdict(set)
        for a, (alo, ahi, _, _) in nets.items():
            for b, (_, _, btop, bbottoms) in nets.items():
                if a == b:
                    continue
                if alo <= btop <= ahi:
                    above[b].add(a)
                if any(alo <= x <= ahi for x in bbottoms):
                    above[a].add(b)
        for a in nets:  # Contradictory pairs cross whatever we do, so drop both constraints.
            for b in list(above[a]):
                if a in above[b]:
                    above[a].discard(b)
                    above[b].discard(a)

        placed: dict[int, list[tuple[int, int]]] = defaultdict(list)
        remaining = set(nets)
        while remaining:
            ready = [n for n in remaining if not any(p in remaining for p in parents(above, n))]
            # A longer cycle can't be satisfied either; break it at the leftmost net.
            n = min(ready or remaining, key=lambda n: nets[n][:2])
            remaining.discard(n)
            lo, hi = nets[n][:2]
            k = 1 + max((tracks[p] for p in parents(above, n) if p in tracks), default=-1)
            while any(not (hi < plo - 1 or lo > phi + 1) for plo, phi in placed[k]):
                k += 1
            tracks[n] = k
            placed[k].append((lo, hi))
        heights.append(1 + max(placed, default=-1))
    return tracks, heights


def parents(above, n):
    """The nets that must sit above `n`."""
    return [p for p, below in above.items() if n in below]


GAP = 2


def size(n):
    return (1, 3) if n.startswith("~") else (len(n) + 4, 3)


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


def place_rank(ns, targets):
    """
    Left x for each node of one rank, minimizing the weighted distance of each node's center from its targets
    subject to keeping the rank's order with at least GAP between neighbours:
    pool-adjacent-violators with weighted medians, which is exact for this L1 objective.
    """
    blocks = []  # [members [(node, offset)], extent, points [(value, weight)], pos]
    for n in ns:
        w = size(n)[0]
        points = [(c - w // 2, wt) for c, wt in targets[n]]
        block = [[(n, 0)], w, points, weighted_median(points)]
        blocks.append(block)
        while len(blocks) > 1 and blocks[-2][3] + blocks[-2][1] + GAP > blocks[-1][3]:
            b2 = blocks.pop()
            b1 = blocks.pop()
            shift = b1[1] + GAP
            members = b1[0] + [(m, off + shift) for m, off in b2[0]]
            points = b1[2] + [(v - shift, wt) for v, wt in b2[2]]
            blocks.append([members, shift + b2[1], points, weighted_median(points)])
    return {m: b[3] + off for b in blocks for m, off in b[0]}


def assign_x(ranked, edges):
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
            x += size(n)[0] + GAP

    def center(n):
        return xs[n] + size(n)[0] // 2

    for sweep in range(12):
        down = sweep % 2 == 0
        order_ = ranked if down else ranked[::-1]
        for ns in order_:
            targets = {}
            for n in ns:
                use = [(center(m), wt) for m, wt, side in nbrs[n] if sweep >= 2 or side == ("up" if down else "down")]
                targets[n] = use or [(center(n), 0.01)]
            xs.update(place_rank(ns, targets))
    lo = min(xs.values())
    return {n: x - lo for n, x in xs.items()}


def layout(ranked, edges, width, channel_heights):
    """
    Lay out the ranks as a column of flex rows with fixed-height channel spacers between them,
    each node pushed to its assigned x by its left margin, centred as a whole in `width`.
    """
    xs = assign_x(ranked, edges)
    extent = max(xs[n] + size(n)[0] for n in xs)
    xs = {n: x + max(0, (width - extent) // 2) for n, x in xs.items()}
    tree = waxy.TaffyTree()
    ids = {}
    rows = []
    for r, ns in enumerate(ranked):
        kids = []
        right = 0
        for n in ns:
            w, h = size(n)
            ids[n] = tree.new_leaf(
                waxy.Style(
                    size_width=waxy.Length(w), size_height=waxy.Length(h), margin_left=waxy.Length(xs[n] - right)
                )
            )
            right = xs[n] + w
            kids.append(ids[n])
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
    rects = {}
    for node, pos, lay in tree.absolute_layouts(root):
        for n, i in ids.items():
            if i == node:
                rects[n] = (int(pos.x), int(pos.y), int(lay.size.width), int(lay.size.height))
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
    _, height, cells = draw(nodes, edges, width)
    return "\n".join("".join(cells.get((x, y), " ") for x in range(width)).rstrip() for y in range(height))


def draw(nodes, edges, width, boxes=True):
    """
    Each real node's rect, the drawing's height, and its non-blank cells by position:
    edges and arrowheads, plus boxes and labels if `boxes`.
    """
    rank = layers(nodes, edges)
    all_nodes, split, rank = add_dummies(nodes, edges, rank)
    ranked = order(all_nodes, split, rank)

    # Pass 1 with zero-height channels just to learn x positions (channel heights only change y).
    rects, _ = layout(ranked, split, width, [0] * (len(ranked) - 1))
    xs_out = {n: x + w // 2 for n, (x, y, w, h) in rects.items()}
    incoming = defaultdict(list)
    for s, t in split:
        incoming[t].append(s)
    xs_in = {}
    for t, ss in incoming.items():
        x, _, w, _ = rects[t]
        ss = sorted(ss, key=lambda s: xs_out[s])
        if len(ss) == 1 or w < 3:
            for s in ss:
                xs_in[(s, t)] = x + w // 2
            continue
        # Land each edge where it already is when that's over the box, two cells apart so arrowheads don't touch,
        # pushing right and then back left to stay within the box's interior.
        lo, hi = x + 1, x + w - 2
        ports = [min(max(xs_out[s], lo), hi) for s in ss]
        for k in range(1, len(ports)):
            ports[k] = max(ports[k], ports[k - 1] + 2)
        ports[-1] = min(ports[-1], hi)
        for k in range(len(ports) - 2, -1, -1):
            ports[k] = min(ports[k], ports[k + 1] - 2)
        for s, p in zip(ss, ports):
            xs_in[(s, t)] = p
    outgoing = defaultdict(list)
    for s, t in split:
        outgoing[s].append(t)
    for s, t in split:
        if len(outgoing[s]) != 1 or len(incoming[t]) != 1:
            continue
        sx, _, sw, _ = rects[s]
        tx, _, tw, _ = rects[t]
        (slo, shi), (tlo, thi) = interior(sx, sw), interior(tx, tw)
        lo, hi = max(slo, tlo), min(shi, thi)
        if lo <= hi:
            x = xs_out[s] if lo <= xs_out[s] <= hi else xs_in[(s, t)] if lo <= xs_in[(s, t)] <= hi else (lo + hi) // 2
            xs_out[s] = xs_in[(s, t)] = x
    # A source with one outgoing edge can leave from wherever that edge lands, if that's over its own interior.
    for s, (t,) in ((s, ts) for s, ts in outgoing.items() if len(ts) == 1):
        sx, _, sw, _ = rects[s]
        if sw >= 3 and sx + 1 <= xs_in[(s, t)] <= sx + sw - 2:
            xs_out[s] = xs_in[(s, t)]
    tracks, heights = channel_tracks(ranked, split, xs_out, xs_in)
    rects, height = layout(ranked, split, width, heights)

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
            text[(x + 2 + i, y + 1)] = c

    arrows = {}
    for s, t in split:
        sx, sy, sw, sh = rects[s]
        tx, ty, tw, th = rects[t]
        x0, x1 = xs_out[s], xs_in[(s, t)]
        bottom = sy + sh - 1
        top = ty
        if t.startswith("~"):
            x1 = tx
        if x0 == x1:
            seg(x0, bottom, x0, top - 1)
        else:
            ty_track = bottom + 1 + tracks[s] + 1
            seg(x0, bottom, x0, ty_track)
            seg(x0, ty_track, x1, ty_track)
            seg(x1, ty_track, x1, top - 1)
        if not t.startswith("~"):
            arrows[(x1, top - 1)] = "▼"
        if not boxes and not s.startswith("~"):
            # Without boxes to merge with, the exit cell carries the border it sits on, so it reads as a tee.
            bits[(x0, bottom)] |= L | R

    cells = {p: GLYPH[b] for p, b in bits.items() if b} | text | arrows
    real = {n: r for n, r in rects.items() if not n.startswith("~")}
    return real, height, cells


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


@component
def diagram(graph: str, width: int, shadow: Style, node: Style, tee: str) -> Div:
    """
    The prototype's layout drawn with counterweight elements: shadowed nodes placed absolutely,
    with the edges as runs of text above both.
    Edges touch a node only at the border cell they leave from, which the router draws as a tee
    (`tee`, to match the node's border weight), because border healing only joins corners.
    """
    rects, _, cells = layered.draw(*layered.GRAPHS[graph], width, boxes=False)
    exits = {(x, y + h - 1) for x0, y, w, h in rects.values() for x in range(x0, x0 + w)}
    cells = {p: tee if p in exits and c == "┬" else c for p, c in cells.items()}
    nodes = [
        Div(
            style=position_absolute | inset_left(x) | inset_top(y) | shadow | z(0),
            children=[Text(content=name, style=border | node | pad_x(1) | z(2))],
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
    layered.GAP = 3  # One more cell between neighbours, for the shadow.
    for graph, width in [("request", 44), ("ci", 90)]:
        _, height, _ = layered.draw(*layered.GRAPHS[graph], width)
        for name, (shadow, node, tee) in STYLES.items():
            await shoot(diagram(graph, width, shadow, node, tee), f"{graph}-{name}", (width, height + 1))


if __name__ == "__main__":
    asyncio.run(main())
    for name in ["swatches", "request-slides"]:
        sys.stdout.write(f"== {name}\n" + (OUT / f"{name}.txt").read_text())
```
