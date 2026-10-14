# Spike: Canvas and Embedding Terminals

This spike asks two questions.
Can a pixel-grid canvas skip text layout, through a new element whose callback paints cells directly?
And what would it take to build a terminal multiplexer in counterweight:
to run programs on pseudo-terminals and show each one in a box, with input routed to it?
It answers the second with a survey of how tmux and zellij work,
and a working prototype (`examples/multiplexer.py`) built on three new layers.
It doesn't cover detaching sessions, scrollback or copy mode, or graphics protocols (sixel, kitty images).

The two ideas turned out to be one stack.
The paint-callback element is the primitive the embed needs:
an embedded terminal is just a painter whose rows come from an emulator's screen.
They can land separately, `Canvas` first.

## The code

All of it is uncommitted on the `embed` branch.
The spike runs with `uv run --with pyghostty==0.1.3 ...`: the dependency isn't in `pyproject.toml`.
The existing tests pass and mypy is clean; the new code has no tests yet, so coverage would fail.

- `elements.py`, `layout.py`, `paint.py`: the `Canvas` element.
- `utils.py`: `HalfBlocks`, a `Canvas` painter equivalent to `canvas()`.
- `benchmarks/canvas.py`: a `canvas-element` workload, `canvas` redrawn with `Canvas` and `HalfBlocks`.
- `emulator.py`: libghostty-vt behind `Emulator`, which produces immutable `Screen` values.
- `input_encoding.py`: pure functions from key, paste and mouse events back to the bytes a terminal sends.
- `headless/terminal.py`: `use_pty` and `use_terminal`.
- `examples/multiplexer.py`: shells side by side, with a tmux-style `Ctrl+B` prefix.

## Part 1: the `Canvas` element

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

### Design

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Canvas:
    draw: Callable[[int, int], Rows]  # (content width, content height) -> rows of Cell
    width: int = 0   # intrinsic size, used on each axis the style leaves auto
    height: int = 0
    style: Style = _DEFAULT_STYLE
    on_input: InputHandler | None = None
    handle: ElementHandle | None = None
```

Prior art splits on two questions:

- **Who owns the buffer?**
  [ratatui](https://github.com/ratatui/ratatui)'s `Widget::render(self, area, &mut Buffer)` hands the widget the whole screen buffer
  in absolute coordinates.
  Nothing stops a widget writing outside `area`, and writing outside the buffer panics.
  Its changelog shows built-in widgets learning to clip one by one (#1670, #1996, #2368).
  [Textual](https://github.com/Textualize/textual)'s `render_line(y) -> Strip` returns immutable values instead,
  and caches them per line.
  `Canvas` follows Textual:
  `draw` returns rows of cells in local coordinates, and the framework places and clips them,
  through the same `write_row` and clip that `Text` uses.
  A painter can't draw outside its box, and the result is a value that can be cached.
- **When does the painter re-run?**
  Ratatui re-renders everything every frame and saves only terminal output through its buffer diff.
  Flutter's `CustomPainter.shouldRepaint(old)` and Compose's `drawWithCache` skip the painter when its inputs are unchanged.
  `Canvas` caches `draw(width, height)` by `(draw, width, height)` (`paint.canvas_rows`),
  so a painter that's a frozen dataclass equal to last frame's isn't called at all.
  This is Flutter's `shouldRepaint` with `==` as the test, which is already how counterweight decides everything else.

Sizing follows HTML's `<canvas>`, a replaced element:
`width` and `height` give the intrinsic size,
which layout uses on each axis the style leaves `auto`.
The style can size the box to anything, and `draw` is called with the box's real content size.
Unlike a browser canvas there's no bitmap to scale, so the painter decides what to draw at that size.
Rows that overflow the box are clipped, and a box with fewer rows shows the background, as `Text` does.
Flutter and Compose default the intrinsic size to zero, and an invisible canvas is a known complaint.
HTML defaults to 300×150.
`Canvas` defaults to 0×0 for now, which is the decision to revisit.

### Open decisions before `Canvas` lands

- **Painters must be hashable.**
  The cache is an `lru_cache`, so a frozen dataclass holding a `dict` raises `TypeError` at paint time.
  `HalfBlocks` holds its pixels as a tuple for this reason.
  The alternatives are a per-node cache that needs only `==`
  (kept across frames the way `LayoutTree` is),
  or falling back to calling an unhashable painter every frame.
  A per-node cache is the one I'd pick: it is also what makes a closure painter cheap when its key is stable.
- **Painters are callables, and hooks treat callables as initializers.**
  `use_state(painter)` calls the painter, and `set_state(painter)` treats it as an updater.
  The spike hit both (`Screen` was callable at first; `use_ref(on_output)` was called).
  Keeping painters out of state is enough, as `ScreenView` does,
  but it should be documented, or `draw` should take a `Painter` protocol with a named method.
- **Wide graphemes.**
  `Paint` requires every two-cell grapheme to be followed by its continuation cell (`Cell("")`).
  Painters must emit it, and the docstring should say so.
  Ratatui leaves the trailing cell blank instead, and its diff special-cases replacing wide glyphs.
- **`Rows` exposes `paint.Cell` and `ResolvedCellStyle` as public API.**
  Painters build resolved styles, so they can't inherit the element's `text_style` the way a `Chunk` does.
  `ScreenView` gets its defaults from the emulator instead.
  If inheriting matters, `draw` could take the resolved text style as a third argument.
- **`utils.canvas` and `HalfBlocks` overlap.**
  `canvas()` could become a thin wrapper that returns a `Canvas`, or be deprecated.

## Part 2: how terminal multiplexers work

The research behind this section read tmux at [`f0a2ed3001`](https://github.com/tmux/tmux/tree/f0a2ed3001)
and zellij at [`dfa40f44a4`](https://github.com/zellij-org/zellij/tree/dfa40f44a4).
Both make the same pipeline, with the same stages:

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

### Emulators you can embed

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

## Part 3: embedding in counterweight

### The layers

```text
Canvas(draw=ScreenView(screen, show_cursor))            element: paints the snapshot, no text layout
  ^
use_terminal(argv, columns, rows) -> EmbeddedTerminal   headless: emulator, snapshots, input forwarding, focus
  ^
use_pty(argv, columns, rows, on_output) -> Pty          headless: PTY, child process, writes, resize, exit status
  ^
Emulator (place) -> Screen (value)                      emulator.py: the only module that knows about libghostty
```

`use_subprocess` (pipes, no PTY) wasn't built; it is `use_pty` without the terminal, and needs no emulator.

The embed needs no element of its own:
a component calls `use_terminal`, measures its own content box with `use_rects`, and returns a `Canvas`.
From `examples/multiplexer.py`:

```python
@component
def pane(pane_id: int, prefix: InputHandler, handle: FocusHandle, on_title: Callable[[str], None]) -> Canvas:
    content = use_rects().content
    terminal = use_terminal(SHELL, content.width, content.height, auto_focus=True, handle=handle)
    ...
    return Canvas(draw=terminal.view, style=fill(1) | border | ..., on_input=first(prefix, terminal.on_input))
```

The pane's size feeds back into the program's terminal size.
`use_rects` reports last frame's box, and an effect keyed on `(columns, rows)` resizes the PTY and the emulator.
So a resize shows the old screen, cropped or padded, for one frame, as tmux does.

### Output: places in the effect, values in the render

The emulator is mutable (a place).
It lives only inside `use_terminal`'s effects, which feed it on the event loop as the PTY becomes readable.
Rendering only ever sees `Screen` values:

- **Parse on read.**
  `loop.add_reader` on the master fd reads up to 64 KiB and feeds the emulator immediately.
  Since nothing is read faster than it's parsed, unparsed bytes never pile up.
  When the app falls behind, the kernel's PTY buffer fills and blocks the child,
  which is the backpressure tmux gets by disabling `EV_READ`.
- **Snapshot at most once per frame.**
  A read schedules a snapshot at most every `SNAPSHOT_INTERVAL` (1/60 s).
  The snapshot sets state, which re-renders the component.
  This is the coalescing zellij (8 ms), neovim (10 ms) and wezterm (3 ms) do.
  In the multiplexer, `seq 1 300000` took 0.18 s of wall time, and the UI stayed responsive.
- **Share unchanged rows.**
  `Screen` compares by identity, so a `Canvas` redraws only when the program's output changed.
  The emulator keeps each converted row by libghostty's row id while it isn't dirty.
  Unstyled cells are cached by their raw 64-bit value,
  which holds only a codepoint and a width when the cell has no style.
  A styled cell's raw value holds a page-local style id, so those can't be cached.

Reading cells through cffi costs several calls per cell, and that is now the bottleneck.
These are medians on a 120×40 screen after one line scrolls, when libghostty marks every row dirty:

| Output | Snapshot |
| --- | --- |
| plain text | 2.8 ms |
| every line colored | 10.5 ms |
| nothing changed | 0.1 ms |

A native binding that converts a row in one call would remove most of this cost (see [the emulator decision](#the-emulator-decision)).

### Input: when keys reach the program

The embed is a focusable component.
Its `on_input`, while focused, sends the program every key press and paste it can encode and claims them,
so nothing bubbles past it.

- **Keys** are re-encoded, as tmux does, rather than passed through, which counterweight couldn't do anyway:
  its input parser has already turned bytes into `KeyPressed`.
  `input_encoding.KEY_SEQUENCES` inverts `input_parsing`'s own tables, so the encoder and parser can't drift.
  Every `Key` round-trips through encode and parse, except `ctrl+h`, `ctrl+i` and `ctrl+m`
  (which terminals send as Backspace, Tab and Enter) and `shift+escape`.
  Cursor keys switch to `SS3` under DECCKM, which vim exercised.
- **Pastes** are wrapped in bracketed-paste markers when the program set `?2004`,
  with any end marker in the text dropped, so a paste can't end itself early.
- **Mouse events** inside the canvas are encoded only if the program enabled tracking,
  filtered by its tracking level, and translated to pane-local coordinates, as SGR or X10.
  A press also focuses the pane.
  Counterweight's press capture already does what terminals expect of a drag:
  the pane that claimed the press gets its motion and release, wherever the pointer goes.
- **The prefix key.**
  The DOM would intercept with a capture-phase listener on an ancestor.
  Counterweight only bubbles from the focused node, and that turned out not to matter:
  the multiplexer puts its prefix handler before the terminal's with `first(prefix, terminal.on_input)`.
  The embed exposes its handler, and composition does the rest.
- **Queries** are answered by libghostty from emulator state, and the replies are written back to the PTY.
  This covers CPR, DA1, DA2 and the other locally answerable queries, which is tier 1 of the three tiers in Part 2.
  Forwarding to the outer terminal is deferred: it has several plausible designs, and nothing has needed it yet.

### What the spike verified

The checks below ran `examples/multiplexer.py` inside a detached tmux session,
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

### Framework gaps the spike hit

These are changes to counterweight itself, which a multiplexer can't work around:

1. **Ctrl+C quits the host.**
   `start_input_control` turns off `ECHO` and `ICANON` but leaves `ISIG` and `IXON` on.
   So Ctrl+C is a `SIGINT` that quits the app, Ctrl+Z (`SIGTSTP`) stops it, Ctrl+\\ is `SIGQUIT`,
   and Ctrl+S/Ctrl+Q are eaten as flow control.
   None of them can reach an embedded program.
   The spike's test session died this way.
   An app that hosts terminals needs a raw input mode, which tmux puts its outer tty in: a knob on `app()`,
   with Ctrl+C then arriving as a key the app can bind to `Quit`.
2. **`FocusOn` can't focus a component that mounts in the same update.**
   The routing table doesn't know the new handle yet, so the control is dropped.
   The multiplexer works around it with `ClearFocus` and `auto_focus`.
   React's answer is an effect after mount that calls `ref.focus()`.
   Counterweight's effects can't return controls, so this needs either a pending `FocusOn` that applies after the render
   that mounts its target, or a way for an effect to send a control.
3. **A mode that changes routing must be readable synchronously.**
   `Ctrl+B %` in one read arrives as two key presses handled before the next render,
   so the second handler saw `is_armed=False` from its closure and sent `%` to the shell.
   The prefix state has to live in a `use_ref`, with state alongside only to re-render.
   `use_text_input` hits the same thing and solves it with updater functions.
   That's worth a documented pattern, since every modal key handler (vim-style modes, chords) hits it.
4. **Colors are truecolor only.**
   `Color` is RGB, so the program's palette indices and its "default" foreground and background
   are resolved to fixed RGB values (libghostty's default palette, and the `Emulator`'s defaults).
   An embedded `ls --color` uses xterm's red, not the user's theme's red.
   tmux keeps palette indices and default colors through to the outer terminal.
   Fixing this means `Color` gaining palette and default variants, and `output.py` emitting them.
5. **The cursor is drawn, not placed.**
   Counterweight hides the real cursor, so `ScreenView` draws a reversed cell.
   That loses cursor shapes (DECSCUSR), blinking, and the position input methods read.
   A framework way for the focused element to place the real cursor would serve `use_text_input` too.
6. **The key model is legacy.**
   `KeyPressed` can't represent what the kitty keyboard protocol adds
   (Ctrl+Shift+letter, key release, Ctrl+I distinct from Tab), so neither can the embed's encoder.
   libghostty's key encoder could produce kitty encodings once the input side carries the information.
7. **No focus events.**
   The embed doesn't send `CSI I`/`CSI O` under `?1004` when it gains and loses focus.
   This is cheap to add, with an effect keyed on `focus.is_focused`.

### The emulator decision

libghostty-vt fits best.
It is Ghostty's core, has the fidelity of a real terminal, and its API was designed for this kind of embedding.
That API covers dirty rows with stable ids, key, mouse, paste and focus encoders that read the terminal's modes,
reply callbacks, and color callbacks.
The cost is supply chain:

- `pyghostty` has had three releases since July 2026, the latest 0.1.3 two weeks ago.
- It bundles a prebuilt `libghostty-vt` from a pinned Ghostty revision, and libghostty-vt is pre-1.0.
- It is cffi in ABI mode: no compiler at install time, but no type information, and several calls per cell.

The alternative fits counterweight's own pattern.
waxy is PyO3 bindings to taffy, and the same could wrap an emulator crate
(`libghostty-rs`, `alacritty_terminal`, or `vt100`).
The binding would expose a snapshot that returns whole rows as Python tuples in one call.
That removes the 3 to 10 ms snapshot cost and gives typed stubs, at the price of building and maintaining another binding.
I'd keep the `Emulator`/`Screen` boundary either way: nothing outside `emulator.py` touches libghostty.

## Next steps

1. Land `Canvas` on its own, with tests, docs and a decision on the [open questions](#open-decisions-before-canvas-lands).
   It stands alone, and it is the prerequisite for everything else.
2. Fix [framework gaps](#framework-gaps-the-spike-hit) 1 to 3, which any app with modal keys or dynamic panes needs anyway.
3. Choose between `pyghostty` and an owned binding, then harden `use_pty`:
   EOF and exit together (tmux's `window_pane_destroy_ready`),
   a configurable `TERM`, and grandchildren that hold the PTY open.
4. Then `use_terminal` as a public headless component, and a `terminal` widget on top of it.
