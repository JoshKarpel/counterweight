# Plan: Gradients

Artifact: https://claude.ai/code/artifact/b3846a59-18f1-42a5-ac9a-30a30be6abc0

This plan adds linear, radial and conic gradients
to every place a counterweight element paints a color:
its margin, padding and content backgrounds,
its border's foreground and background,
and its text's foreground and background.
It takes its geometry from CSS Images 4,
and says where cells change the answer.

It doesn't cover transparency or layering gradients over what's beneath them
(`Color` has no alpha), gradients inside a `Canvas` painter,
or Tailwind's `from-*`/`via-*`/`to-*` composition (see [Deferred](#deferred)).

## Where the old branch went wrong

[PR #132](https://github.com/JoshKarpel/counterweight/pull/132) made
`ColorLike = Color | LinearGradient`, gave both an `at(position, rect)`,
and had paint ask every cell for its color:
a `dict[Position, P]` per element,
with a fresh `CellStyle` merged for each cell,
and `Color.blend` cached on a rounded ratio to save the hit rate.
Two things made that slow, and neither is a property of gradients:

- **Paint was per cell.**
  Today's paint is row-based:
  `Paint` is a flat `list[Cell]`, `fill` assigns row slices,
  and `Cell` and `ResolvedCellStyle` are flyweights compared by identity.
- **Nothing was reused across frames.**
  A gradient is relative to its box,
  so its colors depend on the gradient and the box's size, not its position.
  Moving or scrolling an element doesn't change them.

## How the web does it

A CSS gradient is an `<image>`, not a `<color>`:
`background-image`, `border-image` and `mask-image` take one,
and `color` doesn't (gradient text is `background-clip: text` over transparent text).
SVG is closer to counterweight:
`fill` and `stroke` take a color or a paint server (`url(#gradient)`),
and a `<linearGradient>` maps over the shape's bounding box by default.
Jetpack Compose's `Brush` is the same idea as a value:
`Modifier.background(brush)`, `Modifier.border(width, brush)`
and `TextStyle(brush = ...)` each take a solid color or a gradient.

The CSS geometry this plan uses:

- **Linear.**
  `0deg` points up and angles turn clockwise (`90deg` is `to right`).
  The gradient line passes through the box's center,
  and its length is `abs(W * sin A) + abs(H * cos A)`,
  so the 0% and 100% points are where perpendiculars through the corners cross it.
  `to top right` and the other corners use "magic corners":
  the angle that puts the 50% line through the other two corners,
  so the named corner gets exactly the last color whatever the box's shape.
  The default is `to bottom` (`180deg`).
- **Radial.**
  `radial-gradient([circle | ellipse] [size] [at position], stops)`,
  defaulting to `ellipse farthest-corner at center`.
  `size` is a keyword (`closest-side`, `closest-corner`, `farthest-side`, `farthest-corner`)
  or explicit radii (one for a circle, two for an ellipse).
  An ellipse sized to a corner keeps the aspect ratio the matching side keyword would give it.
- **Conic.**
  `conic-gradient(from <angle> at <position>, stops)`:
  `from` defaults to `0deg` (up), angles run clockwise, and `at` defaults to `center`.
- **Stops.**
  A stop without a position is fixed up:
  the first is 0%, the last is 100%,
  a position smaller than one before it is raised to the largest before it,
  and runs without positions are spaced evenly between their neighbors.
  Before the first stop and after the last, the end colors extend.
  A bare position between two stops is a transition hint,
  which moves the midpoint: at fraction `P` between the stops, with the hint at `H`,
  the weight of the second color is `P ** log(0.5, H)`.
- **Repeating.**
  `repeating-*-gradient` repeats the stop list every `last - first`.
- **Interpolation.**
  CSS Images 4 adds `in <color-space>` (`in oklab`, `in oklch longer hue`, ...),
  and the default interpolation space is Oklab.
  CSS Color 4 keeps sRGB for gradients whose colors are all legacy syntax (`#hex`, `rgb()`),
  which is why `linear-gradient(red, blue)` still looks the way it always did.

Prior art in terminals:
Textual's `LinearGradient` renderable doubles `y` to correct for the cell's aspect ratio,
and draws each cell as `▀` so a cell shows two samples, one in its foreground and one in its background.

## What cells change

### The aspect ratio of a cell

A cell is about twice as tall as it is wide.
CSS works in square pixels, so `45deg` in a box of cells,
computed in cell units, runs one column across for each row down,
which looks like 27 degrees from vertical,
and a `circle` is drawn as an ellipse twice as tall as it is wide.
Not everything is affected:
side and corner keywords, and an `ellipse` sized by a keyword, are relative to the box,
and an affine map stays the same under scaling an axis,
so they look the same in either unit.
Only angles (`linear` and `conic`) and circles depend on it.

Gradients compute in **visual units**:
a row is `cell_aspect_ratio` columns tall, 2 by default.
The ratio is a value passed into paint (from a parameter of `app()`),
since the right one depends on the user's font.
A terminal can report its cell size in pixels (`CSI 16 t`),
which could replace the default later (see [Deferred](#deferred)).
Explicit lengths stay per axis in cells:
a `circle` of radius 10 reaches 10 columns left and right of its center and 5 rows up and down,
and an ellipse's two radii are columns and rows.

### Where a cell samples

A browser samples each pixel at its center,
which is invisible at thousands of pixels and obvious at a few cells.
A three-row vertical gradient sampled at cell centers
shows 17%, 50% and 83% and neither end color,
and a red-to-blue border never draws a red or blue corner.

So the **gradient box spans cell centers**:
from the center of a box's first cell to the center of its last, on each axis.
The corner cells get exactly the 0% and 100% colors,
and the interior divides evenly between them,
as Textual's `VerticalGradient` does (`y / (height - 1)`).
A one-cell axis has no span and samples at its center.

### Which box a slot maps over

CSS maps a background over the padding box (`background-origin`),
paints it over the border box (`background-clip`),
and repeats it over the border, where the two differ.
`border-image` maps over the border box.
Counterweight's slots each paint one region,
so each maps its gradient over the box it paints:

| Slot | Paints | Maps over |
| --- | --- | --- |
| `margin_color` | the margin, outside the border box | the margin box |
| `content_color` | the border box, under the border and padding | the border box |
| `padding_color` | the padding, inside the border | the padding box |
| `border_style` foreground and background | the border | the border box |
| `text_style` and a chunk's foreground and background | the text | the content box |

A gradient's `box` field overrides this, as `background-origin` does,
so a border and a background with the same stops can share one box and line up.
Text overflows its content box down and to the right, and the end colors extend there.

A chunk's gradient maps over the element's content box too.
CSS maps a `<span>`'s background over the span's own box,
but a chunk has no box, and a wrapped one has several.
Mapping every chunk over the same box makes a chunk's gradient
continue the element's, which is what a highlighted word in gradient text wants.

## The API

```python
type Gradient = LinearGradient | RadialGradient | ConicGradient
type Interpolation = Literal["srgb", "oklab", "oklch"]
type HueMethod = Literal["shorter", "longer", "increasing", "decreasing"]
type Box = Literal["margin", "border", "padding", "content"]
type At = float | waxy.Length  # a fraction of the gradient line, or a number of cells


@dataclass(frozen=True, slots=True)
class Stop:
    color: Color
    at: At | None = None


@dataclass(frozen=True, slots=True)
class Hint:
    at: At


type Stops = tuple[Stop | Hint, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class LinearGradient:
    stops: Stops
    direction: float | SideOrCorner = "bottom"  # degrees, or "right", "top right", ...
    repeating: bool = False
    interpolation: Interpolation = "oklab"
    hue: HueMethod = "shorter"
    box: Box | None = None  # None: the box the slot paints


@dataclass(frozen=True, slots=True, kw_only=True)
class RadialGradient:
    stops: Stops
    shape: Literal["circle", "ellipse"] = "ellipse"
    size: Extent | waxy.Length | tuple[waxy.Length, waxy.Length] = "farthest-corner"
    at: tuple[At, At] = (0.5, 0.5)
    repeating: bool = False
    interpolation: Interpolation = "oklab"
    hue: HueMethod = "shorter"
    box: Box | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConicGradient:
    stops: Stops  # positions are fractions of a turn
    start: float = 0  # CSS's `from`, in degrees
    at: tuple[At, At] = (0.5, 0.5)
    repeating: bool = False
    interpolation: Interpolation = "oklab"
    hue: HueMethod = "shorter"
    box: Box | None = None
```

Functions build them the way CSS spells them,
taking a bare `Color` as a stop without a position and a `(Color, at)` pair as one with:

```python
linear_gradient(red_500, blue_500, to="right")
linear_gradient(red_500, (amber_400, 0.3), blue_500, angle=45, interpolation="oklch")
radial_gradient(white, sky_700, shape="circle", at=(0.25, 0.5))
conic_gradient(red_500, amber_400, green_500, blue_500, red_500, start=90)
```

Hints are `Hint(0.3)` among the stops.
The constructors parse once:
they fix up stop positions into a resolved form the painter reads,
and raise `ValueError` for fewer than two color stops
or a hint that isn't between two of them.
Every field is hashable, so a `Style` holding a gradient hashes and caches as it does today,
and `|` replaces a gradient whole rather than merging its fields.

The slots widen from `Color` to `Color | Gradient`:
`Style.margin_color`, `padding_color` and `content_color`,
and `CellStyle.foreground` and `background`,
which `text_style`, `border_style` and chunks share.
`ResolvedCellStyle`, which output reads, stays `Color`-only:
paint turns a gradient into each cell's color before anything reaches output.

Hand-written utilities give every slot a gradient helper,
beside the existing `text_color`, `border_bg` and the rest:
`text_gradient`, `text_bg_gradient`, `border_gradient`, `border_bg_gradient`,
`margin_gradient`, `padding_gradient` and `content_gradient`,
each taking a `Gradient`.

## Painting

### Ramps and fields

A gradient splits into two parts that change for different reasons,
and each is computed once and reused:

- **The ramp** maps a position along the gradient to a color.
  It depends only on the stops, `repeating` and the interpolation,
  so it's a lookup table of colors (256 entries per pair of adjacent stops to start),
  built once per gradient value with the color math, hints and color-space conversion.
- **The field** maps each cell of a box to an index into the ramp.
  It depends on the geometry (direction, shape, size, `at`),
  the box's size in cells, and the cell aspect ratio,
  but not on the colors or the box's position.

A slot's cells are then a lookup: the ramp's colors made into `Cell`s for that slot
(`Cell.blank(color)` for a background, or the border character or text grapheme in a style
whose foreground or background is the ramp's color),
indexed by the field.
Only the rows inside the clip are built, as text's are,
so a gradient behind a long scroll container costs only the rows in view.

A linear field is cheap to build row by row:
the position along the gradient is affine in `x` and `y`,
so each row is a start and a step.
Radial and conic fields need a square root or an `atan2` per cell.

The ramp also bounds how many distinct styles a gradient makes,
which matters to the shared flyweight caches
(`Cell` holds 2**14, `ResolvedCellStyle` and `sgr_from_cell_style` 2**10):
a 200x50 box at 30 degrees has 400 distinct colors computed exactly,
and never more than the ramp's entries through it.

### What a probe measured

A throwaway probe painted a two-stop linear gradient at 30 degrees
over a 200x50 box with today's `Paint`, on this machine:

| Step | Time or size |
| --- | --- |
| field, blending each cell's color directly | 15.6 ms |
| field, indexing a 256-entry ramp of `Cell`s | 1.6 ms |
| writing the prebuilt rows into the paint | 0.04 ms |
| a solid `fill` of the same box, for comparison | 0.06 ms |
| full-frame output, solid | 10 KiB, 0.5 ms |
| full-frame output, gradient | 269 KiB, 3.4 ms |
| full-frame output, gradient, re-sending only changed colors | 125 KiB |
| diffing the gradient against itself rotated a degree | 3.6 ms, 6,255 changed cells |

Painting a field that already exists costs what a solid fill does.
The cost of a gradient is building its field, once per gradient and size,
and writing its cells to the terminal, whenever they change.
A gradient that doesn't move costs output once.
An animated one rebuilds its field and rewrites its cells every frame.

### Where the caches go

Following the project's cache placement rules:

- **Ramps: shared, at the source.**
  An `lru_cache` keyed by the gradient's stops and interpolation.
  The gradients an app uses are few, and recur across nodes and frames.
- **Fields and their cells: per node.**
  They're keyed by one node's geometry, and how many are live grows with the app.
  They go in the per-node paint cache that the
  [Canvas plan](canvas-and-embedding.md#open-decisions) builds,
  kept across frames the way `LayoutTree` keeps texts and placements.
  The Canvas work lands first,
  and this plan is revised against the cache it builds before gradients are implemented.

Both get their hit rates checked (`cache_info()`)
on a workload with more gradient boxes than any shared `maxsize`.

### Output

`paint_to_instructions` resets and re-sends the whole SGR whenever a cell's style differs from the last.
Gradient cells differ only in color,
so sending just the changed foreground or background, without the reset, halves the output (269 to 125 KiB).
Syntax highlighting and any other per-cell colors gain the same,
so it lands as its own change, measured on the existing benchmarks too.

### SVG screenshots

`Frame.svg` and the docs screenshots draw whatever paint made,
so they show gradients with no change:
a `<rect>` for each run of cells with the same background,
and a `fill` on each grapheme's `<tspan>` whose foreground isn't white.
They draw the cells, not a smooth gradient,
which is what the terminal shows.
An SVG `<linearGradient>` would be smoother than the terminal, and output never sees the gradient anyway.
`shape-rendering: crispEdges` already keeps adjacent rects from showing seams,
and an SVG cell is `0.55em` by `1.13em`, close to the default aspect ratio of 2,
so an angle looks the same in a screenshot as in a terminal.

What changes is size, since a gradient makes most runs one cell long:

| Frame, a full gradient at 30 degrees | SVG | Rects |
| --- | --- | --- |
| 60x20, a docs screenshot | 95 KiB | 1,201 |
| 200x50 | 514 KiB, 48 ms to build | 6,493 |
| 200x50, solid | 5 KiB, 8 ms | 51 |
| the largest in `docs/assets/` today | 32 KiB | |

Two ways to shrink it, neither taken (see [Decisions](#decisions)):

- **Rects in cell units**, under a `viewBox` that scales them,
  instead of `em` coordinates with two decimals:
  26% smaller (95 to 70 KiB), and it changes every screenshot in the docs.
- **The backgrounds as one PNG**, a pixel per cell,
  scaled up under `image-rendering: pixelated`:
  a few KiB at any size, with stdlib `zlib` to encode it.
  It turns the backgrounds into one line that doesn't diff,
  where today a screenshot is indented so that it diffs line by line,
  and how SVG viewers honor `pixelated` on an `<image>` needs checking.

Gradient screenshots in the docs stay small instead,
filling part of a frame rather than all of it.
A test pins a gradient frame's SVG, so the per-cell colors are checked in that output too.

## Deferred

- **Two samples per cell.**
  Drawing an empty cell as `▀`, with one sample in its foreground and one in its background,
  doubles vertical resolution, which a short vertical gradient needs most.
  It changes the cell's grapheme, which the text screenshots, copying text from the terminal,
  and border healing all see, and text cells can't do it at all.
  Several plausible designs (opt-in per gradient, per slot, or automatic for empty cells),
  and no way yet to choose between them.
- **Tailwind's composition** (`bg-linear-to-r from-red-500 via-amber-400 to-blue-500`).
  It needs gradients that merge field by field, as style fragments with `UNSET` stops,
  or separate fields per slot for each part.
  Several plausible designs; the constructors cover the need meanwhile.
- **The cell aspect ratio from the terminal** (`CSI 16 t`).
  Cheap to ask for, but it's an input-parsing change with a reply some terminals never send,
  and the knob covers it.
- **`background-attachment: local`**, a scroll container's own gradient scrolling with its content.
  A child's gradient already moves with it, since layout scrolls its box.
- **Dithering.** Truecolor output has 8 bits per channel and needs none.

## Decisions

Each settled choice, with what it costs:

- **Oklab is the default interpolation.**
  It's CSS's default, keeps a red-to-green gradient from going muddy in the middle,
  and costs nothing per cell with a ramp; sRGB is one argument away.
  It costs matching `Color.blend`, which mixes in sRGB,
  and what a browser draws for legacy-syntax colors like `linear-gradient(red, blue)`.
- **Angles and circles are in visual units.**
  `45deg` and `circle` look like they do on the web.
  It costs computing in a unit the layout doesn't use,
  and a default aspect ratio that's wrong for some fonts until the knob is set.
- **Cells sample from center to center.**
  End cells show the end colors, which a short box needs.
  It costs matching CSS's pixel-center sampling, so a gradient's numbers differ from a browser's for the same box.
- **Each slot maps over the box it paints**, with `box` to override.
  A margin gradient spans the margin, and so on for each slot.
  It costs alignment: a border and a background with the same stops line up only when `box` says so.
- **Chunks take gradients**, mapped over the element's content box.
  Widening `CellStyle` gives them gradients without a second style type.
  It costs CSS's per-span mapping: a chunk's gradient continues the element's rather than spanning the chunk.
- **Gradient SVGs keep one rect per run**, and gradient screenshots in the docs stay small.
  Screenshots keep diffing line by line, and the rest of the screenshots don't change.
  It costs size: a full-frame gradient screenshot is about three times the largest in the docs today.

## Work

1. Bring in the Canvas work and its per-node paint cache, and revise this plan against them.
2. `counterweight.gradients`: `Stop`, `Hint`, the three gradient types and their constructors,
   stop fixup and hints, color-space conversion (sRGB, Oklab, Oklch with hue methods),
   ramps, and fields for each geometry.
   Pure functions, tested directly, with property tests that a ramp lookup matches the exact color
   to within a channel step, and that magic corners land the end colors on the corners.
3. Paint: widen the slots, paint each slot from its field kept in the per-node paint cache,
   and pass the cell aspect ratio in from `app()`.
   A `gradients` benchmark workload with a static and a rotating gradient,
   profiled with the `cw-profile` workflow.
4. Output: send only the colors that changed between styles that differ only in color.
5. Utilities, a `docs/styles/gradients.md` page with screenshots from `docs/examples/`,
   and an `examples/gradients.py` that rotates a gradient, as the old branch's did.
6. Tests to 100% coverage, including a gradient frame's SVG and text output,
   and a mutation testing pass over the new code.
