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

## Architecture

The framework follows a React-like architecture:

- **Components** (src/counterweight/components.py): Declarative functions decorated with `@component` that return elements and manage state through hooks
- **Elements** (src/counterweight/elements.py): Core UI primitives like `Div` and `Text`, with style and event handling capabilities
- **Hooks** (src/counterweight/hooks/): State management (`use_state`), side effects (`use_effect`), and UI interactions (`use_mouse`, `use_hovered`, `use_focus`, `use_text_input`)
- **App** (src/counterweight/app.py): Main application loop that handles rendering, input, and event processing
- **Routing** (src/counterweight/routing.py): Which handlers an input event reaches: its target (the focused node for keys), bubbling, and press capture; and where focus can move
- **Handlers** (src/counterweight/handlers.py): Library input handlers (`on_click`, `tab_focus`, `focus_receiver_on_press`, ...) and combinators (`first`, `each`)
- **Text editing** (src/counterweight/text_editing.py): The pure core of `use_text_input`: which edit each key press or paste makes, and what it does to a value and a cursor
- **Widgets** (src/counterweight/widgets.py): Styled components built on headless hooks, such as `text_input`
- **Styles** (src/counterweight/styles/): Tailwind-inspired utility classes and styling system
- **Paint/Rendering** (src/counterweight/paint.py, src/counterweight/output.py): Terminal rendering engine that converts components to terminal output

The entry point is typically through `counterweight.app.app()` which starts the main application loop.

## Development Commands

This project uses [Just](https://github.com/casey/just) as the task runner. Key commands:

```bash
# Install dependencies
just install

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

When a utility family covers a set of variants (such as safe and `_unsafe` alignment),
generate every member of it (see [Public API Scope](#public-api-scope)).

`docs/styles/utilities.md` lists every public utility through `<!-- utilities: <glob> ... -->` markers,
which `mkdocs_hooks/utility_tables.py` renders from the module.
The docs build fails until each new utility, generated or hand-written, matches exactly one marker,
and hand-written utility functions need a docstring to describe them there.

## Docs Screenshots

Each module in `docs/examples/` declares the screenshots it produces in a `SCREENSHOTS` list,
and pages include its code between `--8<--` snippet markers.
Run one in the terminal with `uv run python -m docs.examples.<module> [root]`, naming a root function to pick
among several; running it by path fails, since the examples import from the `docs` package.
Regenerate them with `uv run python -m docs.examples.generate_screenshots [module ...]`
(the pre-commit hook runs it too).
Every `docs/assets/<name>.svg` has a plain-text twin, `<name>.txt`:
read that to check a layout instead of the SVG.
`mkdocs_hooks/screenshot_tabs.py` shows both in the built docs.

## Project Structure

- **src/counterweight/**: Main framework code
  - **hooks/**: React-like hooks for state and side effects
  - **styles/**: Styling system with utilities
- **examples/**: Complete example applications (wordle.py, chess.py, etc.)
- **tests/**: Test suites organized by module
- **benchmarks/**: Deterministic render-loop workloads, profiled with `just profile`, and input-parsing timings (see the `cw-profile` skill)
- **docs/**: MkDocs documentation with examples and API reference

## Key Dependencies

- **pydantic**: Data validation and settings
- **without-cli**: The `counterweight` CLI and the benchmark CLI
- **without-logging**: The devlog, written off the render loop from stdlib `logging` records
- **wcwidth**: How many terminal cells each grapheme cluster of text takes
- **more-itertools**: Extended iteration utilities

## Code Style Guidelines
- Line length: 120
- Strict typing: All functions must be fully typed
- Formatting and linting: Run `uv run pre-commit` to enforce
- Use pathlib instead of os.path
- Follow PEP 8 conventions for naming
- Pydantic for data modeling
- Use pytest for testing
- Line and branch coverage of `src/counterweight` and `tests` is held at 100% (`fail_under` in `pyproject.toml`),
  so new code comes with the tests that run it.
  Mark a function a test builds only to compare or inspect (a handler `equivalent` compares) `# pragma: never runs`,
  and use `# pragma: no cover` only for code the suite can't run, saying why.
- No implicit optional types
- Don't write lots of comments; the code and test names should be self-explanatory.
