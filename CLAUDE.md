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
- **Hooks** (src/counterweight/hooks/): State management (`use_state`), side effects (`use_effect`), and UI interactions (`use_mouse`, `use_hovered`)
- **App** (src/counterweight/app.py): Main application loop that handles rendering, input, and event processing
- **Styles** (src/counterweight/styles/): Tailwind-inspired utility classes and styling system
- **Paint/Rendering** (src/counterweight/paint.py, src/counterweight/output.py): Terminal rendering engine that converts components to terminal output

The entry point is typically through `counterweight.app.app()` which starts the main application loop.

## Development Commands

This project uses [Just](https://github.com/casey/just) as the task runner. Key commands:

```bash
# Install dependencies
just install

# Run tests with type checking and coverage
just test

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
- **benchmarks/**: Deterministic render-loop workloads, profiled with `just profile` (see the `cw-profile` skill)
- **docs/**: MkDocs documentation with examples and API reference

## Key Dependencies

- **pydantic**: Data validation and settings
- **typer**: CLI interface
- **without-logging**: The devlog, written off the render loop from stdlib `logging` records
- **parsy**: Parser combinators for terminal input
- **wcwidth**: How many terminal cells each grapheme cluster of text takes
- **more-itertools**: Extended iteration utilities

## Code Style Guidelines
- Line length: 120
- Strict typing: All functions must be fully typed
- Formatting and linting: Run `uv run pre-commit` to enforce
- Use pathlib instead of os.path
- Follow PEP 8 conventions for naming
- Use rich for terminal output
- Pydantic for data modeling
- Use pytest for testing
- No implicit optional types
- Don't write lots of comments; the code and test names should be self-explanatory.
