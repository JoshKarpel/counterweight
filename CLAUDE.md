# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Counterweight is an experimental text user interface (TUI) framework for Python, inspired by React and Tailwind CSS.
It builds declarative TUI applications using a component-based architecture with hooks for state management and styles for visual presentation.

## Public API Scope

Counterweight is a framework, so the people who need a feature are its users,
and the examples, docs, and tests in this repository are only a sample of what they'll build.
"Nothing here needs it yet" is not a reason to omit or defer public API.
When a feature fits the design and is cheap to build, test, and document,
build it with the change that makes it obvious:
every variant in a family of utilities,
or an option that browsers or React offer beside the one a change adds.
Defer only what is expensive, or what has several plausible designs and no way yet to choose between them,
and say which of those it is.

This applies to the API users call, not to internal structure:
don't add abstractions to the implementation ahead of a change that needs them.

## Types Are the Contract

Assume users type-check their code with mypy in strict mode.
The public API's type annotations are its contract,
so don't add runtime checks or coercions for input the types already reject,
such as a `list` where a `tuple` is annotated.
They cost time on every call (often on the render path) to help only code that is already a type error.

## Ask How the Web Does It

Counterweight borrows its models from browsers and React,
so when a design question is open, first find out how the web answers it
(CSS, the DOM, HTML elements, React's APIs, and the patterns apps build on them),
and write that answer into the plan, issue or PR beside the design.
It's the starting point, not the verdict:
where counterweight differs (cells instead of pixels, taffy's layout,
effects that start after the frame paints), say what the difference changes
and why the design diverges.

## Where Caches Go

Put a cache where the repeats it serves can be seen.

- **Shared, at the source** (`lru_cache`, `@flyweight`): values keyed by something from a small set
  that recurs across nodes and frames, such as a grapheme, a style, or a short piece of text.
  However large the app, the keys in use stay few, so a fixed `maxsize` holds them.
- **Per node, on the consumer** (the shadow node, a `memo` component, or the layout tree's texts and placements):
  values keyed by one node's content or geometry, such as the lines of a document or a node's place on screen.
  How many keys are live grows with the app, and a shared cache that sees more keys a frame than its `maxsize`,
  in the same order every frame, gets no hits and evicts everything else in it.
  Kept on the node, the entries are freed when the node is.
- **Both, layered,** when both kinds of repeat are real: the node's cache in front and the shared one behind,
  so only the node's misses reach it, as `MeasurableText.of` does in front of `styled_cells`.

Before adding or moving a cache, check its hit rate (`cache_info()`) on a workload whose content is larger than its `maxsize`.

## Architecture

The framework follows a React-like architecture:

- **Components** (src/counterweight/components.py): Declarative functions decorated with `@component` that return elements and manage state through hooks
- **Elements** (src/counterweight/elements.py): Core UI primitives like `Div`, `Text` and `Canvas`, with style and event handling capabilities
- **Painters** (src/counterweight/painters/): What draws a `Canvas`'s cells, one module per kind of picture, such as `pixels` (`Pixels` and `HalfBlocks`), `terminal` (`ScreenView` and `Transcript`), and `frames` (`PaintView`, what `Paint.as_painter` makes of a region of a frame)
- **Emulator** (src/counterweight/emulator.py): The terminal emulator (libghostty-vt) behind `Emulator`, a place fed a program's output, which snapshots into immutable `Screen` values; nothing else touches libghostty
- **One-shot commands** (src/counterweight/commands.py): `use_command`, which runs a program on a pseudo-terminal when asked, feeds an emulator, and snapshots it at most once a frame into `CommandRun` values whose output is a `Transcript` painter, and `command_output`, the widget that shows a run
- **Embedded terminals** (src/counterweight/headless/terminal.py, src/counterweight/input_encoding.py): `use_terminal`, which runs an interactive program on a pseudo-terminal while its component is mounted, feeds an emulator, snapshots it at most once a frame into `Screen` values, and sends the program the input its focused `Canvas` receives, re-encoded by `input_encoding`'s pure functions (the inverse of `input_parsing`); the `terminal` widget is built on it
- **Programs on the app's terminal** (src/counterweight/programs.py): `run_program`, which runs a program on the terminal a suspended app hands back, swallowing the Ctrl+C meant for it, and `edit_file` and `edit_text`, which edit a file or a string in the user's editor; `Suspend.to_program`, `Suspend.to_edit_file` and `Suspend.to_edit_text` run them; also `Exited`, `FailedToStart` and `TimedOut`, how any program ends
- **Pseudo-terminals** (src/counterweight/pseudoterminal.py): Runs a program on a pseudo-terminal and hands back the bytes it writes: `run_pty` until it exits, and `use_pty` while a component is mounted; hangs the program's process group up when it ends, which the hooks leave to the app's task group so it doesn't hold up rendering
- **Hooks** (src/counterweight/hooks/): State and side effects (`use_state` and its `toggle`, `use_ref`, `use_memo`, `use_effect`, `use_clock`, `use_controls`), animation built on `use_clock` (`use_progress`, `use_loop`), and what the UI looks like now (`use_rects`, `use_scroll`, `use_mouse`, `use_hovered`, `use_focus`)
- **Animation** (src/counterweight/animation.py): The pure half of animation: CSS's easing functions (`linear`, `piecewise_linear`, `cubic_bezier` and its named curves, `steps`) and `between`, which picks a phase out of an animation's progress
- **App** (src/counterweight/app.py): Main application loop that handles rendering, input, and event processing; it makes its own event queue, task group and mouse listeners current only while it renders (`app_scope` in `_context_vars.py`), so a hook that needs one later captures it while rendering, and an app can run inside another
- **Autopilot** (src/counterweight/autopilot.py): What an autopilot drives an app with beyond events and controls, `Wait` and `WaitFor`, which hold it back until real time passes or the screen shows something, the steps built from them and from events (`typed`, `showing`, `advance`), and the `Autopilot` that hands the render loop its next step
- **Recording** (src/counterweight/asciicast.py): `Recording`, which records an app as an asciicast v3 file, the pure encoding of its lines, and the `Recorder` the render loop records each frame's diff, input, resizes, markers and its exit into, timed by the app's clock with suspensions cut out
- **Shadow tree** (src/counterweight/shadow.py): Runs components and reconciles each render's elements, by key, into the tree of nodes that holds their hooks
- **Layout** (src/counterweight/layout.py): Lays the shadow tree out with [waxy](https://github.com/JoshKarpel/waxy) (taffy's flexbox and grid), wraps text, settles scroll offsets (anchoring, sticking to the end, the scroll controls), and clips
- **Events and controls** (src/counterweight/events.py, src/counterweight/controls.py): What handlers receive (key presses, pastes, mouse events, and the `Receiver`) and what they return to act on the app (`Quit`, the focus and scroll controls, ...)
- **Focus** (src/counterweight/focus.py): The values controls name their targets by: `FocusHandle` (a focusable component), `ElementHandle` (an element, to scroll), and `Subtree` (part of the tree)
- **Input** (src/counterweight/input_parsing.py, src/counterweight/input.py): Pure, incremental parsing of terminal bytes into events, the raw terminal mode that lets every key through, and the reader on the event loop that feeds the parser and times out cut-off escape sequences and pastes
- **Routing** (src/counterweight/routing.py): Which handlers an input event reaches: its target (the focused node for keys), bubbling, press capture, and the default control of a key press nothing claims; and where focus can move
- **Handlers** (src/counterweight/handlers.py): Library input handlers (`on_click`, `tab_focus`, `focus_receiver_on_press`, ...) and combinators (`first`, `each`)
- **Headless components** (src/counterweight/headless/): Hooks that give a component a common control's behavior and leave drawing it to the component, such as `use_text_input`, `use_text_area` and `use_scroll_area`, the text ones each beside its pure core (`text_editing.py`, `text_area_editing.py`): which edit each key press or paste makes, and what it does to a value and a cursor
- **Widgets** (src/counterweight/widgets.py): Styled components built on headless components, such as `text_input`, `text_area` and `scroll_area`
- **Styles** (src/counterweight/styles/): Tailwind-inspired utility classes and styling system; colors are RGB `Color`s, or `IndexedColor` and `TERMINAL_DEFAULT`, which the terminal decides and so follow the user's theme
- **Gradients** (src/counterweight/gradients.py): Linear, radial and conic gradients any color slot can hold, and the pure functions paint draws them with: a `Ramp` of colors keyed by the stops, and `field_indices`, the ramp entry each cell takes, keyed by the geometry and the box's size
- **Paint/Rendering** (src/counterweight/paint.py, src/counterweight/output.py): Terminal rendering engine that converts components to terminal output; each slot that holds a gradient paints from fields its element keeps per node in `LayoutTree.fields`, and each solid slot fills with one cell
- **Rich text** (src/counterweight/markdown.py, src/counterweight/highlighting.py): Pure functions that turn Markdown and source code into elements and chunks, and `markdown_document`, the `memo` component that renders a Markdown document

The entry point is typically through `counterweight.app.app()` which starts the main application loop.

## Development Commands

This project uses [Just](https://github.com/casey/just) as the task runner. Key commands:

```bash
# Install Just and uv (pinned in mise.toml), then the dependencies
mise install
uv sync

# Run type checking, then the tests with coverage, passing any arguments on to pytest
just test [-k pattern | tests/test_paint.py ...]

# Run mutation testing (mutmut), or re-run only the named mutants (see the cw-mutate skill)
just mutate ['counterweight.shadow.*']

# Build the documentation
just docs-build

# Lint and format code
just pre-commit
```

## Style Utilities Codegen

`src/counterweight/styles/utilities.py` contains a large section of generated utility constants
(between `# Start generated` and `# Stop generated` markers) as well as hand-written helpers below
the `# Stop generated` marker.

**Never edit the generated section by hand.** To add or change generated utilities, edit
`codegen/generate_utilities.py` and then run:

```bash
just codegen
```

Codegen also writes the module's `__all__`, at the end of the file, from every public name the module defines,
so a new hand-written utility joins it on the next `just codegen` (or commit) and nothing edits it by hand.

When a utility family covers a set of variants (such as safe and `_unsafe` alignment),
generate every member of it (see [Public API Scope](#public-api-scope)).

`docs/styles/utilities.md` lists every public utility through `<!-- utilities: <glob> ... -->` markers,
which `mkdocs_hooks/utility_tables.py` renders from the module.
The docs build fails until each new utility, generated or hand-written, matches exactly one marker,
and hand-written utility functions need a docstring to describe them there.

## Logo

`codegen/generate_logo.py` draws every file in `docs/assets/logo/`
from the JetBrains Mono outlines in `codegen/fonts/`, so `just codegen` regenerates them and nothing edits them by hand.
They live apart from the screenshots because the screenshot generator fails on any `docs/assets/*.svg` no example writes.
The favicon's PNGs aren't committed, because Pillow encodes the same pixels to different bytes on macOS and Linux:
`mkdocs_hooks/logo_icons.py` draws them into the site on every docs build.
The text logo in `counterweight --help` is `LOGO` in `src/counterweight/cli.py`.

## Docs Screenshots

Each module in `docs/examples/` declares the screenshots it produces in a `SCREENSHOTS` list.
A page shows a section of one with a `<!-- example: <module>.py:<section> -->` line outside any code block,
which `mkdocs_hooks/examples.py` replaces with the code between the module's `# --8<-- [start:<section>]`
and `# --8<-- [end:<section>]` comments,
so every Python code block in a page is real Python that ruff can format.
Run one in the terminal with `uv run python -m docs.examples.<module> [root]`, naming a root function to pick
among several; running it by path fails, since the examples import from the `docs` package.
Regenerate them with `uv run python -m docs.examples.generate_screenshots [module ...]`
(the pre-commit hook runs it too).
Every `docs/assets/<name>.svg` has a plain-text twin, `<name>.txt`:
read that to check a layout instead of the SVG.
`mkdocs_hooks/screenshot_tabs.py` shows both in the built docs.

A module may also declare recordings in a `CASTS` list of `CastSpec`s, which the same command records,
with a frozen clock, to `docs/assets/<name>.cast`; `paced` puts a pause before each step and holds on the last.
A page plays one with a `<!-- cast: <name> -->` line, which `mkdocs_hooks/casts.py` replaces
with the element `docs/assets/casts.js` starts the vendored asciinema-player in.
Files in `docs/assets/vendor/` are third-party releases, kept byte for byte as published with their licenses,
which pre-commit leaves alone.

## Project Structure

- **src/counterweight/**: Main framework code
  - **hooks/**: React-like hooks for state and side effects
  - **styles/**: Styling system with utilities
- **examples/**: Complete example applications (wordle.py, chess.py, etc.)
- **tests/**: Test suites organized by module
- **benchmarks/**: Deterministic render-loop workloads, profiled with `just profile`, and input-parsing and emulator snapshot timings (see the `cw-profile` skill)
- **docs/**: MkDocs documentation with examples and API reference

## Key Dependencies

- **waxy**: The layout engine, Python bindings to [taffy](https://github.com/DioxusLabs/taffy)'s flexbox and grid
- **without-cli**: The `counterweight` CLI and the benchmark CLI
- **without-logging** and **without-streams**: The devlog, written off the render loop from stdlib `logging` records
- **wcwidth**: How many terminal cells each grapheme cluster of text takes
- **more-itertools**: Extended iteration utilities
- **markdown-it-py**: Parses Markdown for `counterweight.markdown`
- **mdit-py-plugins**: The GitHub Flavored Markdown, math, and front matter rules `counterweight.markdown` parses with
- **pygments**: Lexes and colors source code for `counterweight.highlighting`
- **pyghostty**: libghostty-vt's cffi bindings, the terminal emulator behind `counterweight.emulator`
- **pillow**: Decodes images for `Pixels.from_image`, which counterweight itself never imports, and draws the logo's PNGs
- **fonttools** (dev): Outlines the logo's letters for `codegen/generate_logo.py`

## Code Style Guidelines
- Line length: 120
- Strict typing: All functions must be fully typed
- Formatting and linting: Run `just pre-commit` to enforce
- Use pathlib instead of os.path
- Follow PEP 8 conventions for naming
- Frozen, slotted dataclasses for data modeling
- Use pytest for testing
- Line and branch coverage of `src/counterweight` and `tests` is held at 100% (`fail_under` in `pyproject.toml`),
  so new code comes with the tests that run it.
  Mark a function a test builds only to compare or inspect (a handler `equivalent` compares) `# pragma: never runs`,
  a line only Linux or only macOS runs `# pragma: linux only` or `# pragma: macos only`,
  which coverage ignores on the other platform (see `coverage_conditional_plugin` in `pyproject.toml`),
  and use `# pragma: no cover` only for code the suite can't run on any platform, saying why.
- No implicit optional types
- Don't write lots of comments; the code and test names should be self-explanatory.
