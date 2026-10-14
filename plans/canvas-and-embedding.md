# Plan: Canvas, One-Shot Commands and Embedded Terminals

Artifact: https://claude.ai/code/artifact/d1d450c4-611b-4225-b9f7-aac8f9fc1a90

This plan lands three features that share one stack.
A `Canvas` element paints cells directly, skipping text layout.
A one-shot command runs a program that's expected to exit, and shows what it printed, colors and all.
An embedded terminal runs a program on a pseudo-terminal and shows it in a box, with input routed to it,
which is enough to build a terminal multiplexer in counterweight.
Neither of the last two needs an element of its own:
each is a `Canvas` whose painter draws what an emulator made of a program's output.

A one-shot command is a terminal you read, and an embedded terminal is one you use.
Both run a program on a pseudo-terminal, feed an emulator, snapshot it at most once per frame,
answer the program's queries, and draw the result in a `Canvas`.
They differ in everything about input and lifetime:

| | One-shot command | Embedded terminal |
| --- | --- | --- |
| The program | expected to exit, successfully or not | interactive, running as long as its pane |
| Starts | when the app calls `run(argv)`, from a key press or an effect on mount | when the pane mounts |
| Input | none: stdin is `/dev/null`, and `PAGER=cat` and `GIT_PAGER=cat` by default | key presses, pastes and mouse events, re-encoded as the bytes a terminal sends |
| Focus | none | focusable, with handlers such as a prefix key put before its own |
| Shows | the transcript: everything printed, scrollback then the screen | the current screen, with its cursor |
| Size | width fixed when the run starts and `rows` a knob (24), growing with its output and scrolling | its box's size, with a resize sending the program `SIGWINCH` |
| Result | a `CommandRun` value that outlives the program | live state, tied to the mounted pane |
| Ends | when the program exits, or the run is cancelled or times out | when the program exits, or the pane unmounts |
| Asks of the emulator | scrollback with its styles | dirty rows, and key and mouse encoding |

Input and focus are why the one-shot command needs none of [phase 5](#phase-5-framework-fixes-for-the-embed).

It lands in six phases, each of which stands alone:

| Phase | What it adds | Needs |
| --- | --- | --- |
| 1. [Canvas](#phase-1-canvas) | the element, painters, and pixel images | |
| 2. [Emulator](#phase-2-emulator) | a terminal emulator behind `Emulator` and `Screen`, and the screen painter | 1 |
| 3. [Pseudo-terminals](#phase-3-pseudo-terminals) | `use_pty`: a program on a PTY, its output, its exit, and resizing | |
| 4. [One-shot commands](#phase-4-one-shot-commands) | `use_command`, the transcript painter, a widget, and `use_rects(handle)` | 1, 2, 3 |
| 5. [Framework fixes](#phase-5-framework-fixes-for-the-embed) | raw input, focusing a new component, and modal keys | |
| 6. [Embed](#phase-6-embedding-terminals) | input encoding, `use_terminal`, and a `terminal` widget | 1, 2, 3, 5 |

Each arrow points from a phase to one that needs it:

```text
1 Canvas ──> 2 Emulator ──┐
                          ├──> 4 One-shot commands
3 Pseudo-terminals ───────┤
                          └──> 6 Embed
                                 ^
                                 │
                               5 Framework fixes
```

One-shot commands don't need phase 5, so they can ship before the embed.
Phase 3 can be written alongside phases 1 and 2, and phase 5 any time before phase 6.
[Fidelity](#later-fidelity) improvements that neither feature needs come last.

It doesn't cover detaching sessions, scrollback or copy mode in an embedded terminal,
or graphics protocols (sixel, kitty images).

## The spike

A spike answered whether the canvas and the embed are feasible.
It didn't build one-shot commands, which phase 4 builds from the pieces it did.
Its code is in [the appendix](#appendix-the-spike-code):
diffs against `main` for the files it changed, and the full source of the files it added.
It ran with `uv run --with pyghostty==0.1.3 ...`, since the dependency wasn't in `pyproject.toml`.
The existing tests passed and mypy was clean; the new code had no tests.

| Code | What it is | Phase |
| --- | --- | --- |
| `elements.py`, `layout.py`, `paint.py` | the `Canvas` element | 1 |
| `utils.py` | `HalfBlocks`, a `Canvas` painter equivalent to `canvas()` | 1 |
| `benchmarks/canvas.py` | a `canvas-element` workload: `canvas` redrawn with `Canvas` and `HalfBlocks` | 1 |
| `emulator.py` | libghostty-vt behind `Emulator`, which produces immutable `Screen` values | 2 |
| `headless/terminal.py` | `use_pty` and `use_terminal` | 3 and 6 |
| `input_encoding.py` | pure functions from key, paste and mouse events back to the bytes a terminal sends | 6 |
| `examples/multiplexer.py` | shells side by side, with a tmux-style `Ctrl+B` prefix | 6 |

Each phase writes its code fresh, with tests, starting from `main`'s code and using the appendix as a reference.

## Phase 1: Canvas

### What text layout costs a canvas

`utils.canvas` turns a pixel grid into a tuple of `Chunk`s for a `Text`.
Each frame, the `Text` is then measured (`MeasurableText.of`, `_measure_text`, wrapping) during layout,
and wrapped again into cells (`text_lines`) during paint,
although a canvas has no words, never wraps, and knows its size up front.
In the `canvas` benchmark, that path is most of the frame:

| Stage | `canvas` (`Text` chunks) | `canvas-element` (`Canvas`) | Change |
| --- | --- | --- | --- |
| median frame | 6.66 ms | 1.40 ms | -79% |
| `LayoutTree.compute` | 2.13 ms | 0.11 ms | -95% |
| `update_shadow` (building chunks) | 1.07 ms | 0.23 ms | -79% |
| `paint_layout` | 1.60 ms | 1.14 ms | -28% |

Both runs drew the same final frame (`profiles/canvas-text.txt` and `profiles/canvas-element.txt` are identical).
The machine was shared with a mutation testing run, so absolute times are noisy:
an earlier `canvas` run measured a 2.6 ms median.
The stage ratios held across runs.
Every walker moves every frame in this workload, so the painter's cache never hits;
a canvas that changes less often skips its painter entirely.

### The element and its painter

```python
type Rows = Sequence[Sequence[StyledGrapheme]]  # top to bottom, each from the content box's left edge


class Painter(Protocol):
    @property
    def natural_size(self) -> tuple[int, int]: ...  # (columns, rows): the intrinsic size

    @property
    def keeps_aspect_ratio(self) -> bool: ...  # whether a box sized on one axis takes the other from natural_size

    def draw(self, width: int, height: int) -> Rows: ...  # the content box's size -> rows of styled graphemes


@dataclass(frozen=True, slots=True, kw_only=True)
class Canvas:
    painter: Painter
    style: Style = _DEFAULT_STYLE
    on_input: InputHandler | None = None
    handle: ElementHandle | None = None
```

The spike's `Canvas` took a bare callable, `draw: Callable[[int, int], Rows]`, and `width` and `height` fields beside it.
A protocol fixes two problems with that:

- **The size was stated twice.**
  A painter knows its natural size, but the spike makes the caller repeat it on the element
  (`width, height = painter.cells`, then `Canvas(draw=painter, width=width, height=height)`).
  Taking it from the painter keeps it in one place, as an `<img>` takes its natural size from its image.
- **Hooks treat callables as initializers.**
  `use_state(painter)` calls a callable painter, and `set_state(painter)` treats it as an updater.
  The spike hit both (`Screen` was callable at first; `use_ref(on_output)` was called).
  A painter with a named `draw` method isn't callable, so it can be held in state like any other value.

`draw` returns `StyledGrapheme`s, the cells a `Text`'s chunks become, and paint resolves them the same way:
whatever a grapheme's `CellStyle` leaves unset comes from the element's `text_style`,
and a two-cell grapheme gets its continuation cell.
So a painter never needs the element's style.
A pixel painter leaves a transparent pixel's color unset to show the canvas's background,
and the terminal painter leaves a program's default colors unset to follow the app's.
Building a cell is `StyledGrapheme(grapheme="▀", style=CellStyle(foreground=top, background=bottom))`,
with no resolved style to fill in.
`draw`'s rows don't depend on the style, so the paint cache stays keyed by `(painter, width, height)`.
Resolving runs after it and costs what it costs a `Text`:
one cached `resolve_cell_style` per run of graphemes that share a style.
The per-node cache (see [Open decisions](#open-decisions)) can keep the resolved rows too,
and resolve again only when the rows or the `text_style` change.

Painters live in a `counterweight.painters` package, one module per kind:
`counterweight.painters.pixels` holds `Pixels` and `HalfBlocks` (phase 1),
`counterweight.painters.terminal` the terminal's screen painter (phase 2) and transcript painter (phase 4),
and later ones could include a plotter that draws data as braille curves with text tick labels.
The plotter is why `draw` returns cells rather than pixels: its labels are text, which pixels can't hold.

The element is `Canvas` rather than `Image` because most of what it shows isn't an image:
a terminal pane, a plot, a game board.
It is the surface, and its painter decides what's on it.
SwiftUI's `Canvas { context, size in ... }` is the closest precedent, a view whose content code draws at the view's size.
`Image` would also collide with `PIL.Image` in the image example.
If the image case wants its own name, an `image(pixels, fit=...)` function
that returns `Canvas(painter=HalfBlocks(...))` can give it one.

Prior art splits on two questions, and `Canvas` takes the same side as Textual and Flutter on both:

- **Who owns the buffer?**
  [ratatui](https://github.com/ratatui/ratatui)'s `Widget::render(self, area, &mut Buffer)` hands the widget the whole screen buffer
  in absolute coordinates.
  Nothing stops a widget writing outside `area`, and writing outside the buffer panics.
  Its changelog shows built-in widgets learning to clip one by one (#1670, #1996, #2368).
  [Textual](https://github.com/Textualize/textual)'s `render_line(y) -> Strip` returns immutable values instead,
  and caches them per line.
  `draw` returns rows of cells in local coordinates, and the framework places and clips them,
  through the same `write_row` and clip that `Text` uses.
  A painter can't draw outside its box, and the result is a value that can be cached.
- **When does the painter re-run?**
  Ratatui re-renders everything every frame and saves only terminal output through its buffer diff.
  Flutter's `CustomPainter.shouldRepaint(old)` and Compose's `drawWithCache` skip the painter when its inputs are unchanged.
  The spike caches `draw(width, height)` by `(painter, width, height)` (`paint.canvas_rows`),
  so a painter that's a frozen dataclass equal to last frame's isn't called at all.
  This is Flutter's `shouldRepaint` with `==` as the test, which is already how counterweight decides everything else.

### Sizing

Sizing follows HTML's replaced elements (`<img>`, `<canvas>`).
The painter's natural size is the canvas's intrinsic size,
which layout uses on each axis the style or the parent's layout leaves undetermined.
A styled or stretched size wins on its axis, and `draw` is called with the box's real content size.
Unlike a browser `<canvas>`, there's no bitmap to stretch to the box, so the painter decides what to draw at that size.
Rows that overflow the box are clipped, and a box with fewer rows shows the background, as `Text` does.

A probe of the spike's `Canvas` in a 12-cell bordered row beside a `Text("TXT")` showed it behaves as an `<img>` does in flexbox:

```text
intrinsic 6x2, style auto            intrinsic 20x1 in a 12-cell row
│aaaaaaTXT   │                       │aaaaaaaaaaaaa
│aaaaaa      │                       │aaaaaaaaaaaaa

intrinsic 6x2, style width(10)       intrinsic 20x1, min_width(0)
│aaaaaaaaaTXT│                       │aaaaaaaaaTXT│
│aaaaaaaaa   │                       │aaaaaaaaa   │
```

- A styled width is a flex basis: `width(10)` beside `TXT` shrank to 9.
- **The intrinsic size is a floor in a flex row.**
  Flex items get `min-width: auto`, which for a replaced element resolves to its intrinsic size,
  so a 20-cell canvas overflowed its row, drew over the border, and pushed `TXT` out of view.
  `min_width(0)` lets it shrink, as `min-width: 0` does for an `<img>`.
  The `Canvas` docstring and docs need to say so.
- Every canvas drew 2 rows even with an intrinsic height of 1: the row stretches its children (`align-items: stretch`).

Two changes complete the replaced-element model:

- **Transfer the aspect ratio.**
  An `<img>` with only `width` set scales its height to keep its natural aspect ratio.
  The spike's `_measure_text` returns the intrinsic height whatever the width.
  A canvas should transfer a known size through its painter's natural ratio,
  most likely by giving its taffy node an `aspect_ratio` when the style doesn't set one,
  so that taffy also applies the ratio through min and max sizes.
  That taffy does this for leaf nodes with a measure function needs checking.
  Only a picture has a ratio to keep, so a painter opts in with `keeps_aspect_ratio`:
  `HalfBlocks` does, while a transcript (phase 4) or a plotter doesn't,
  since a transcript stretched wider than its columns would otherwise grow taller by the same ratio,
  padding itself with blank rows.
- **A painter with no natural size.**
  Flutter and Compose default the intrinsic size to zero, and an invisible canvas is a known complaint.
  HTML's `<canvas>` defaults to 300×150.
  Under the protocol every painter states its size,
  so the question becomes what an unsized painter (a terminal, which takes whatever box it gets) should report.
  Zero with a documented "size it with its style" is the simplest answer.
  A painter whose natural size is zero on either axis has no aspect ratio to transfer,
  so its node gets none, rather than a ratio of `0 / 0`.

### Pixels and images

The two common uses of a canvas both start from a grid of pixels:
drawing (walkers, a paint program, plots), and showing an image loaded from disk or memory.
Three pieces split that work, and each works in one unit:

- `Pixels` is the picture, in pixels:
  a value holding a width, a height and RGBA bytes.
  It knows nothing about cells, boxes or terminals.
- `HalfBlocks` is a `Painter` that holds a `Pixels` and draws it in cells.
  It is the only piece that knows both units:
  each cell shows two pixels stacked vertically,
  as `▀` with the top pixel's color as its foreground and the bottom pixel's as its background.
- `Canvas` is the element, in cells.
  It takes its intrinsic size from its painter, gets a box from layout,
  and places and clips the rows its painter draws.
  It knows nothing about pixels.

Each frame, the three meet in layout, paint, and input:

```text
layout  Canvas --natural_size------> HalfBlocks --(width, ceil(height / 2))--> intrinsic size in cells
paint   Canvas --draw(W, H)--------> HalfBlocks --fit Pixels into W x 2H pixels, encode--> W x H cells
input   Canvas cell (x, y) --------> HalfBlocks.pixels_at --> the source pixels that cell shows
```

Dependencies point one way.
`Canvas` depends only on the `Painter` protocol,
`HalfBlocks` on `Pixels` and `StyledGrapheme`,
and `Pixels` only on `Color`.
`Pixels` and `HalfBlocks` live together in `counterweight.painters.pixels`, not in `utils.py`.

The web splits the same work three ways:

| Web | Counterweight |
| --- | --- |
| a decoded image, or `ImageData`: pixels with a natural size and no box | `Pixels` |
| the browser drawing an image into its box: `object-fit`, `object-position`, and the device pixel ratio | `HalfBlocks` |
| `<img>`, a replaced element: a box in CSS layout with an intrinsic size from its content | `Canvas` |

Cells change three things:

- **`Canvas` is closer to `<img>` than to `<canvas>`.**
  A browser `<canvas>` owns a bitmap at its own resolution (its `width` and `height` attributes),
  and CSS stretches that bitmap to the box.
  `Canvas` owns no bitmap: its painter draws at the box's size, so nothing is stretched after drawing.
- **Pixels per cell is the painter's device pixel ratio.**
  A cell is the layout unit, as a CSS pixel is,
  and `HalfBlocks` puts 1×2 pixels in each, as a 2x display puts 2×2 device pixels in a CSS pixel.
  So the natural size in cells depends on the painter, not only on the pixels:
  a 30×30 `Pixels` is 30×15 cells under `HalfBlocks`, and would be 15×8 under a braille painter's 2×4.
  That's why `natural_size` belongs to the painter, and `Pixels` has no size in cells.
  A cell is about twice as tall as it is wide, so 1×2 makes pixels roughly square,
  and an image keeps its proportions without correction.
  The exact ratio depends on the user's font.
- **`fit` is on the painter, not the element's style.**
  CSS sets `object-fit` on the element (Tailwind's `object-contain`).
  `Canvas` can't apply it, because only a painter with pixels has something to scale:
  a terminal's screen has no "contain".
  The cost is that fit isn't a style utility, so it can't be combined with `|` or shared through a style.

```python
@dataclass(frozen=True, slots=True)
class Pixels:
    width: int
    height: int
    rgba: bytes  # row-major, width * height * 4

    @classmethod
    def blank(cls, width: int, height: int, color: Color) -> Pixels: ...
    @classmethod
    def from_points(
        cls, width: int, height: int, points: Mapping[tuple[int, int], Color], default: Color
    ) -> Pixels: ...
    @classmethod
    def from_rgba(
        cls, width: int, height: int, rgba: bytes
    ) -> Pixels: ...  # raises unless len(rgba) == width * height * 4
    @classmethod
    def from_image(cls, image: SupportsRGBA) -> Pixels: ...  # Pillow, matched structurally
    def with_points(self, points: Mapping[tuple[int, int], Color]) -> Pixels: ...


type Fit = Literal["fill", "contain", "cover", "none", "scale-down"]


@dataclass(frozen=True, slots=True)
class HalfBlocks:
    pixels: Pixels
    fit: Fit = "fill"
    position: tuple[float, float] = (0.5, 0.5)  # object-position, as fractions of the leftover space

    @property
    def natural_size(self) -> tuple[int, int]:
        return self.pixels.width, (self.pixels.height + 1) // 2

    @property
    def keeps_aspect_ratio(self) -> bool:
        return True

    def draw(self, width: int, height: int) -> Rows: ...

    def pixels_at(self, cell: Position, width: int, height: int) -> tuple[Position, ...]: ...  # draw, inverted
```

Drawing and loading then share one painter:

```python
pixels = Pixels.from_points(30, 30, {walker: color for walker, color in ...}, default=black)
Canvas(painter=HalfBlocks(pixels), style=border)  # 30x15 cells, from the painter

image = PIL.Image.open(path)
Canvas(painter=HalfBlocks(Pixels.from_image(image), fit="contain"), style=fill(1) | min_width(0))
```

Without `min_width(0)`, an image wider than the screen would floor its flex item at its intrinsic width
(see [Sizing](#sizing)) and overflow the row rather than shrink to fit.

`draw(width, height)` works in pixels until its last step:

1. **Scale.**
   The scale on each axis is the box's size over the picture's size, both in pixels:
   `width` over the pixel width, and `2 * height` over the pixel height.
   Ratios in cells would be wrong for an odd pixel height, whose natural height rounds up half a cell:
   a 1-pixel-tall picture under `fill` in a 10-row box would cover only its top 10 of 20 pixel rows.
   As with `object-fit`, `fill` scales each axis by its own ratio,
   `contain` uses the smaller ratio on both, `cover` the larger, `none` neither,
   and `scale-down` whichever of `none` and `contain` is smaller.
2. **Place.**
   `position` places the scaled picture in the box's `width` × `2 * height` pixels.
   It places in whole pixels, which are half cells vertically, so a picture can start halfway down a cell.
   Where the picture is bigger than the box (`cover`, `none`), the overflow is cropped.
3. **Sample.**
   Each box pixel the picture covers takes its nearest source pixel.
   A box pixel it doesn't cover, and a transparent pixel, is left unset,
   so it shows the element's background,
   as a contained image in a browser shows its `<img>`'s background around it.
   Alpha is all or nothing: a pixel under half opacity is transparent, and any other is opaque.
   A painter that doesn't know the background can't blend with it.
4. **Encode.**
   Cell `(x, y)` shows box pixels `(x, 2y)` and `(x, 2y + 1)`.
   Two opaque pixels are `▀`, with the top pixel as its foreground and the bottom as its background.
   An unset pixel can only be a background, since an unset foreground resolves to the text color:
   so an unset top pixel makes the cell `▄`, with the bottom pixel as its foreground,
   and two unset pixels make it a space.

The default `fit` is `fill`, as `object-fit`'s is.
For an even pixel height, every `fit` is the identity at the natural size,
so the default matters only when a style or a stretch sizes the box.
A row that stretches its children distorts a `fill` picture, as it does an `<img>` in a flex row, and `contain` keeps the ratio.
An odd pixel height has half a cell more box than picture even at the natural size:
`fill` and `cover` stretch the picture over it, and `contain`, `none` and `scale-down` leave the bottom half of the last row unset
(`utils.canvas` rejects odd heights instead).
A `Pixels` built from `Color`s is opaque, since `Color` has no alpha;
transparency arrives only through `from_rgba` and `from_image`.

- **Bytes, not tuples of `Color`.**
  The paint cache hashes its key on every lookup and compares it on every hit.
  CPython caches a `bytes` object's hash, and comparing equal copies is a `memcmp`:
  on a 4 MiB buffer the first hash took 0.73 ms, the next 0.4 µs, and comparing equal copies 0.14 ms.
  The spike's `HalfBlocks` holds a tuple of `((x, y), Color)` pairs,
  which costs a Python-level `Color.__hash__` per pixel whenever the painter is rebuilt,
  and is the wrong shape for a dense image.
- **What the cache sees.**
  The canvas compares painters with `==`,
  and two `HalfBlocks` are equal when their pixels' bytes, `fit` and `position` are.
  So a component holds only a `Pixels` in state and builds `HalfBlocks(pixels)` in every render,
  and `draw` re-runs only when the pixels or the box change.
  A change is a new `Pixels`: `with_points` copies the whole buffer.
- **Input arrives in cells.**
  A mouse event gives the canvas a cell, and the cell shows two pixels, scaled and placed by `fit` and `position`.
  `pixels_at` inverts `draw` for one cell:
  the source pixels its two halves sample, none where the cell is outside the picture.
  A paint program sets those pixels.
  `examples/mouse.py` draws one full block per cell today, and sets both pixels to look the same.
- **No Pillow dependency.**
  `from_rgba` takes raw bytes, so Pillow, numpy, or any decoder reaches `Pixels` the same way.
  `from_image` takes a `Protocol` with Pillow's `size`, `convert` and `tobytes`,
  which gives the one-liner without importing PIL.
  The docs say to decode before `app()` or in an effect that sets state, never in render.
- **Nearest-neighbor.**
  It reads only the pixels it outputs, which keeps it cheap,
  but it's rough when shrinking a photo a long way.
  Averaging reads every source pixel, which in Python is too slow for a large image.
  The docs point to Pillow's `Image.thumbnail` for quality.
  These costs are estimates to measure in the benchmark.

Deferred, each for a different reason:

- **Shapes** (lines, rectangles, circles, as ratatui's `Canvas` draws):
  several plausible designs, such as pure functions from shapes to `Pixels` or an immutable path builder,
  and no way yet to choose between them.
- **Other cell encodings** (braille 2×4, quadrants 2×2, sextants 2×3):
  each is another painter over the same `Pixels`, scaled and placed as `HalfBlocks` is,
  but each needs design work that `HalfBlocks` doesn't.
  A cell has two colors, which `HalfBlocks` spends one per pixel,
  and the others must split four to eight pixels between them.
  A brightness threshold, the two most distant colors, and a split around the mean are all plausible,
  with no way yet to choose between them.
  Quadrants also make pixels twice as tall as wide, so they need an aspect correction.
  The color split is the same question for all three, so they're best designed together.

### Open decisions

- **The paint cache.**
  `paint.canvas_rows` is a shared `lru_cache`, so a painter must be hashable,
  and a frozen dataclass holding a `dict` raises `TypeError` at paint time.
  It also holds 256 entries for every canvas in the app, so many canvases evict each other.
  A per-node cache, kept across frames the way `LayoutTree` is, needs only `==` and holds one entry per canvas.
  I'd pick the per-node cache.
- **Which background an unset cell shows.**
  Paint fills the content box with `content_color`,
  but resolves a grapheme's unset background against `text_style.background`, which defaults to black on its own.
  So on a canvas styled with only `content_bg`, a cell the picture doesn't reach at all shows `content_color`,
  while a transparent pixel, or the uncovered half of a `▀` or `▄` cell, shows `text_style.background`.
  Either `Canvas` resolves unset backgrounds against `content_color`,
  or the docs say a canvas sets both, as a `Text` with a background does.
- **`utils.canvas`.**
  `examples/canvas.py` carries its own copy of it, and `examples/mouse.py` a full-block variant.
  Once they draw with `Pixels` and `HalfBlocks`, `canvas()` can be deprecated.

### Phase 1 work

1. `Painter`, drawing `StyledGrapheme` rows that paint resolves against the element's `text_style`;
   `Canvas`, taking its intrinsic size from the painter, and its aspect ratio when the painter keeps one;
   and the per-node paint cache.
2. `counterweight.painters.pixels`: `Pixels`, and `HalfBlocks(pixels, fit, position)` with `pixels_at`.
3. Port `examples/canvas.py`, `examples/mouse.py` (setting both pixels of a clicked cell)
   and the `canvas-element` benchmark, and deprecate `utils.canvas`.
4. Docs: a `Canvas` page covering sizing (the shrink floor and `min_width(0)`), writing a painter, and loading an image,
   with screenshots from `docs/examples/`.
   Whether the image example makes Pillow a docs dependency or decodes a bundled file another way is open.
5. Tests to 100% coverage, and a mutation testing pass over the new code.

## Background: how terminal multiplexers work

The research behind this section read tmux at [`f0a2ed3001`](https://github.com/tmux/tmux/tree/f0a2ed3001)
and zellij at [`dfa40f44a4`](https://github.com/zellij-org/zellij/tree/dfa40f44a4).
Both build the same pipeline, with the same stages:

```text
child program <-> PTY master fd <-> parser (VT state machine) -> grid/screen model -> renderer -> outer terminal
                      ^                                                                   |
                      +----------- re-encoded keys, mouse, paste <- key tables <- outer terminal input
```

- **Process model.**
  tmux is a server holding every pane's PTY in one libevent loop.
  Clients pass their tty fd over a Unix socket, and the server writes to it directly.
  zellij runs named threads (`pty`, `screen`, `pty_writer`, `wasm`, `background_jobs`) joined by channels,
  and PTY bytes reach the screen thread through a bounded channel.
- **Parsing.**
  Both parse with Paul Williams' [DEC parser state machine](https://vt100.net/emu/dec_ansi_parser):
  tmux in `input.c`, zellij through the `vte` crate that alacritty uses.
  The parser drives a grid model (tmux's `grid.c`/`screen.c`/`screen-write.c`, zellij's `Grid`).
  That model holds rows of styled cells, scrollback, the cursor, and the mode flags that change input encoding:
  DECCKM, bracketed paste, mouse tracking, and focus events.
- **The alternate screen.**
  `?1049` swaps in a second grid that never feeds scrollback.
  This is how vim and less leave the shell's screen intact.
- **Rendering.**
  zellij tracks dirty lines per pane and debounces renders (1 ms of quiet, at most 8 ms).
  tmux mirrors simple operations, such as a scroll, onto the outer terminal with scroll regions,
  and otherwise redraws regions.
  When a client falls behind, tmux drops the queued output and redraws, rather than queueing frames.
- **Input is re-encoded, not passed through.**
  tmux parses outer input into its own key codes, looks each key up in the current key table
  (`root`, or `prefix` after the prefix key), and re-encodes anything unbound for the pane from that pane's modes.
  zellij forwards the raw bytes, patched for the pane's modes.
  Mouse events reach the pane only if it enabled tracking, translated to pane-relative coordinates.
- **Queries.**
  Programs ask their terminal things: cursor position (`CSI 6 n`), device attributes (DA1, DA2), the version (XTVERSION).
  The multiplexer answers almost all of them from its own state, because it _is_ the program's terminal.
  It forwards only what it can't know, such as palette colors and clipboard reads, to the outer terminal.
  Forwarding needs ordering machinery: tmux queues later replies behind the outstanding one,
  and zellij pauses the pane and uses a DA query as a barrier.
- **Lifecycle.**
  The child runs in its own session with the PTY as its controlling terminal (setsid + `TIOCSCTTY`).
  A resize is `ioctl(TIOCSWINSZ)` on the master, which sends the child `SIGWINCH`.
  Closing the master hangs up the session.

## Phase 2: Emulator

A terminal emulator's grid model turns the bytes a program writes into what a terminal shows:
rows of styled cells, scrollback, a cursor, and the modes that change how input is encoded.
This phase puts one behind `Emulator`, a place that only `emulator.py` touches, which produces immutable `Screen` values,
and adds the painter that draws them.
It runs no programs: its tests feed it bytes.

### Choosing an emulator

The grid model is the part not to write.
Several are libraries that take bytes in and hand out cells, a cursor and modes:

| Emulator | From Python | Throughput (measured here) | Notes |
| --- | --- | --- | --- |
| [pyte](https://github.com/selectel/pyte) 0.8.2 | pure Python | 0.25 to 0.85 MB/s | no alternate screen, no key encoding, last release 2023 |
| [libghostty-vt](https://ghostty.org) via [pyghostty](https://github.com/AnswerDotAI/pyghostty) 0.1.3 | cffi, prebuilt library | 52 to 470 MB/s | dirty rows, key/mouse/paste encoders, answers queries |
| alacritty_terminal, vt100, wezterm-term, libvterm | Rust/C, no maintained Python binding | n/a | the usual bases for a PyO3 binding |

At pyte's speed, `cat` of a 5 MB log freezes the pane for about nine seconds.
[textual-terminal](https://github.com/mitosch/textual-terminal), which embeds pyte in Textual, is a catalogue of what goes wrong:
it rebuilds every row as Rich text on every read, drops UTF-8 split across reads,
always sends application-mode cursor keys, and never answers DA or CPR.

libghostty-vt fits best.
It is Ghostty's core, has the fidelity of a real terminal, and its API was designed for this kind of embedding.
That API covers dirty rows with stable ids, key, mouse, paste and focus encoders that read the terminal's modes,
reply callbacks, and color callbacks.
The cost is supply chain:

- `pyghostty` has had three releases since July 2026, the latest 0.1.3.
- It bundles a prebuilt `libghostty-vt` from a pinned Ghostty revision, and libghostty-vt is pre-1.0.
- It is cffi in ABI mode: no compiler at install time, but no type information, and several calls per cell.

Phase 4 adds a requirement the spike didn't test: reading scrollback with its styles.
A transcript is everything a program printed, and most of a long one has scrolled off the screen by the time the program exits.
pyghostty 0.1.3 keeps scrollback (`Terminal(scrollback=10000)`), but its only reader is `contents()`, which returns plain text.
The spike reads styled cells through libghostty's render state, which covers the active screen.
Whether libghostty-vt's C API reaches styled scrollback rows, so that pyghostty's `lib` can read them as the spike reads the screen,
needs checking.
If it doesn't, this requirement decides for an owned binding.

The alternative fits counterweight's own pattern.
waxy is PyO3 bindings to taffy, and the same could wrap an emulator crate
(`libghostty-rs`, `alacritty_terminal`, or `vt100`).
The binding would expose a snapshot that returns whole rows as Python tuples in one call.
That removes the 3 to 10 ms snapshot cost (see [Snapshots](#snapshots))
and gives typed stubs, at the price of building and maintaining another binding.
I'd keep the `Emulator`/`Screen` boundary either way: nothing outside `emulator.py` touches the emulator.

### Snapshots

A snapshot shares unchanged rows.
`Screen` compares by identity, so a `Canvas` redraws only when the program's output changed.
The emulator keeps each converted row by libghostty's row id while it isn't dirty.
Unstyled cells are cached by their raw 64-bit value,
which holds only a codepoint and a width when the cell has no style.
A styled cell's raw value holds a page-local style id, so those can't be cached.

Reading cells through cffi costs several calls per cell, and that is the bottleneck.

These are medians on a 120×40 screen after one line scrolls, when libghostty marks every row dirty:

| Output | Snapshot |
| --- | --- |
| plain text | 2.8 ms |
| every line colored | 10.5 ms |
| nothing changed | 0.1 ms |

### The screen painter

The screen painter draws a `Screen`, with the cursor as a reversed cell when asked (see [Fidelity](#later-fidelity)).
It lives in `counterweight.painters.terminal`, and phase 4's transcript painter joins it there.
The box sizes the terminal rather than the other way round,
so it is a painter with no natural size (see [Sizing](#sizing)).
It leaves a program's default colors unset, so they follow the canvas's `text_style`.

Paint adds a wide grapheme's continuation cell, and `StyledGrapheme(grapheme="")` raises,
so the screen painter drops libghostty's spacer tails.
A row then has one entry per grapheme, not per column,
so drawing the cursor maps its column to an index rather than indexing the row by `cursor.x`,
which would put it on the wrong cell after any wide character on its line.

Paint measures each grapheme with counterweight's own `grapheme_width`, not libghostty's,
and the program laid its line out by libghostty's.
Where the two disagree (an emoji with a variation selector, a character newer than one of the width tables),
the rest of the line would shift by a column, and paint drops a cluster it measures as zero wide, shifting it back.
So the screen painter keeps one column per libghostty column:
a cell libghostty draws two wide that `grapheme_width` measures as one gets a space after it,
and a cell it draws one wide that `grapheme_width` measures as zero or two is drawn as a space.

### Phase 2 work

1. Choose between `pyghostty` and an owned binding, against styled scrollback as well as what the spike needed,
   and add the dependency.
2. `Emulator` and `Screen`, ported from the spike, with bounded color and style caches:
   the spike's module-level `_STYLES` and per-emulator `colors` grow with every truecolor value a program prints.
3. The screen painter, keeping libghostty's column widths where `grapheme_width` disagrees.
4. Tests that feed bytes (colors, wide characters and width disagreements, the alternate screen, scrolling, query replies),
   and a benchmark of snapshot cost.

## Phase 3: Pseudo-terminals

`use_pty` runs a program on a pseudo-terminal while its component is mounted, and hands back the bytes the program writes.
It knows nothing about emulators or painters, so it can be written alongside phases 1 and 2.

- **The program's terminal.**
  The child runs in its own session with the PTY as its controlling terminal,
  and a resize is `ioctl(TIOCSWINSZ)` on the master (see [Lifecycle](#background-how-terminal-multiplexers-work)).
  Cancelling the effect hangs the program up, sending `SIGHUP` to its process group, as closing a terminal window does.
  A program can ignore `SIGHUP` (`nohup`, `trap '' HUP`), so if its group is still running after a grace period
  (a knob, one second by default), it gets `SIGTERM`, and then `SIGKILL` after another,
  so that no program outlives the effect that ran it.
- **Writes never block.**
  Bytes the program isn't reading yet are buffered and flushed when the master is writable,
  so a handler that writes never blocks the event loop.
- **Standard input.**
  An interactive program reads its keys from the PTY.
  A one-shot run (phase 4) gives the program `/dev/null` instead, so `run_pty` takes the choice.
  The child then can't make its controlling terminal from standard input, as the spike's `make_controlling_terminal` does
  (`TIOCSCTTY` on fd 0): on `/dev/null` that fails with `ENOTTY`, so every one-shot spawn would fail.
  It uses standard output, which is the PTY either way.
- **The environment.**
  A program gets the environment the app started with, the hook's defaults over that, and the caller's `env` over those:
  `os.environ | defaults | env`, with later layers winning.
  The defaults say what terminal the program is on (`TERM=xterm-256color`, `COLORTERM=truecolor`),
  phase 4 adds its pager defaults, and a caller changes any of them through `env`.
  Inheriting is the default because a program run without `PATH`, `HOME` or a locale rarely does what anyone wants.
  Python's `subprocess` and Node's `spawn` replace the whole environment when given one,
  which makes every caller write `os.environ | ...` and leaves no layer for defaults.
  Deno's `Command` merges `env` over the inherited environment, and takes `clearEnv` to start from nothing.
  The hooks follow Deno, with `clear_env=True` to drop the inherited layer,
  so a docs screenshot doesn't depend on the environment of whoever generated it.
  `env` can only add or override, so removing one inherited variable means `clear_env` and passing the rest.
- **The size comes from the PTY, not the environment.**
  The inherited layer drops `COLUMNS` and `LINES`, which describe the terminal the app was started from.
  Some programs read them before asking the terminal:
  Python's `shutil.get_terminal_size` does, so an inherited `COLUMNS=200` on a 77-column PTY formats for 200.
  Setting them to the PTY's size would be right only until the embed resizes,
  after which they'd be stale and still win, so the hooks leave the size to the PTY alone.

The spike's `use_pty` needs hardening:

- EOF and exit together (tmux's `window_pane_destroy_ready`), and grandchildren that hold the PTY open.
  The spike's drain re-raises its `TimeoutError` out of the effect,
  and an effect's exception ends the app's task group,
  so a shell that exits leaving a background job on the PTY quits the whole app, and its exit status is never set.
- A spawn that fails (an `argv` that doesn't exist) closes both PTY fds and reports the failure as the hook's state,
  rather than raising out of the effect with the fds leaked.
- The program starts at its real size.
  `use_rects` is zero on the first render, so the spike spawns at 0×0,
  and a resize that arrives while `create_subprocess_exec` is still awaited finds no connection and is dropped,
  leaving the program at 0×0 until the pane's size next changes.
  Applying the latest size on connect closes that gap.
- The spike hardcodes `TERM` and `COLORTERM` over the inherited environment, and passes `COLUMNS` and `LINES` through;
  the environment's layers above replace that.

### Phase 3 work

1. `run_pty` and `use_pty`, with the choice of standard input, the environment's layers, and the hardening above.
2. Tests against real programs:
   output, an exit status, a background job that holds the PTY open, an `argv` that doesn't exist, a resize,
   standard input on `/dev/null`, cancelling a program that ignores `SIGHUP`,
   and the environment (a default overridden by `env`, `clear_env`, and an inherited `COLUMNS` dropped).

## Phase 4: One-shot commands

A one-shot command runs a program that's expected to exit, though not necessarily to succeed,
and shows everything it printed, colors and all, as a terminal would have shown it.
A presentation can run an example command on a slide,
and an editor can run the code in a text area and show what it printed.
This is the first feature of the stack that ships.
It needs phases 1 to 3 but none of phase 5, since it takes no input and holds no focus.

### Why a terminal, not pipes

Pipes are simpler, and they keep stdout and stderr apart.
However, they lose what this feature is for:

- **Colors.**
  Most programs color their output only when `isatty(stdout)` is true.
  `FORCE_COLOR` and `CLICOLOR_FORCE` work tool by tool, not everywhere.
- **Cursor movement.**
  Progress bars rewrite their line with `\r`, and live displays (rich, tqdm) move the cursor up and redraw.
  Run through an emulator, the transcript shows what the program left on the screen.
  Turning only the color codes into styled text would show every frame of a progress bar on one garbled line.

So a run gets a pseudo-terminal and an emulator, and its stdout and stderr arrive interleaved, as they do in a terminal.
A hook that runs a program on pipes, for a caller that must tell the streams apart, needs no emulator and is outside this plan.

The program sees a terminal, so it acts as it would on one:

- Standard input is `/dev/null`, so a program that reads input gets end of file rather than waiting.
- `git log` and other commands start a pager, which waits for keys that never come,
  so the hook adds `PAGER=cat` and `GIT_PAGER=cat` to its defaults, which `env` can override
  (see [the environment](#phase-3-pseudo-terminals)).
  `PAGER` alone isn't enough for git, which prefers `GIT_PAGER` and the user's `core.pager` over it.
  Other tools read their own variables (`MANPAGER`, `SYSTEMD_PAGER`), so the timeout stays the backstop.
- Queries (CPR, DA) are answered from the emulator and written back to the PTY, as in the embed,
  so a program that asks its terminal something doesn't wait for a reply.
- Anything else that waits ends when the run is cancelled or times out.

### How the web shapes it

The closest web answer is a `fetch` whose body streams, run through React Query's hooks:

- `useQuery` runs when its component mounts, and again when its key changes:
  a slide that runs its command when shown.
- `useMutation` runs on an event, through `mutate()`, and exposes the latest run's status and result:
  an editor that runs its code on a key press.
- An `AbortController` cancels a request, and `AbortSignal.timeout` bounds one.

A query is a mutation started by an effect keyed on its inputs, but a mutation can't be built from a query,
so the hook takes the mutation's shape and the slide's case is an effect on top of it.
It differs from `fetch` in two ways.
The result streams, so a run shows its output so far while the program is still running.
A program that exits with a failing status is a result like any other, not an error.

### The run

```python
@dataclass(frozen=True, slots=True)
class Running: ...


@dataclass(frozen=True, slots=True)
class Exited:
    status: int  # negative for a signal, as asyncio reports it


@dataclass(frozen=True, slots=True)
class FailedToStart:
    reason: str  # the OSError's message, such as "No such file or directory"


@dataclass(frozen=True, slots=True)
class Cancelled: ...


@dataclass(frozen=True, slots=True)
class TimedOut: ...


type Outcome = Running | Exited | FailedToStart | Cancelled | TimedOut


@dataclass(frozen=True, slots=True)
class CommandRun:
    argv: tuple[str, ...]
    output: Transcript  # a Painter, sized (columns, lines)
    outcome: Outcome


@dataclass(frozen=True, slots=True)
class Command:
    run: Callable[[Sequence[str]], None]  # starts a run, cancelling one in progress
    cancel: Callable[[], None]
    latest: CommandRun | None


def use_command(
    columns: int,
    rows: int = 24,
    env: Mapping[str, str] | None = None,
    clear_env: bool = False,
    timeout: timedelta | None = None,
    max_lines: int = 10_000,
) -> Command: ...
```

A finished run is a value that outlives its program,
so a component can keep it in state, show it again, or show it beside the next run.
A slide runs its command when it's shown:

```python
viewport, _ = use_state(ElementHandle)
command = use_command(columns=use_rects(viewport).content.width)


async def start() -> None:
    command.run(argv)


use_effect(start, deps=(tuple(argv),))
```

The widget that shows the run takes `viewport` for its `scroll_area`,
so `use_rects(viewport)` measures the box the transcript fills (see [Measuring the box](#measuring-the-box)).

- **`run` records a request in state, and an effect keyed on the request runs it.**
  Cancelling, starting another run, and unmounting all end that effect, which hangs the program up.
- **Cancelling is a key the app binds**, such as Escape.
  Until phase 5's raw input mode, Ctrl+C quits the whole app,
  and it never reaches the program, which runs in its own session.

### How a run is sized

A run has two sizes, and only the first comes from its box.
The PTY's size is what the program formats its output for, and is fixed for the run.
The transcript's size is how much the program has printed, and grows while it runs.

```text
the box's content width, when the run starts ──> columns ──┐
rows, a knob (24) ─────────────────────────────> rows ─────┴──> the PTY, which the program formats for
                                                                  │ output, through the emulator
                                                                  v
                                       Transcript: natural size (columns, lines printed)
                                                                  │
                                                                  v
              Canvas: width from its parent, height = lines ──> scroll_area: shows what fits, scrolls the rest
```

- **`columns` is the PTY's width, read when the run starts.**
  The program lays its output out for it (wrapping, tables, progress bars),
  and a run requested before the box has a width (`use_rects` is zero on the first render) waits for one.
  So the box has to take its width from its parent (a stretch, `fill`, or a styled width), never from its content:
  the transcript's natural width is the run's `columns`, so a box sized by its content stays zero wide
  and the run never starts.
  The widget's docs say so.
  A later resize doesn't rewrap the transcript: columns past the box's edge are clipped,
  and running again at the new width is the caller's choice.
- **`rows` is the PTY's height**, which the program sees and the transcript doesn't:
  what a live display sizes itself to, and how tall a program that moves the cursor around its screen can draw.
  The transcript holds scrollback and the screen alike, so `rows` doesn't bound its height.
  It defaults to 24, a fresh xterm's height, rather than the box's height,
  because the transcript scrolls in its box, so the box isn't the program's screen.
- **The transcript's height is the lines printed.**
  Its natural size is `(columns, lines)`, where `lines` counts scrollback then the screen,
  with trailing blank rows dropped and at most `max_lines`.
  Its canvas takes that height (the transcript keeps no aspect ratio, so a wider box doesn't make it taller),
  and the `scroll_area` shows as many rows as fit and scrolls the rest, following the end while the program runs.

#### Measuring the box

`use_rects()` reports the calling component's own top element,
but the box the transcript fills is the widget's `scroll_area`, a component of its own.
So `use_rects` takes an optional handle, as `use_scroll` already does:
`use_rects(handle)` reports the rects of the element that `handle` names,
and `use_rects()` keeps reporting the caller's own top element.
This is the web's answer: React measures an element through a ref and a `ResizeObserver`,
not through the component's own root.

It follows `use_scroll(handle)` in the details too:

- A handle that named no visible element in the previous render reports the initial rects (all zero),
  so a run requested before the widget mounts waits for its width, as it does on the first render.
- The caller records the rects it read per handle, as `use_scroll` records scrolls,
  and renders again when any of them move.
- The handle comes from `use_state(ElementHandle)`, and the widget passes it on to its `scroll_area` as `viewport`.

Without it, the slide example would measure the right box only when the widget was all that the calling component rendered.
A fixed width, such as 80 with the box scrolling sideways, needs no new API: it's `columns=80`.

### Output: places in the effect, values in the render

The emulator is mutable (a place).
It lives only inside the run's effect, which feeds it on the event loop as the PTY becomes readable.
Rendering only ever sees `CommandRun` values.
The embed in phase 6 feeds its emulator the same way.

- **Parse on read.**
  `loop.add_reader` on the master fd reads up to 64 KiB and feeds the emulator immediately.
  Since nothing is read faster than it's parsed, unparsed bytes never pile up.
  When the app falls behind, the kernel's PTY buffer fills and blocks the child,
  which is the backpressure tmux gets by disabling `EV_READ`.
- **Snapshot at most once per frame.**
  A read schedules a snapshot at most every `SNAPSHOT_INTERVAL` (1/60 s).
  The snapshot sets state, which re-renders the component.
  This is the coalescing zellij (8 ms), neovim (10 ms) and wezterm (3 ms) do.
  In the spike's multiplexer, `seq 1 300000` took 0.18 s of wall time, and the UI stayed responsive.
- **The transcript is scrollback, then the screen**, with trailing blank rows dropped.
  A run's terminal never resizes, so a row that has scrolled into scrollback doesn't change again,
  and the transcript converts each row once.
  A snapshot then costs the screen plus whatever scrolled since the last one.
  A runaway `yes` would grow the transcript without bound, so it keeps the last `max_lines` rows.
  The emulator's scrollback has to hold what a run prints between two snapshots, which a timed snapshot doesn't bound:
  `seq 1 300000` printed about 27,000 lines a frame in the spike.
  So the emulator keeps at least `max_lines` rows of scrollback.
  Anything that scrolls off it before a snapshot is then older than the last `max_lines` rows,
  which the transcript would have dropped anyway, so no gap opens in its middle.
- **The transcript is a painter with a natural size**, `(columns, lines)`,
  so it sizes its `Canvas` as an image does, and a `scroll_area` scrolls through it.
- **Recorded output.**
  Building a transcript from bytes is a function from a value to a value,
  so `Transcript.of(output, columns, rows)` renders output captured ahead of time the same way, with no program run.
  A slide can show a command's output without running it, and docs screenshots stay deterministic.

### Phase 4 work

1. `use_rects(handle)`, with tests and docs alongside `use_scroll(handle)`'s.
   It stands alone, so it can land first.
2. `Transcript`, in `counterweight.painters.terminal`, with `Transcript.of` for recorded output.
3. `use_command` and its `CommandRun` values, with cancelling, the timeout, `max_lines`
   (and scrollback to match), the pager defaults, and `clear_env`.
4. A widget that shows a run's transcript in a `scroll_area` that follows its end while the program runs,
   with its outcome beneath, taking the `viewport` handle its caller measures.
5. Examples: a slide that runs a command when shown, and a code runner that runs a `text_area`'s Python on a key press.
   Docs with screenshots from `docs/examples/`, drawn from recorded output through `Transcript.of`.
6. Tests against real programs (colors, a progress bar's last frame, a failing status, a program that doesn't exist,
   cancelling and timing out a program that sleeps, and the pager defaults), to 100% coverage,
   and a mutation testing pass over the new code.

## Phase 5: Framework fixes for the embed

The spike hit these limits in counterweight itself, which a multiplexer can't work around.
Each is also useful to apps that never embed a terminal.
Nothing before phase 6 needs them, so this phase can land any time before it.

1. **Ctrl+C quits the host.**
   `start_input_control` turns off `ECHO` and `ICANON` but leaves `ISIG` and `IXON` on.
   So Ctrl+C is a `SIGINT` that quits the app, Ctrl+Z (`SIGTSTP`) stops it, Ctrl+\\ is `SIGQUIT`,
   and Ctrl+S/Ctrl+Q are eaten as flow control.
   None of them can reach an embedded program.
   The spike's test session died this way.
   An app that hosts terminals needs a raw input mode, which tmux puts its outer tty in: a knob on `app()`,
   with Ctrl+C then arriving as a key the app can bind to `Quit`,
   or that a code runner (phase 4) can bind to cancel a run.
2. **`FocusOn` can't focus a component that mounts in the same update.**
   The routing table doesn't know the new handle yet, so the control is dropped.
   The spike's multiplexer works around it with `ClearFocus` and `auto_focus`.
   React's answer is an effect after mount that calls `ref.focus()`.
   Counterweight's effects can't return controls, so this needs either a pending `FocusOn` that applies after the render
   that mounts its target, or a way for an effect to send a control.
3. **A mode that changes routing must be readable synchronously.**
   `Ctrl+B %` in one read arrives as two key presses handled before the next render,
   so the second handler saw `is_armed=False` from its closure and sent `%` to the shell.
   The prefix state has to live in a `use_ref`, with state alongside only to re-render.
   `use_text_input` hits the same thing and solves it with updater functions.
   This needs a documented pattern, since every modal key handler (vim-style modes, chords) hits it.

## Phase 6: Embedding terminals

The embed runs an interactive program in a pane:
it shows the screen as the program draws it, and routes keys, pastes and mouse events to the program.

### The layers

```text
Canvas(painter=ScreenView(screen, show_cursor))         element (phase 1): paints the snapshot, no text layout
  ^
use_terminal(argv, columns, rows) -> EmbeddedTerminal   headless (phase 6): emulator, snapshots, input forwarding, focus
  ^
use_pty(argv, columns, rows, on_output) -> Pty          headless (phase 3): PTY, child process, writes, resize, exit status
  ^
Emulator (place) -> Screen (value)                      emulator.py (phase 2): the only module that knows about the emulator
```

`use_command` sits on the same two lower layers, beside `use_terminal`.

The embed needs no element of its own:
a component calls `use_terminal`, measures its own content box with `use_rects`, and returns a `Canvas`.
From the spike's [`examples/multiplexer.py`](#examplesmultiplexerpy), which predates the `Painter` protocol:

```python
@component
def pane(pane_id: int, prefix: InputHandler, handle: FocusHandle, on_title: Callable[[str], None]) -> Canvas:
    content = use_rects().content
    terminal = use_terminal(SHELL, content.width, content.height, auto_focus=True, handle=handle)
    ...
    return Canvas(draw=terminal.view, style=fill(1) | border | ..., on_input=first(prefix, terminal.on_input))
```

### Output and resizing

The emulator is fed and snapshotted as phase 4 feeds it (see [Output](#output-places-in-the-effect-values-in-the-render)),
except that the snapshot is the screen rather than a transcript.

The pane's size feeds back into the program's terminal size.
`use_rects` reports last frame's box, and an effect keyed on `(columns, rows)` resizes the PTY and the emulator.
So a resize shows the old screen, cropped or padded, for one frame, as tmux does.

### Input: when keys reach the program

The embed is a focusable component.
Its `on_input`, while focused, sends the program every key press and paste it can encode and claims them,
so nothing bubbles past it.

- **Keys** are re-encoded, as tmux does, rather than passed through, which counterweight couldn't do anyway:
  its input parser has already turned bytes into `KeyPressed`.
  `input_encoding.KEY_SEQUENCES` inverts `input_parsing`'s own tables, so the encoder and parser can't drift.
  Every `Key` round-trips through encode and parse, except `ctrl+h`, `ctrl+i` and `ctrl+m`
  (which terminals send as Backspace, Tab and Enter) and `shift+escape`.
  `alt+space` needs its own case, `ESC` then a space:
  `Key.Space`'s value is `" "`, so the spike's Alt rule looks up `space`, finds nothing, and drops the key.
  Cursor keys switch to `SS3` under DECCKM, which vim exercised.
  Where a key has several spellings, the encoder picks the one xterm sends, which is what `TERM=xterm-256color` promises:
  F1 to F4 are `SS3 P` to `SS3 S`, and Shift+F1 to F4 are `CSI 1 ; 2 P` and so on.
  The spike's rule (`CSI` over `SS3`, then the shorter `CSI`) sends `CSI 11 ~` for F1 and `CSI 25 ~` for F13,
  which xterm's terminfo doesn't list, so htop's F1 to F4 do nothing.
- **Pastes** are wrapped in bracketed-paste markers when the program set `?2004`,
  with every end marker in the text removed, so a paste can't end itself early.
  Removal repeats until none is left: one pass of `replace` turns `ESC [ 20 ESC [ 201 ~ 1 ~` into an end marker.
- **Mouse events** inside the canvas are encoded only if the program enabled tracking,
  filtered by its tracking level, and translated to pane-local coordinates, as SGR or X10.
  A press also focuses the pane.
  A press outside the program's screen (on the pane's border or padding) only focuses it:
  the spike encodes it too, sending the program a column or row of 0 or past its edge.
  Counterweight's press capture already does what terminals expect of a drag:
  the pane that claimed the press gets its motion and release, wherever the pointer goes.
- **The prefix key.**
  The DOM would intercept with a capture-phase listener on an ancestor.
  Counterweight only bubbles from the focused node, and that turned out not to matter:
  the multiplexer puts its prefix handler before the terminal's with `first(prefix, terminal.on_input)`.
  The embed exposes its handler, and composition does the rest.
- **Queries** are answered by libghostty from emulator state, and the replies are written back to the PTY.
  This covers CPR, DA1, DA2 and the other queries a multiplexer answers from its own state.
  Forwarding to the outer terminal is deferred: it has several plausible designs, and nothing has needed it yet.

### What the spike verified

These checks ran `examples/multiplexer.py` inside a detached tmux session,
driving it with `send-keys` and reading the screen with `capture-pane`:

- bash with a starship prompt, colors, CJK and emoji widths.
- `Ctrl+B %` split: both shells resized to 48×17 (`tput`), and the left prompt reflowed.
- `Ctrl+B o` moved focus between panes, and a click focused the pane clicked.
- vim: arrow keys, insert mode, Escape, and `:wq` (the file was written).
  The shell's screen came back when vim left the alternate screen.
- htop drew in a pane, and resizing the outer window resized each program.
- `exit 3` showed `exited 3` in the status bar.
- A press, drag and release reached a raw-mode program as
  `\x1b[<0;20;7M`, `\x1b[<32;22;7M`, `\x1b[<0;22;7m`: pane-local, 1-based, button tracking.
- The app idled at 0.6% CPU with two shells open.

### Phase 6 work

1. `input_encoding`: key presses, pastes and mouse events back to the bytes a terminal sends,
   with xterm's spellings for F1 to F4, `alt+space`, and a press outside the program's screen only focusing the pane.
2. `use_terminal`, ported from the spike onto phases 2 and 3,
   using phase 5's fixes to drop the multiplexer's `ClearFocus` and closure-state workarounds.
   The multiplexer's `%` split reads `next_id` from its closure,
   so two splits in one read open two panes with the same id and key.
   The new id comes from the updater instead.
3. Send focus events: `CSI I`/`CSI O` under `?1004` when the embed gains and loses focus,
   with an effect keyed on `focus.is_focused`.
4. A `terminal` widget on top of `use_terminal`, with tests, docs, and the multiplexer as an example.

## Later: fidelity

The embed and one-shot commands work without these,
but each makes a program's output look, or the program behave, less like it does in a real terminal.

1. **Colors are truecolor only.**
   `Color` is RGB, so a program's palette indices are resolved to libghostty's default palette.
   Its "default" foreground and background are left unset, so they follow the canvas's `text_style`,
   but that is RGB too.
   An embedded `ls --color`, and one in a transcript, uses xterm's red, not the user's theme's red.
   tmux keeps palette indices and default colors through to the outer terminal.
   Fixing this means `Color` gaining palette and default variants, and `output.py` emitting them.
   Since transcripts show it too, it could land before phase 6.
2. **The cursor is drawn, not placed.**
   Counterweight hides the real cursor, so the terminal painter draws a reversed cell.
   That loses cursor shapes (DECSCUSR), blinking, and the position input methods read.
   A framework way for the focused element to place the real cursor would serve `use_text_input` too.
3. **The key model is legacy.**
   `KeyPressed` can't represent what the kitty keyboard protocol adds
   (Ctrl+Shift+letter, key release, Ctrl+I distinct from Tab), so neither can the embed's encoder.
   libghostty's key encoder could produce kitty encodings once the input side carries the information.

## Appendix: the spike code

The spike's code, kept here as a reference for writing each phase.
Changed files are diffs against `main`; added files are in full.

### Canvas (phase 1)

#### `src/counterweight/elements.py`

````diff
diff --git a/src/counterweight/elements.py b/src/counterweight/elements.py
index 398c142..d586c78 100644
--- a/src/counterweight/elements.py
+++ b/src/counterweight/elements.py
@@ -1,8 +1,9 @@
 from __future__ import annotations

+from collections.abc import Callable, Sequence
 from dataclasses import dataclass, field
 from functools import lru_cache
-from typing import Union
+from typing import TYPE_CHECKING, Union

 from counterweight._utils import flyweight
 from counterweight.events import InputHandler
@@ -11,6 +12,9 @@ from counterweight.graphemes import grapheme_width, graphemes, visible
 from counterweight.styles import CellStyle, Style
 from counterweight.styles.styles import _DEFAULT_CELL_STYLE

+if TYPE_CHECKING:
+    from counterweight.paint import Cell
+
 _DEFAULT_STYLE = Style()


@@ -81,9 +85,43 @@ class Text:
         return text_cells(self.content, self.style.text_style)


+# Rows of cells, top to bottom, each drawn left to right from the left edge of a canvas's content box.
+type Rows = Sequence[Sequence[Cell]]
+
+
+@dataclass(frozen=True, slots=True, kw_only=True)
+class Canvas:
+    """
+    A leaf element that paints its content box itself, instead of laying out text.
+
+    After layout, `draw` is called with the width and height of the content box and returns the rows of cells
+    to put there. Rows (or cells in a row) past the box overflow it, as a `Text`'s do, for the clip to cut off,
+    and a box it leaves short shows the background beneath it.
+
+    `draw` must be pure, since its rows are cached by `(draw, width, height)`:
+    a frozen dataclass with a `__call__` that is equal from one render to the next is drawn once,
+    while a new closure each render is drawn every frame.
+
+    Like HTML's `<canvas>`, a `Canvas` is sized by its style, and `width` and `height` give its
+    intrinsic size, which it takes on each axis its style leaves `auto`. Without them, its intrinsic size is 0.
+    """
+
+    draw: Callable[[int, int], Rows]
+    width: int = 0
+    height: int = 0
+    style: Style = _DEFAULT_STYLE
+    on_input: InputHandler | None = None
+    handle: ElementHandle | None = None
+
+    @property
+    def children(self) -> tuple[Component | AnyElement, ...]:
+        return ()
+
+
 AnyElement = Union[
     Div,
     Text,
+    Canvas,
 ]

 from counterweight.components import Component  # noqa: E402, deferred to avoid circular import
````

#### `src/counterweight/layout.py`

````diff
diff --git a/src/counterweight/layout.py b/src/counterweight/layout.py
index 0bb9c2a..98dddab 100644
--- a/src/counterweight/layout.py
+++ b/src/counterweight/layout.py
@@ -10,7 +10,7 @@ from typing import TYPE_CHECKING, assert_never
 import waxy

 from counterweight.controls import ScrollAlignment, ScrollBy, ScrollIntoView, ScrollTo
-from counterweight.elements import AnyElement, Chunk, Div, StyledGrapheme, Text, text_cells
+from counterweight.elements import AnyElement, Canvas, Chunk, Div, StyledGrapheme, Text, text_cells
 from counterweight.geometry import Position, Rects, Region, Scroll
 from counterweight.graphemes import LINE_BREAKS
 from counterweight.styles.styles import CellStyle, ClipTo, ResolvedStyle, Style, TextWrap
@@ -43,11 +43,33 @@ def text_source(text: Text) -> TextSource:
     return content, text.style.text_style, text.style.resolved.text_wrap


+@dataclass(frozen=True, slots=True)
+class IntrinsicSize:
+    """A `Canvas`'s intrinsic size, which it takes on each axis its style leaves `auto`, as a replaced element does."""
+
+    width: int
+    height: int
+
+
+type LeafSource = TextSource | IntrinsicSize
+
+
+def leaf_source(leaf: Text | Canvas) -> LeafSource:
+    """Everything a leaf's measured size depends on: its text, or its intrinsic size."""
+    match leaf:
+        case Text():
+            return text_source(leaf)
+        case Canvas():
+            return IntrinsicSize(leaf.width, leaf.height)
+        case _ as unreachable:
+            assert_never(unreachable)
+
+
 @dataclass(frozen=True, slots=True)
 class CreateLeaf:
     key: NodeKey
     style: waxy.Style
-    text: TextSource
+    text: LeafSource


 @dataclass(frozen=True, slots=True)
@@ -66,7 +88,7 @@ class SetStyle:
 @dataclass(frozen=True, slots=True)
 class SetText:
     key: NodeKey
-    text: TextSource
+    text: LeafSource


 @dataclass(frozen=True, slots=True)
@@ -133,16 +155,16 @@ def _reconcile(
     # Taffy discards a node's cached layout when its text or children are set, even to equal values,
     # so each is set only when it changed.
     match element:
-        case Text():
-            source = text_source(element)
+        case Text() | Canvas():
+            source = leaf_source(element)
             if previous is None:
                 changes.append(CreateLeaf(key=key, style=style, text=source))
                 return

             _append_style_change(previous, key, style, changes)
             match previous.element:
-                case Text() as previous_text:
-                    if text_source(previous_text) != source:
+                case Text() | Canvas() as previous_leaf:
+                    if leaf_source(previous_leaf) != source:
                         changes.append(SetText(key=key, text=source))
                 case Div():
                     for child in previous.children:
@@ -164,7 +186,7 @@ def _reconcile(

             _append_style_change(previous, key, style, changes)
             match previous.element:
-                case Text():
+                case Text() | Canvas():
                     changes.append(ClearText(key=key))
                     changes.append(SetChildren(key=key, children=child_keys))
                 case Div():
@@ -302,7 +324,7 @@ class LayoutTree:
     Only `apply` and `compute` read or write its taffy nodes.
     """

-    tree: waxy.TaffyTree[MeasurableText] = field(default_factory=waxy.TaffyTree)
+    tree: waxy.TaffyTree[MeasurableText | IntrinsicSize] = field(default_factory=waxy.TaffyTree)
     nodes: dict[NodeKey, waxy.NodeId] = field(default_factory=dict)

     def compute(
@@ -351,13 +373,13 @@ class LayoutTree:
         for change in changes:
             match change:
                 case CreateLeaf(key=key, style=style, text=text):
-                    nodes[key] = tree.new_leaf_with_context(style, MeasurableText.of(text))
+                    nodes[key] = tree.new_leaf_with_context(style, measurable(text))
                 case CreateContainer(key=key, style=style, children=children):
                     nodes[key] = tree.new_with_children(style, [nodes[child] for child in children])
                 case SetStyle(key=key, style=style):
                     tree.set_style(nodes[key], style)
                 case SetText(key=key, text=text):
-                    tree.set_node_context(nodes[key], MeasurableText.of(text))
+                    tree.set_node_context(nodes[key], measurable(text))
                 case ClearText(key=key):
                     tree.set_node_context(nodes[key], None)
                 case SetChildren(key=key, children=children):
@@ -421,7 +443,7 @@ def place(
         style = node.element.style
         scrolls_x, scrolls_y = scrolled_axes(style)
         if scrolls_x or scrolls_y:
-            if isinstance(node.element, Text):
+            if isinstance(node.element, Text | Canvas):
                 raise ValueError(
                     "A Text doesn't scroll its own text, so its overflow can't be Scroll: "
                     "put it in a Div whose overflow is Scroll, which scrolls it."
@@ -750,14 +772,27 @@ class MeasurableText:
         return self.min_content_width


+def measurable(source: LeafSource) -> MeasurableText | IntrinsicSize:
+    """What a leaf's layout node holds for `_measure_text` to size it by."""
+    if isinstance(source, IntrinsicSize):
+        return source
+    return MeasurableText.of(source)
+
+
 def _measure_text(
     known: waxy.KnownSize,
     available: waxy.AvailableSize,
-    context: MeasurableText,
+    context: MeasurableText | IntrinsicSize,
 ) -> waxy.Size:
     known_width = known.width
     known_height = known.height

+    if isinstance(context, IntrinsicSize):
+        return waxy.Size(
+            known_width if known_width is not None else float(context.width),
+            known_height if known_height is not None else float(context.height),
+        )
+
     width: int | None
     if known_width is not None:
         width = int(known_width)
````

#### `src/counterweight/paint.py`

````diff
diff --git a/src/counterweight/paint.py b/src/counterweight/paint.py
index e6d82be..f636eec 100644
--- a/src/counterweight/paint.py
+++ b/src/counterweight/paint.py
@@ -1,7 +1,7 @@
 from __future__ import annotations

 import logging
-from collections.abc import Iterable, Iterator, Sequence
+from collections.abc import Callable, Iterable, Iterator, Sequence
 from dataclasses import dataclass
 from functools import lru_cache
 from itertools import groupby
@@ -12,7 +12,7 @@ from xml.etree.ElementTree import Element, SubElement
 import waxy

 from counterweight._utils import flyweight, halve_integer
-from counterweight.elements import AnyElement, Div, StyledGrapheme, Text
+from counterweight.elements import AnyElement, Canvas, Div, Rows, StyledGrapheme, Text
 from counterweight.geometry import Position, Rects, Region
 from counterweight.layout import cells_width, child_clip, clipped_axes, wrap_cells
 from counterweight.styles.styles import (
@@ -286,9 +286,11 @@ def paint_element(

     match element:
         case Div():
-            lines: tuple[tuple[Cell, ...], ...] = ()
+            lines: Rows = ()
         case Text() as e:
             lines = text_lines(e.cells, style.text_wrap, style.text_justify, style.text_style, resolved.content.width)
+        case Canvas() as e:
+            lines = canvas_rows(e.draw, resolved.content.width, resolved.content.height)
         case _:
             assert_never(element)

@@ -309,6 +311,14 @@ def paint_element(
     return hints


+@lru_cache(maxsize=2**8)
+def canvas_rows(draw: Callable[[int, int], Rows], width: int, height: int) -> Rows:
+    """What a `Canvas` with `draw` paints in a `width` by `height` content box, cached because `draw` is pure."""
+    if width <= 0 or height <= 0:
+        return ()
+    return draw(width, height)
+
+
 @lru_cache(maxsize=2**12)
 def edge_fills(outer: Region, inner: Region, color: Color) -> tuple[Fill, ...]:
     """The parts of `outer` outside `inner`, as up to four strips filled with blank cells of `color`."""
````

#### `src/counterweight/utils.py`

````diff
diff --git a/src/counterweight/utils.py b/src/counterweight/utils.py
index f1b0af0..771fcdd 100644
--- a/src/counterweight/utils.py
+++ b/src/counterweight/utils.py
@@ -1,11 +1,13 @@
 from __future__ import annotations

+from dataclasses import dataclass, replace
 from functools import lru_cache

 from more_itertools import grouper

-from counterweight.elements import NEWLINE, Chunk
-from counterweight.styles.styles import CellStyle, Color
+from counterweight.elements import NEWLINE, Chunk, Rows
+from counterweight.paint import Cell
+from counterweight.styles.styles import CELL_STYLE_DEFAULTS, CellStyle, Color

 _BLACK = Color.from_name("black")

@@ -53,4 +55,41 @@ def canvas(
     return tuple(chunks)


-__all__ = ["canvas", "clamp"]
+@lru_cache(maxsize=2**12)
+def _half_block(top: Color, bottom: Color) -> Cell:
+    return Cell("▀", replace(CELL_STYLE_DEFAULTS, foreground=top, background=bottom))
+
+
+@dataclass(frozen=True, slots=True)
+class HalfBlocks:
+    """
+    A `Canvas` painter for a pixel grid drawn with half blocks (▀), two pixels to a cell, as `canvas` draws it.
+
+    `pixels` pairs `(x, y)` positions with colors (a later pair wins over an earlier one at the same position),
+    and every other pixel of the `width` by `height` grid is `default`.
+    It's a tuple rather than a dict so the painter is hashable, which caches what it draws.
+    """
+
+    width: int
+    height: int
+    pixels: tuple[tuple[tuple[int, int], Color], ...]
+    default: Color = _BLACK
+
+    @property
+    def cells(self) -> tuple[int, int]:
+        """The canvas's intrinsic size, in cells."""
+        return self.width, (self.height + 1) // 2
+
+    def __call__(self, width: int, height: int) -> Rows:
+        colors = dict(self.pixels)
+        default = self.default
+        get = colors.get
+        return tuple(
+            tuple(
+                _half_block(get((x, top), default), get((x, top + 1), default)) for x in range(min(width, self.width))
+            )
+            for top in range(0, min(height * 2, self.height), 2)
+        )
+
+
+__all__ = ["HalfBlocks", "canvas", "clamp"]
````

#### `benchmarks/canvas.py`

````diff
diff --git a/benchmarks/canvas.py b/benchmarks/canvas.py
index 2546c25..88968ed 100644
--- a/benchmarks/canvas.py
+++ b/benchmarks/canvas.py
@@ -10,8 +10,8 @@ from dataclasses import dataclass
 from itertools import product

 from benchmarks.harness import Workload
-from counterweight.components import component
-from counterweight.elements import Chunk, Div, Text
+from counterweight.components import Component, component
+from counterweight.elements import Canvas, Chunk, Div, Text
 from counterweight.styles.styles import COLORS_BY_NAME, CellStyle, Color
 from counterweight.styles.utilities import (
     align_children_center,
@@ -26,7 +26,7 @@ from counterweight.styles.utilities import (
     row,
     text_justify_center,
 )
-from counterweight.utils import canvas, clamp
+from counterweight.utils import HalfBlocks, canvas, clamp

 WIDTH = 30
 HEIGHT = 30
@@ -75,6 +75,15 @@ def walk(walkers: Walkers, rng: random.Random) -> Walkers:

 def view(model: Model) -> Div:
     canvases = tuple(walker_canvas(colors, walkers) for colors, walkers in zip(model.colors, model.walkers))
+    return layout(canvases)
+
+
+def element_view(model: Model) -> Div:
+    canvases = tuple(walker_canvas_element(colors, walkers) for colors, walkers in zip(model.colors, model.walkers))
+    return layout(canvases)
+
+
+def layout(canvases: tuple[Component, ...]) -> Div:
     return Div(
         style=col | align_children_center | justify_children_space_evenly,
         children=(
@@ -107,6 +116,27 @@ def walker_canvas(colors: tuple[Color, ...], walkers: Walkers) -> Text:
     )


+@component
+def walker_canvas_element(colors: tuple[Color, ...], walkers: Walkers) -> Canvas:
+    painter = HalfBlocks(WIDTH, HEIGHT, tuple(zip(walkers, colors)))
+    width, height = painter.cells
+    return Canvas(
+        draw=painter,
+        width=width,
+        height=height,
+        style=border | border_heavy | border_color("slate", 400),
+    )
+
+
+ELEMENT_WORKLOAD = Workload(
+    name="canvas-element",
+    description="`canvas` drawn with `Canvas` elements and a `HalfBlocks` painter instead of `Text` chunks.",
+    initial=initial,
+    step=step,
+    view=element_view,
+    dimensions=(80, 40),
+)
+
 WORKLOAD = Workload(
     name="canvas",
     description=__doc__ or "",
````

#### `benchmarks/workloads.py`

````diff
diff --git a/benchmarks/workloads.py b/benchmarks/workloads.py
index 37747ae..379daa7 100644
--- a/benchmarks/workloads.py
+++ b/benchmarks/workloads.py
@@ -7,6 +7,7 @@ WORKLOADS: dict[str, Runnable] = {
     workload.name: workload
     for workload in (
         canvas.WORKLOAD,
+        canvas.ELEMENT_WORKLOAD,
         top.WORKLOAD,
         top.MEMO_WORKLOAD,
         agent.WORKLOAD,
````

### Emulator, pseudo-terminals and the embed (phases 2, 3 and 6)

#### `src/counterweight/emulator.py`

````python
"""
A terminal emulator for embedding a program's output, and the immutable `Screen` values it produces.

Spike: the emulator is [libghostty-vt](https://ghostty.org), through `pyghostty`'s cffi bindings.
Everything outside this module sees only `Screen` and `Modes`, so the emulator behind them can be swapped.
The emulator object is a place (bytes fed to it change it); `snapshot` turns it into a value once per frame.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from pyghostty import Terminal
from pyghostty._ffi import check, ffi, lib
from pyghostty.core import init_sized

from counterweight.elements import Rows
from counterweight.geometry import Position
from counterweight.paint import Cell
from counterweight.styles.styles import CELL_STYLE_DEFAULTS, Color, ResolvedCellStyle

type MouseTracking = Literal["none", "x10", "normal", "button", "any"]


@dataclass(frozen=True, slots=True)
class Modes:
    """The modes the embedded program has set that change how input must be encoded for it."""

    application_cursor_keys: bool = False
    """DECCKM (`?1`): cursor keys send `ESC O A` rather than `ESC [ A`."""
    bracketed_paste: bool = False
    """`?2004`: pastes are wrapped in `ESC [ 200 ~` and `ESC [ 201 ~`."""
    mouse_tracking: MouseTracking = "none"
    """Which mouse events the program asked for (`?9`, `?1000`, `?1002`, `?1003`), if any."""
    sgr_mouse: bool = False
    """`?1006`: mouse events are reported in SGR format."""
    focus_events: bool = False
    """`?1004`: the program wants `ESC [ I` and `ESC [ O` when it gains and loses focus."""
    alternate_screen: bool = False
    """`?1049` (or `?47`, `?1047`): the program is drawing on the alternate screen, as full-screen programs do."""


@dataclass(frozen=True, slots=True, eq=False)
class Screen:
    """
    What an embedded program's terminal shows at one moment: its rows of cells, its cursor, its modes and its title.

    Compared by identity: each snapshot of a changed terminal is a new `Screen`,
    so a `Canvas` drawing one is drawn again only when the program's output changed it.
    Rows the program didn't change are the same tuples as in the previous snapshot.
    """

    columns: int
    rows: int
    lines: tuple[tuple[Cell, ...], ...]
    cursor: Position | None
    """Where the cursor is, or `None` if the program hid it."""
    modes: Modes
    title: str


@dataclass(frozen=True, slots=True)
class ScreenView:
    """A `Canvas` painter for a `Screen`, drawing its cursor as a reversed cell when `show_cursor`."""

    screen: Screen
    show_cursor: bool

    def __call__(self, width: int, height: int) -> Rows:
        lines = self.screen.lines[:height]
        cursor = self.screen.cursor
        if not self.show_cursor or cursor is None or cursor.y >= len(lines) or cursor.x >= len(lines[cursor.y]):
            return lines
        line = lines[cursor.y]
        under = line[cursor.x]
        if under.is_continuation:
            return lines
        reversed_style = replace(under.style, foreground=under.style.background, background=under.style.foreground)
        cursor_line = (*line[: cursor.x], Cell(under.grapheme, reversed_style), *line[cursor.x + 1 :])
        return (*lines[: cursor.y], cursor_line, *lines[cursor.y + 1 :])


BLANK_SCREEN = Screen(columns=0, rows=0, lines=(), cursor=None, modes=Modes(), title="")


class Emulator:
    """
    A terminal emulator fed an embedded program's output.

    `replies` receives the bytes the emulator answers the program's queries with (cursor position reports,
    device attributes), which belong on the program's input, as a terminal would send them.
    """

    def __init__(
        self,
        columns: int,
        rows: int,
        replies: Callable[[bytes], None],
        defaults: ResolvedCellStyle = CELL_STYLE_DEFAULTS,
    ) -> None:
        self.terminal = Terminal(cols=columns, rows=rows)
        self.terminal.on_reply(replies)
        self.defaults = defaults
        self.state = ffi.new("GhosttyRenderState*")
        check(lib.ghostty_render_state_new(ffi.NULL, self.state), "render_state_new")
        self.row_iterator = ffi.new("GhosttyRenderStateRowIterator*")
        check(lib.ghostty_render_state_row_iterator_new(ffi.NULL, self.row_iterator), "row_iterator_new")
        self.cells = ffi.new("GhosttyRenderStateRowCells*")
        check(lib.ghostty_render_state_row_cells_new(ffi.NULL, self.cells), "row_cells_new")
        self.style = init_sized("GhosttyStyle")
        self.rgb = ffi.new("GhosttyColorRgb*")
        self.raw = ffi.new("GhosttyCell*")
        self.wide = ffi.new("int*")
        self.grapheme_length = ffi.new("uint32_t*")
        self.grapheme_buffer = ffi.new("uint32_t[32]")
        self.dirty = ffi.new("bool*")
        # An unstyled cell's raw value holds only its codepoint and width, so it maps to one Cell for good.
        # A styled cell's raw value holds a style id that only means something within its page, so it can't be cached.
        self.plain: dict[int, Cell] = {}
        self.has_styling = ffi.new("bool*")
        self.content_tag = ffi.new("int*")
        self.codepoint = ffi.new("uint32_t*")
        self.classify_keys = ffi.new(
            "GhosttyCellData[4]",
            [
                lib.GHOSTTY_CELL_DATA_WIDE,
                lib.GHOSTTY_CELL_DATA_HAS_STYLING,
                lib.GHOSTTY_CELL_DATA_CONTENT_TAG,
                lib.GHOSTTY_CELL_DATA_CODEPOINT,
            ],
        )
        self.classify_values = ffi.new(
            "void*[4]",
            [
                ffi.cast("void*", self.wide),
                ffi.cast("void*", self.has_styling),
                ffi.cast("void*", self.content_tag),
                ffi.cast("void*", self.codepoint),
            ],
        )
        self.row_id = ffi.new("GhosttyRenderStateRowId*")
        self.title_out = ffi.new("GhosttyString*")
        # Converted rows by libghostty's row id, kept from one snapshot to the next for rows that aren't dirty,
        # so a program scrolling by a line converts one row rather than all of them.
        self.converted: dict[tuple[int, int], tuple[Cell, ...]] = {}
        self.colors: dict[tuple[int, int, int], Color] = {}
        self.last: Screen = BLANK_SCREEN

    def feed(self, data: bytes) -> None:
        self.terminal.feed(data)

    def resize(self, columns: int, rows: int) -> None:
        self.terminal.resize(columns, rows)

    def snapshot(self) -> Screen:
        """The screen as the emulator shows it now."""
        terminal = self.terminal._t[0]
        state = self.state[0]
        check(lib.ghostty_render_state_update(state, terminal), "render_state_update")
        check(
            lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_ROW_ITERATOR, self.row_iterator), "rows"
        )
        rows = self.row_iterator[0]
        converted: dict[tuple[int, int], tuple[Cell, ...]] = {}
        lines = []
        while lib.ghostty_render_state_row_iterator_next(rows):
            lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_DIRTY, self.dirty)
            lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_ID, self.row_id)
            key = (self.row_id.bits[0], self.row_id.bits[1])
            line = None if self.dirty[0] else self.converted.get(key)
            if line is None:
                line = self.convert_row(rows)
            converted[key] = line
            lines.append(line)
        lib.ghostty_render_state_clean(state)
        self.converted = converted

        columns, row_count = self.terminal.size
        x, y = self.terminal.cursor
        screen = Screen(
            columns=columns,
            rows=row_count,
            lines=tuple(lines),
            cursor=Position(x, y) if self.terminal.mode(25) else None,
            modes=self.modes(),
            title=self.title(),
        )
        self.last = screen
        return screen

    def convert_row(self, rows: object) -> tuple[Cell, ...]:
        cells_handle = self.cells
        check(lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_CELLS, cells_handle), "cells")
        cells = cells_handle[0]
        style = self.style
        rgb = self.rgb
        defaults = self.defaults
        row: list[Cell] = []
        get = lib.ghostty_render_state_row_cells_get
        plain = self.plain
        while lib.ghostty_render_state_row_cells_next(cells):
            get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_RAW, self.raw)
            raw = self.raw[0]
            if (cell := plain.get(raw)) is not None:
                row.append(cell)
                continue
            lib.ghostty_cell_get_multi(raw, 4, self.classify_keys, self.classify_values, ffi.NULL)
            wide = self.wide[0]
            is_plain = not self.has_styling[0] and self.content_tag[0] == lib.GHOSTTY_CELL_CONTENT_CODEPOINT
            if is_plain and wide != lib.GHOSTTY_CELL_WIDE_SPACER_TAIL:
                cell = plain[raw] = Cell(chr(self.codepoint[0]) if self.codepoint[0] else " ", defaults)
                row.append(cell)
                continue
            if wide == lib.GHOSTTY_CELL_WIDE_SPACER_TAIL:
                row.append(Cell("", row[-1].style if row else defaults))
                continue
            get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_GRAPHEMES_LEN, self.grapheme_length)
            length = self.grapheme_length[0]
            if length:
                get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_GRAPHEMES_BUF, self.grapheme_buffer)
                grapheme = "".join(map(chr, self.grapheme_buffer[0:length]))
            else:
                grapheme = " "
            foreground = (
                self.color(rgb)
                if get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_FG_COLOR, rgb) == lib.GHOSTTY_SUCCESS
                else defaults.foreground
            )
            background = (
                self.color(rgb)
                if get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_BG_COLOR, rgb) == lib.GHOSTTY_SUCCESS
                else defaults.background
            )
            get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_STYLE, style)
            if style.inverse:
                foreground, background = background, foreground
            if style.invisible:
                foreground = background
            row.append(
                Cell(
                    grapheme,
                    cell_style(
                        foreground,
                        background,
                        style.bold,
                        style.faint,
                        style.italic,
                        style.underline != 0,
                        style.strikethrough,
                    ),
                )
            )
        return tuple(row)

    def color(self, rgb: object) -> Color:
        key = (rgb.r, rgb.g, rgb.b)  # type: ignore[attr-defined]
        try:
            return self.colors[key]
        except KeyError:
            color = self.colors[key] = Color(*key)
            return color

    def modes(self) -> Modes:
        mode = self.terminal.mode
        # The most detailed tracking mode set wins, as in xterm.
        tracking: MouseTracking = (
            "any"
            if mode(1003)
            else "button"
            if mode(1002)
            else "normal"
            if mode(1000)
            else "x10"
            if mode(9)
            else "none"
        )
        return Modes(
            application_cursor_keys=mode(1),
            bracketed_paste=mode(2004),
            mouse_tracking=tracking,
            sgr_mouse=mode(1006),
            focus_events=mode(1004),
            alternate_screen=mode(1049) or mode(1047) or mode(47),
        )

    def title(self) -> str:
        result = lib.ghostty_terminal_get(self.terminal._t[0], lib.GHOSTTY_TERMINAL_DATA_TITLE, self.title_out)
        if result != lib.GHOSTTY_SUCCESS or not self.title_out.len:
            return ""
        return bytes(ffi.buffer(self.title_out.ptr, self.title_out.len)).decode(errors="replace")

    def close(self) -> None:
        lib.ghostty_render_state_row_cells_free(self.cells[0])
        lib.ghostty_render_state_row_iterator_free(self.row_iterator[0])
        lib.ghostty_render_state_free(self.state[0])
        self.terminal.close()


_STYLES: dict[tuple[Color, Color, bool, bool, bool, bool, bool], ResolvedCellStyle] = {}


def cell_style(
    foreground: Color, background: Color, bold: bool, dim: bool, italic: bool, underline: bool, strikethrough: bool
) -> ResolvedCellStyle:
    key = (foreground, background, bold, dim, italic, underline, strikethrough)
    try:
        return _STYLES[key]
    except KeyError:
        style = _STYLES[key] = ResolvedCellStyle(
            foreground=foreground,
            background=background,
            bold=bold,
            dim=dim,
            italic=italic,
            underline=underline,
            strikethrough=strikethrough,
            link=None,
        )
        return style
````

#### `src/counterweight/input_encoding.py`

````python
"""
Pure encoding of input events back into the bytes a terminal would send a program, for an embedded program's input.

The inverse of `input_parsing`: the key tables are recovered from its tables, so the two can't drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import assert_never

from counterweight.emulator import Modes
from counterweight.events import (
    MouseDown,
    MouseEvent,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
    MouseScrolledUp,
    MouseUp,
)
from counterweight.geometry import Position
from counterweight.input_parsing import CONTROL_KEYS, LETTER_KEYS, PASTE_END, PASTE_START, SEQUENCE_KEYS
from counterweight.keys import Key

ESC = b"\x1b"


def key_sequences() -> dict[str, bytes]:
    """
    The bytes for each key `input_parsing` recognizes, choosing among a key's several spellings
    the one xterm sends by default: `DEL` for Backspace, `CSI` rather than `SS3` for cursor keys.
    """
    sequences: dict[str, bytes] = {}
    for sequence, key in SEQUENCE_KEYS.items():
        # Prefer CSI over SS3, and the shorter of two CSI spellings (Home is both `CSI H` and `CSI 1 ~`).
        if (existing := sequences.get(key)) is None or (
            existing.startswith(b"\x1bO") and sequence.startswith(b"\x1b[")
        ):
            sequences[key] = sequence
        elif existing.startswith(b"\x1b[") and sequence.startswith(b"\x1b[") and len(sequence) < len(existing):
            sequences[key] = sequence
    for byte, key in CONTROL_KEYS.items():
        sequences.setdefault(key, bytes([byte]))
    sequences[Key.Backspace] = b"\x7f"
    sequences[Key.Escape] = ESC
    sequences[Key.Space] = b" "
    return sequences


KEY_SEQUENCES: Mapping[str, bytes] = key_sequences()

# DECCKM's cursor keys, which a program in application cursor key mode expects as `SS3 <letter>`.
APPLICATION_CURSOR_KEYS: Mapping[str, bytes] = {
    key: b"\x1bO" + final
    for final, key in LETTER_KEYS.items()
    if key in (Key.Up, Key.Down, Key.Right, Key.Left, Key.Home, Key.End)
}


def encode_key(key: str, modes: Modes) -> bytes | None:
    """
    The bytes a terminal sends for a `KeyPressed` with `key`, given the program's `modes`,
    or `None` for a key there's no legacy encoding for.
    """
    if modes.application_cursor_keys and (sequence := APPLICATION_CURSOR_KEYS.get(key)) is not None:
        return sequence
    if (sequence := KEY_SEQUENCES.get(key)) is not None:
        return sequence
    if key.startswith("ctrl+alt+") and (control := KEY_SEQUENCES.get(f"ctrl+{key.removeprefix('ctrl+alt+')}")):
        return ESC + control
    if key.startswith("alt+"):
        rest = key.removeprefix("alt+")
        inner = KEY_SEQUENCES.get(rest) or (rest.encode() if len(rest) == 1 or not rest.isascii() else None)
        return None if inner is None else ESC + inner
    if key in Key.__members__.values():
        return None
    return key.encode()


def encode_paste(text: str, modes: Modes) -> bytes:
    """
    The bytes a terminal sends for a paste of `text`: line breaks as carriage returns, as terminals send them,
    wrapped in bracketed paste markers if the program asked for them.
    An end marker inside the text is dropped, so a paste can't end itself early and type the rest as keys.
    """
    body = text.replace("\r\n", "\r").replace("\n", "\r").encode()
    if not modes.bracketed_paste:
        return body
    return PASTE_START + body.replace(PASTE_END, b"") + PASTE_END


WHEEL_CODES: Mapping[type[MouseEvent], int] = {
    MouseScrolledUp: 64,
    MouseScrolledDown: 65,
    MouseScrolledLeft: 66,
    MouseScrolledRight: 67,
}


def encode_mouse(event: MouseEvent, position: Position, modes: Modes) -> bytes | None:
    """
    The bytes a terminal sends for `event` at `position` in the program's screen,
    given the mouse tracking the program asked for, or `None` if it didn't ask for this event.
    """
    tracking = modes.mouse_tracking
    if tracking == "none":
        return None

    match event:
        case MouseDown(button=button):
            code, is_release = button_code(button), False
        case MouseUp(button=button):
            if tracking == "x10":
                return None
            code, is_release = button_code(button), True
        case MouseMoved(button=held):
            if held is None:
                if tracking != "any":
                    return None
                code, is_release = 3 + 32, False
            else:
                if tracking not in ("button", "any"):
                    return None
                code, is_release = button_code(held) + 32, False
        case MouseScrolledUp() | MouseScrolledDown() | MouseScrolledLeft() | MouseScrolledRight():
            code, is_release = WHEEL_CODES[type(event)], False
        case _ as unreachable:
            assert_never(unreachable)

    if tracking != "x10":
        code |= (
            (4 if event.is_shift_held else 0) | (8 if event.is_alt_held else 0) | (16 if event.is_control_held else 0)
        )

    x, y = position.x + 1, position.y + 1
    if modes.sgr_mouse:
        return b"\x1b[<%d;%d;%d%s" % (code, x, y, b"m" if is_release else b"M")
    if x > 223 or y > 223:
        return None
    # The legacy encoding has no release per button: a release is button code 3.
    legacy = (3 | (code & ~0b11)) if is_release else code
    return b"\x1b[M" + bytes([32 + legacy, 32 + x, 32 + y])


def button_code(button: int) -> int:
    """The low bits (and bit 128 for buttons 8 to 11) of a mouse report's code for `button`, numbered from 1."""
    if button >= 8:
        return 128 | (button - 8)
    return button - 1
````

#### `src/counterweight/headless/terminal.py`

````python
"""
[`use_pty`][counterweight.headless.terminal.use_pty], which runs a program on a pseudo-terminal,
and [`use_terminal`][counterweight.headless.terminal.use_terminal], which emulates the terminal that program draws on,
leaving where and how to show it to the calling component.

Spike: Linux and macOS only.
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
import struct
import termios
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from counterweight.controls import FocusOn
from counterweight.emulator import BLANK_SCREEN, Emulator, Screen, ScreenView
from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    KeyPressed,
    MouseDown,
    MouseEvent,
    Pasted,
    Receiver,
)
from counterweight.focus import FocusHandle
from counterweight.hooks import Focus, Ref, use_effect, use_focus, use_ref, use_state
from counterweight.input_encoding import encode_key, encode_mouse, encode_paste

logger = logging.getLogger(__name__)

READ_SIZE = 2**16

# The shortest time between two snapshots of a busy terminal, so a program writing as fast as it can
# (`cat` of a big file) costs one snapshot per frame rather than one per read.
SNAPSHOT_INTERVAL = timedelta(milliseconds=1000 / 60)


@dataclass(slots=True)
class PtyConnection:
    """
    The master side of a running program's pseudo-terminal, which `use_pty`'s effect owns.
    Writes that the program isn't reading yet are buffered and flushed when the master is writable,
    so a handler never blocks the event loop.
    """

    master: int
    pid: int
    pending: bytearray = field(default_factory=bytearray)
    is_writing: bool = False

    def write(self, data: bytes) -> None:
        if not data:
            return
        self.pending += data
        self.flush()

    def flush(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            written = os.write(self.master, self.pending)
        except BlockingIOError:
            written = 0
        except OSError:
            # The program exited and the slave side closed, so there's no one left to read this.
            self.pending.clear()
            written = 0
        del self.pending[:written]
        if self.pending and not self.is_writing:
            loop.add_writer(self.master, self.flush)
            self.is_writing = True
        elif not self.pending and self.is_writing:
            loop.remove_writer(self.master)
            self.is_writing = False

    def resize(self, columns: int, rows: int) -> None:
        """Sets the terminal's size, which sends the program `SIGWINCH`, as resizing a terminal window does."""
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))


def make_controlling_terminal() -> None:
    """In the child, after `setsid`: make its stdin, the pty's slave side, its controlling terminal."""
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


async def run_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    env: Mapping[str, str] | None,
    on_output: Callable[[bytes], None],
    on_connect: Callable[[PtyConnection | None], None],
) -> int:
    """
    Runs `argv` on a new pseudo-terminal `columns` by `rows` in its own session, as its controlling terminal,
    calling `on_output` with what it writes, until it exits, returning its exit status.
    Cancelled, it hangs the program up (`SIGHUP` to its process group), as closing a terminal window does.
    """
    master, slave = os.openpty()
    os.set_blocking(master, False)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    environment = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", **(env or {})}
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=environment,
        start_new_session=True,
        preexec_fn=make_controlling_terminal,
    )
    os.close(slave)
    connection = PtyConnection(master=master, pid=process.pid)
    loop = asyncio.get_running_loop()
    closed = loop.create_future()

    def read() -> None:
        try:
            data = os.read(master, READ_SIZE)
        except BlockingIOError:
            return
        except OSError:  # EIO once the slave side closes, on Linux
            data = b""
        if not data:
            loop.remove_reader(master)
            if not closed.done():
                closed.set_result(None)
            return
        on_output(data)

    loop.add_reader(master, read)
    on_connect(connection)
    try:
        status = await process.wait()
        # Drain what the program wrote just before it exited.
        await asyncio.wait_for(asyncio.shield(closed), timeout=0.5)
        return status
    except asyncio.CancelledError, TimeoutError:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
        raise
    finally:
        on_connect(None)
        loop.remove_reader(master)
        if connection.is_writing:
            loop.remove_writer(master)
        os.close(master)


@dataclass(frozen=True, slots=True)
class Pty:
    """What `use_pty` returns: how to write to the program and resize its terminal, and whether it exited."""

    write: Callable[[bytes], None]
    exit_status: int | None
    """The program's exit status, or `None` while it's running (or before it starts)."""


def use_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    on_output: Callable[[bytes], None],
    env: Mapping[str, str] | None = None,
) -> Pty:
    """
    Runs `argv` on a pseudo-terminal while the calling component is mounted, and again if `argv` changes,
    calling `on_output` with the bytes it writes (from an effect, not during a render),
    and keeping its terminal `columns` by `rows`.
    """
    connection: Ref[PtyConnection | None] = use_ref(None)
    initial_status: int | None = None
    exit_status, set_exit_status = use_state(initial_status)
    size = use_ref((columns, rows))
    size.current = (columns, rows)

    # Wrapped in a getter, since use_ref would call a bare callable as its initializer.
    def initial_output() -> Callable[[bytes], None]:
        return on_output

    output: Ref[Callable[[bytes], None]] = use_ref(initial_output)
    output.current = on_output

    def connect(c: PtyConnection | None) -> None:
        connection.current = c

    def forward(data: bytes) -> None:
        # Through the ref, so the latest render's callback gets the output, not the first one's.
        output.current(data)

    async def run() -> None:
        set_exit_status(None)
        status = await run_pty(argv, *size.current, env, on_output=forward, on_connect=connect)
        set_exit_status(status)

    use_effect(run, deps=(tuple(argv),))

    async def resize() -> None:
        if (c := connection.current) is not None and columns > 0 and rows > 0:
            c.resize(columns, rows)

    use_effect(resize, deps=(columns, rows))

    def write(data: bytes) -> None:
        if (c := connection.current) is not None:
            c.write(data)

    return Pty(write=write, exit_status=exit_status)


@dataclass(frozen=True, slots=True)
class EmbeddedTerminal:
    """What `use_terminal` returns to the calling component."""

    screen: Screen
    """What the program's terminal shows, as of the last snapshot."""

    view: ScreenView
    """The painter for the `Canvas` the calling component shows the terminal in, with the cursor drawn when focused."""

    exit_status: int | None
    focus: Focus

    on_input: InputHandler
    """
    The handler for the `Canvas`: while it's focused, it sends the program every key press and paste
    it has an encoding for, and claims them, so they don't bubble.
    It sends mouse events in the canvas to the program when the program asked for them,
    and focuses the canvas on a press.
    Put a handler before it with `first` to take keys before the program sees them, as a multiplexer's prefix key does.
    """

    write: Callable[[bytes], None]


def use_terminal(
    argv: Sequence[str],
    columns: int,
    rows: int,
    env: Mapping[str, str] | None = None,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
) -> EmbeddedTerminal:
    """
    Runs `argv` on a pseudo-terminal `columns` by `rows`, emulating the terminal it draws on.

    The emulator is fed on the event loop as the program writes, and snapshotted into a `Screen` value at most once
    per `SNAPSHOT_INTERVAL`, which re-renders the calling component.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle)
    screen, set_screen = use_state(BLANK_SCREEN)
    emulator_ref: Ref[Emulator | None] = use_ref(None)
    scheduled = use_ref(False)
    last_snapshot = use_ref(0.0)

    def publish() -> None:
        scheduled.current = False
        if (emulator := emulator_ref.current) is not None:
            last_snapshot.current = asyncio.get_running_loop().time()
            set_screen(emulator.snapshot())

    def schedule_snapshot() -> None:
        if scheduled.current:
            return
        scheduled.current = True
        loop = asyncio.get_running_loop()
        wait = last_snapshot.current + SNAPSHOT_INTERVAL.total_seconds() - loop.time()
        if wait <= 0:
            loop.call_soon(publish)
        else:
            loop.call_later(wait, publish)

    def on_output(data: bytes) -> None:
        if (emulator := emulator_ref.current) is None:
            return
        emulator.feed(data)
        schedule_snapshot()

    pty = use_pty(argv, columns, rows, on_output=on_output, env=env)

    async def own_emulator() -> None:
        emulator = emulator_ref.current = Emulator(max(columns, 1), max(rows, 1), replies=pty.write)
        try:
            await asyncio.Event().wait()
        finally:
            emulator.close()
            emulator_ref.current = None

    use_effect(own_emulator, deps=(tuple(argv),))

    async def resize() -> None:
        if (emulator := emulator_ref.current) is not None and columns > 0 and rows > 0:
            emulator.resize(columns, rows)
            schedule_snapshot()

    use_effect(resize, deps=(columns, rows))

    modes = screen.modes

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=key):
                if not receiver.is_focused or (encoded := encode_key(key, modes)) is None:
                    return None
                pty.write(encoded)
                return ()
            case Pasted(text=text):
                if not receiver.is_focused:
                    return None
                pty.write(encode_paste(text, modes))
                return ()
            case _:
                return on_mouse(event, receiver)

    def on_mouse(event: MouseEvent, receiver: Receiver) -> InputResponse:
        position = receiver.relative(event.absolute)
        if not (0 <= position.x < screen.columns and 0 <= position.y < screen.rows) and not isinstance(
            event, MouseDown
        ):
            return None
        if (encoded := encode_mouse(event, position, modes)) is not None:
            pty.write(encoded)
            return FocusOn(focus.handle) if isinstance(event, MouseDown) else ()
        if isinstance(event, MouseDown):
            return FocusOn(focus.handle)
        return None

    return EmbeddedTerminal(
        screen=screen,
        view=ScreenView(screen=screen, show_cursor=focus.is_focused),
        exit_status=pty.exit_status,
        focus=focus,
        on_input=on_input,
        write=pty.write,
    )
````

#### `examples/multiplexer.py`

````python
"""
A tiny terminal multiplexer: shells side by side, each on its own pseudo-terminal.

Ctrl+B is the prefix, as in tmux. After it:
  %  split: open another shell to the right
  o  focus the next pane
  x  close the focused pane
  q  quit
Ctrl+B Ctrl+B sends a Ctrl+B to the focused program.
"""

import asyncio
import os
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import ClearFocus, FocusNext, Quit
from counterweight.elements import Canvas, Div, Text
from counterweight.events import InputEvent, InputHandler, InputResponse, KeyPressed, Receiver
from counterweight.handlers import first
from counterweight.headless.terminal import use_terminal
from counterweight.hooks import FocusHandle, use_effect, use_rects, use_ref, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

SHELL = (os.environ.get("SHELL", "/bin/sh"),)


@component
def root() -> Div:
    panes, set_panes = use_state((0,))
    next_id, set_next_id = use_state(1)
    # A ref, not state: keys in one read are all handled before the next render, so each must see the last one's effect.
    armed = use_ref(False)
    is_armed, set_shown_armed = use_state(False)

    def set_armed(value: bool) -> None:
        armed.current = value
        set_shown_armed(value)

    titles, set_titles = use_state({})
    handles, _ = use_state(dict)

    def handle_of(pane_id: int) -> FocusHandle:
        return handles.setdefault(pane_id, FocusHandle())

    def prefix(pane_id: int) -> InputHandler:
        def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
            if not isinstance(event, KeyPressed) or not receiver.is_focused:
                return None
            if not armed.current:
                if event.key == Key.ControlB:
                    set_armed(True)
                    return ()
                return None
            set_armed(False)
            match event.key:
                case Key.ControlB:
                    return None  # the pane's own handler sends it on
                case "%":
                    set_panes(lambda p: (*p, next_id))
                    set_next_id(lambda n: n + 1)
                    # FocusOn can't name a pane that mounts in this update, so clear focus for the new pane's auto_focus.
                    return ClearFocus()
                case "o":
                    return FocusNext()
                case "x":
                    set_panes(lambda p: tuple(i for i in p if i != pane_id) or p)
                    return FocusNext()
                case "q":
                    return Quit()
                case _:
                    return ()

        return on_input

    def set_title(pane_id: int) -> Callable[[str], None]:
        return lambda title: set_titles(lambda t: t if t.get(pane_id) == title else {**t, pane_id: title})

    status = "  ".join(f"[{i}] {titles.get(i, '')}" for i in panes)
    return Div(
        style=col | full,
        children=(
            Div(
                style=row | grow(1),
                children=tuple(
                    pane(pane_id, prefix(pane_id), handle_of(pane_id), set_title(pane_id)).with_key(str(pane_id))
                    for pane_id in panes
                ),
            ),
            Text(
                content=("PREFIX " if is_armed else "") + status,
                style=text_color("slate", 900) | text_bg("amber", 400 if is_armed else 200) | text_wrap_none,
            ),
        ),
    )


@component
def pane(pane_id: int, prefix: InputHandler, handle: FocusHandle, on_title: Callable[[str], None]) -> Canvas:
    content = use_rects().content
    terminal = use_terminal(SHELL, content.width, content.height, auto_focus=True, handle=handle)
    title = terminal.screen.title if terminal.exit_status is None else f"exited {terminal.exit_status}"

    async def report_title() -> None:
        on_title(title)

    use_effect(report_title, deps=(title,))
    return Canvas(
        draw=terminal.view,
        style=fill(1)
        | border
        | border_lightrounded
        | (border_color("amber", 400) if terminal.focus.is_focused else border_color("slate", 600)),
        on_input=first(prefix, terminal.on_input),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
````
