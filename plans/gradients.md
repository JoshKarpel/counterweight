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
(`Color` has no alpha),
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
The ratio is a parameter of `app()`, passed to the layout tree that builds fields
(see [Where the caches go](#where-the-caches-go)),
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
That makes some gradients degenerate:
a radial gradient whose radius is zero on an axis (`closest-side` in a one-row box, say),
and a repeating gradient whose stops span nothing.
Those follow CSS Images 4's rules for degenerate gradients rather than dividing by zero.

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
Text overflows its content box down and to the right,
and a `box` override can name a box smaller than the region its slot paints.
What color those cells take is an [open question](#what-color-do-cells-outside-the-mapping-box-take).

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

A stop is an RGB `Color`, not an `IndexedColor` or `TerminalDefault`.
The terminal decides what those look like, so the app has no color to interpolate from.
CSS can take `currentcolor` and system colors as stops because the browser knows their values;
counterweight knows a palette entry only as `DEFAULT_PALETTE` guesses it,
and interpolating from that guess would draw a gradient that doesn't meet the user's theme at either end.

Hints are `Hint(0.3)` among the stops.
The constructors parse once:
they fix up stop positions into a resolved form the painter reads,
and raise `ValueError` for fewer than two color stops
or a hint that isn't between two of them.
That holds only if every position is a fraction:
whether `At` takes a `waxy.Length` is an [open question](#can-stops-be-lengths-in-cells).
Every field is hashable, so a `Style` holding a gradient hashes and caches as it does today,
and `|` replaces a gradient whole rather than merging its fields.

The slots widen from `AnyColor` to `AnyColor | Gradient`:
`Style.margin_color`, `padding_color` and `content_color`,
and `CellStyle.foreground` and `background`,
which `text_style`, `border_style`, chunks and a canvas painter's cells share.
`ResolvedCellStyle`, which output reads, stays `AnyColor`:
paint turns a gradient into each cell's color before anything reaches output.
Where `ResolvedStyle` holds a cell style's gradient until then
is an [open question](#where-does-resolvedstyle-keep-a-slots-gradient).

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
  It depends only on the stops, `repeating`, the interpolation and the hue method,
  so it's a lookup table of colors, built once per gradient value
  with the color math, hints and color-space conversion.
  It needs enough entries that a lookup is within a channel step of the exact color,
  which 256 per pair of adjacent stops isn't:
  red to blue in Oklab misses by 4 steps, and black to white with a hint at 0.1 by 11,
  where the hint's curve is steepest.
- **The field** maps each cell of a box to an index into the ramp.
  It depends on the geometry (direction, shape, size, `at`),
  the box's size in cells, and the cell aspect ratio,
  but not on the colors or the box's position.

A slot's cells are then a lookup: the ramp's colors made into `Cell`s for that slot
(`Cell.blank(color)` for a background, or the border character or text grapheme in a style
whose foreground or background is the ramp's color),
indexed by the field.
Whether a field covers its whole box or only the rows inside the clip
is an [open question](#does-a-field-cover-the-whole-box-or-only-the-rows-in-view).

Text and canvas rows can't take that lookup whole.
A grapheme's own style can set the color the gradient would give it,
so only the graphemes that leave it unset take the field's color,
and that's known only before they're resolved.
Paint's shared `line_cells` cache resolves a row against one `ResolvedCellStyle`,
which has no gradient to hold,
so a gradient text's rows are resolved against the field cell by cell
and kept per node with the field (see [Where the caches go](#where-the-caches-go)),
rebuilt when the lines, the style or the field change.
A two-cell-wide cluster takes the field's color at its first cell for both of its cells,
since the terminal draws both halves in the style it's written with,
and its continuation cell shares that style today.
A canvas reaches the same path from its background:
`canvas_text_style` resolves a painter's unset background to the canvas's `content_color`,
so a transparent pixel over a gradient `content_color` shows the field's color at that cell,
as it shows a solid `content_color` today.

A linear field is cheap to build row by row:
the position along the gradient is affine in `x` and `y`,
so each row is a start and a step.
Radial and conic fields need a square root or an `atan2` per cell.

The ramp also bounds how many distinct styles a gradient makes,
which matters to the shared flyweight caches
(`Cell` holds 2**14, `ResolvedCellStyle` and `sgr_from_cell_style` 2**10):
a 200x50 box at 30 degrees has 400 distinct colors computed exactly,
and never more than the ramp's entries through it.
That bound is per gradient: a cell whose foreground and background are both gradients,
such as a border with `border_gradient` and `border_bg_gradient`, can take any pair of their colors,
and a few gradients on screen together already hold more styles than those caches.

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
  An `lru_cache` keyed by the gradient's stops, `repeating`, interpolation and hue method.
  The gradients an app uses are few, and recur across nodes and frames.
- **Fields and their cells: per node, in `LayoutTree`.**
  They're keyed by one node's geometry, and how many are live grows with the app.
  `LayoutTree.drawings` already keeps each canvas's rows by node
  with the painter and size that drew them, and reuses them while both compare equal
  (see the [Canvas plan](canvas-and-embedding.md#the-element-and-its-painter)).
  Fields follow it: a `LayoutTree.fields` keeps each node's fields
  by the gradient and the box each maps over, so each distinct chunk gradient in a text gets its own,
  with the box size and the aspect ratio each was built for,
  and `LayoutTree.painted` hands them to paint beside the node's lines,
  building one only when one of those changed.
  `LayoutTree.apply` drops a node's fields when it drops the node, as it does its drawing.

Both get their hit rates checked (`cache_info()`)
on a workload with more gradient boxes than any shared `maxsize`,
and so do the shared caches a gradient's cells pass through:
the `Cell` and `ResolvedCellStyle` flyweights, `Cell.blank` and `sgr_from_cell_style`.

### Output

`paint_to_instructions` resets and re-sends the whole SGR whenever a cell's style differs from the last.
Gradient cells differ only in color,
so sending just the changed foreground or background, without the reset, halves the output (269 to 125 KiB).
`sgr_color` already builds one color's parameters on its own,
for RGB, palette and default colors alike, so the change is to `paint_to_instructions` alone.
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

## On a canvas

A canvas has no slots to put a gradient in: its painter draws every cell.
`counterweight.painters.pixels` gets two pieces that draw one there,
at two samples per cell:

```python
@classmethod
def from_gradient(cls, width: int, height: int, gradient: Gradient) -> Pixels: ...  # on Pixels


@dataclass(frozen=True, slots=True)
class HalfBlockGradient:
    gradient: Gradient

    natural_size = (0, 0)  # size it with its style, as a terminal canvas is
    keeps_aspect_ratio = False

    def draw(self, width: int, height: int) -> Rows:
        return HalfBlocks(Pixels.from_gradient(width, 2 * height, self.gradient)).draw(width, height)
```

- **`Pixels.from_gradient`** is a picture to draw on:
  a gradient background that a paint program or a plot then sets points over with `with_points`.
  It builds the gradient's field over the picture's pixels and looks each one up in the ramp,
  with the same functions an element's slots use.
  Pixels under `HalfBlocks` are about square, so the field takes them as square
  rather than taking the cell aspect ratio,
  as `HalfBlocks` keeps an image's proportions without correction.
  The gradient box spans pixel centers, so the corner pixels take the end colors,
  and lengths (`at`, a radius) are in pixels.
  A gradient's `box` names one of an element's boxes, so it doesn't apply here:
  the gradient maps over the whole picture.
- **`HalfBlockGradient`** is a painter that fills its canvas with a gradient at whatever size the canvas is.
  A `Pixels` has a fixed size, and `HalfBlocks` scaling it to a larger box repeats pixels into visible bands,
  so the painter builds its picture at the box's size, `width` by `2 * height` pixels, on each draw.
  `LayoutTree.drawings` reuses what it drew while the gradient and the box's size are unchanged,
  so a gradient that doesn't move is drawn once, with no cache of its own.

The browser's canvas takes gradients too, as a `fillStyle`:
`createLinearGradient(x0, y0, x1, y1)`, `createRadialGradient` with two circles,
and `createConicGradient(angle, x, y)`, all in the canvas's own pixels.
These take the CSS geometry instead,
so the `Gradient` value an element's style holds draws the same on a canvas.
The canvas API's points and two-circle radials have no counterpart (see [Decisions](#decisions)).

## Deferred

- **Two samples per cell.**
  Drawing an empty cell as `▀`, with one sample in its foreground and one in its background,
  doubles vertical resolution, which a short vertical gradient needs most.
  `HalfBlocks` (`counterweight.painters.pixels`) already draws a canvas this way,
  and `HalfBlockGradient` uses it to show a gradient on a canvas at two samples per cell
  (see [On a canvas](#on-a-canvas)).
  For an element's slots, it changes the cell's grapheme, which the text screenshots,
  copying text from the terminal, and border healing all see, and text cells can't do it at all.
  Several plausible designs (opt-in per gradient, per slot, or automatic for empty cells),
  and no way yet to choose between them.
- **Tailwind's composition** (`bg-linear-to-r from-red-500 via-amber-400 to-blue-500`).
  It needs gradients that merge field by field, as style fragments with `UNSET` stops,
  or separate fields per slot for each part.
  Several plausible designs; the constructors cover the need meanwhile.
- **The cell aspect ratio from the terminal** (`CSI 16 t`).
  Cheap to ask for, but it's an input-parsing change with a reply some terminals never send,
  and the knob covers it.
- **Palette and default colors as stops.**
  A terminal reports its palette entries (`OSC 4`) and its default colors (`OSC 10` and `OSC 11`) when asked,
  which would give the app the RGB values to interpolate.
  It's the same kind of change as asking for the cell size, with replies some terminals never send,
  and a gradient between them goes stale when the user changes their theme.
- **`background-attachment: local`**, a scroll container's own gradient scrolling with its content.
  A child's gradient already moves with it, since layout scrolls its box.
- **Dithering.** Truecolor output has 8 bits per channel and needs none.

## Open questions

Four choices the rest of the plan depends on, each with how the web answers it,
the options and what each costs, and the one this plan leans toward.
The third and fourth fit together (see [Together](#together)).

### Where does `ResolvedStyle` keep a slot's gradient?

`ResolvedStyle.border_style` and `text_style` are `ResolvedCellStyle`s,
which stay `AnyColor`, so nothing resolved can carry a border or text gradient to paint.
`margin_color`, `padding_color` and `content_color` aren't a problem:
only paint reads them, so they become `AnyColor | Gradient` in `ResolvedStyle` too.

The web: Compose's public `TextStyle` takes a `color` and a `brush` as separate fields,
and folds them internally into one value that is either a color or a brush.
SVG's `fill` takes a color or a paint server.

- **A. Widen `ResolvedCellStyle`.**
  The smallest diff.
  It costs output's type: it admits a gradient output can never receive,
  so `sgr_color` grows an unreachable branch, and a gradient could leak into `Paint` without mypy noticing.
- **B. Keep `ResolvedCellStyle`, with gradient fields beside it**
  (`border_foreground_gradient: Gradient | None`, ...).
  The fast path is untouched.
  It costs two fields that must agree, since the style's color is a meaningless placeholder while a gradient is set,
  and chunks: `line_cells` resolves each chunk's `CellStyle` against the text style through `resolve_cell_style`,
  and a chunk's gradient has no field to land in.
- **C. A second resolved type that paint reads**, with colors that are `AnyColor | Gradient`.
  `ResolvedStyle` and `resolve_cell_style` return it,
  and paint turns it into a `ResolvedCellStyle` for each cell;
  for a solid style that's one cached step,
  so `line_cells` and `border_fills` get the same flyweight they do today.
  It costs a second flyweight type with the same fields,
  and that step wherever a style reaches output.

Leaning C: chunks put the wide type into `resolve_cell_style` anyway,
and C is the option that keeps a gradient out of output's type.

### Can stops be lengths in cells?

`At = float | waxy.Length` lets a stop be a number of cells,
but whether 10 cells comes before or after 40% depends on the gradient line's length in that box,
so the constructors can't fix up the stops, and a ramp cached by stops alone is wrong at every size but one.
Visual units add a second problem:
a length along a line at 30 degrees has no unit but columns,
so `to bottom` with `Length(10)` would cover 5 rows,
and measuring side keywords in their axis's cells instead
makes `to bottom` and `180deg` disagree though they're the same direction.

The web: linear and radial stops are `<length-percentage>`s,
fixed up when the gradient is drawn, against the gradient line's length for that box.
Conic stops are angles or percentages, never lengths.

- **A. Fractions only (`At = float`).**
  The constructors resolve everything, ramps depend only on the gradient,
  and a stop means the same thing on a canvas,
  which also answers two review findings:
  "draws the same on a canvas" for length positions, and conic stops as lengths.
  It costs stripes of a fixed width:
  `repeating-linear-gradient(red 0 2px, blue 2px 4px)`, a progress bar's barber pole, hazard stripes.
  With fractions, a stripe grows and shrinks with its box.
- **B. Lengths, resolved per box.**
  `resolve_stops(gradient, line_length)` returns fraction-only stops, and the ramp is keyed by them,
  so a gradient whose stops are all fractions resolves to the same stops at every size and still shares one ramp.
  It costs a ramp per line length a length gradient appears at (a resize animation builds one every frame),
  validation moving partly from the constructor to paint,
  and the unit question, which it still has to answer.

Leaning A, with lengths deferred as having several plausible designs:
the unit of a length along an angled line has no answer yet,
and the deferred entry names stripes as the use.

### Does a field cover the whole box, or only the rows in view?

Building only the rows inside the clip,
under a cache keyed by the gradient, the box's size and the aspect ratio,
either leaves out the rows that scroll into view or rebuilds on every scroll.

The web: browsers rasterize in tiles, painting only the tiles in view,
and Chromium evaluates a gradient per pixel in a shader with no field kept per box.
Here, `LayoutTree.drawings` keeps a canvas's whole drawing whatever the clip,
and text builds only the rows inside the clip, through the shared `line_cells` cache.

- **A. The whole box.**
  The key stays the gradient, the size and the aspect ratio.
  It costs a box that grows, such as a chat log or a command's output:
  a `to bottom` gradient changes every color when the height changes,
  so a 200-column, 5,000-row box rebuilds about a million cells for each new line.
- **B. The rows in view, keyed by which rows they are.**
  Always correct, and never more than the viewport.
  It costs rebuilding the viewport on every scroll step:
  1.6 ms for a 200x50 linear field in the probe,
  and more for radial and conic fields, which haven't been measured.
- **C. The rows in view, kept per node as they're built.**
  A scroll builds only the rows that came into view, and scrolling back costs nothing.
  It costs a mutable row store per node, dropped whenever the size or gradient changes,
  which in the worst case holds as much as A.

Leaning B, moving to C if profiling says to:
C is B plus keeping rows, so the move is small,
and the `gradients` benchmark gets a long scroll container to make that call on.

### What color do cells outside the mapping box take?

Text overflows its content box down and to the right,
and a `box` override can name a box smaller than the region its slot paints,
such as a margin gradient with `box="content"`.
A field the size of the mapping box has no entries for those cells,
and the end colors are wrong for most geometries:
text overflowing to the right under `to bottom` should keep each row's color,
and a repeating gradient should keep repeating.

The web: CSS sizes a gradient image to its origin box
and by default tiles it outside that box (`background-repeat: repeat`);
with `no-repeat`, the cells outside are transparent.
SVG's `spreadMethod` defaults to `pad`:
the gradient's geometry continues everywhere, with the end colors past its ends.

- **A. Continue the geometry, as SVG's `pad` does.**
  A cell outside the box is evaluated where it is, relative to the mapping box:
  overflowing text under `to bottom` keeps each row's color,
  a repeating gradient keeps repeating, and radial and conic gradients continue.
  It costs a field that covers the cells being painted rather than the mapping box,
  keyed by where those cells sit relative to it.
- **B. Tile, as CSS's default does.**
  Each box-sized copy restarts the gradient,
  so overflowing text jumps color at the box's edge,
  which is rarely wanted: CSS authors usually set `no-repeat` on a gradient.
- **C. Clamp to the nearest cell inside the box.**
  The field stays the box's size, and a lookup outside it clamps its coordinates.
  It matches A for horizontal and vertical gradients.
  It costs the rest: angled, radial and conic gradients smear instead of continuing,
  and a repeating gradient stops repeating.

Leaning A: it's what the geometry already defines.

### Together

The leanings fit together.
With the third question's B and the fourth's A,
a field is the rows being painted at an offset from the mapping box,
and nothing in it asks whether a cell is inside that box.
With all four, a field is one pure function of the gradient, the mapping box's size, the aspect ratio,
and the rows being painted relative to the mapping box,
and its colors come from a ramp keyed by the gradient alone.

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
- **Stops are RGB `Color`s.**
  A gradient looks the same in every terminal, and its ramp is computed in the app.
  It costs following the user's theme: `IndexedColor` and `TerminalDefault` can fill a slot but not stop a gradient.
- **Fields are kept in `LayoutTree`**, beside each canvas's drawing.
  They live and die with the node, as drawings do, with no second per-node store to keep in step.
  It costs layout knowing which box each slot maps over, which is a question of paint,
  and the aspect ratio reaching layout, which otherwise has no use for it.
- **A canvas takes the CSS geometry**, through `Pixels.from_gradient` and `HalfBlockGradient`.
  One `Gradient` value draws the same in an element's slot and on a canvas.
  It costs the browser canvas's gradients: there are no point-to-point lines or two-circle radials.
- **Chunks take gradients**, mapped over the element's content box.
  Widening `CellStyle` gives them gradients without a second style type.
  It costs CSS's per-span mapping: a chunk's gradient continues the element's rather than spanning the chunk.
- **Gradient SVGs keep one rect per run**, and gradient screenshots in the docs stay small.
  Screenshots keep diffing line by line, and the rest of the screenshots don't change.
  It costs size: a full-frame gradient screenshot is about three times the largest in the docs today.

## Work

1. `counterweight.gradients`: `Stop`, `Hint`, the three gradient types and their constructors,
   stop fixup and hints, color-space conversion (sRGB, Oklab, Oklch with hue methods),
   ramps, and fields for each geometry.
   Pure functions, tested directly, with property tests that a ramp lookup matches the exact color
   to within a channel step (which sets the ramp's size, hints and Oklch included),
   and that magic corners land the end colors on the corners.
2. Paint: widen the slots, keep each node's fields in `LayoutTree.fields`,
   paint each slot from its field, resolve gradient text and canvas rows against it,
   and pass the cell aspect ratio from `app()` to `LayoutTree.compute`.
   A `gradients` benchmark workload with a static and a rotating gradient,
   profiled with the `cw-profile` workflow.
3. Canvas: `Pixels.from_gradient` and `HalfBlockGradient` in `counterweight.painters.pixels`,
   and a section on them in `docs/elements/canvas.md`.
4. Output: send only the colors that changed between styles that differ only in color.
5. Utilities, a `docs/styles/gradients.md` page with screenshots from `docs/examples/`,
   and an `examples/gradients.py` that rotates a gradient, as the old branch's did.
6. Tests to 100% coverage, including a gradient frame's SVG and text output,
   a canvas with transparent pixels over a gradient `content_color`,
   and the corner pixels of `Pixels.from_gradient` taking the end colors,
   and a mutation testing pass over the new code.
