# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Counterweight is an experimental text user interface (TUI) framework for Python, inspired by React and Tailwind CSS.
It builds declarative TUI applications using a component-based architecture with hooks for state management and styles for visual presentation.

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

## Project Structure

- **src/counterweight/**: Main framework code
  - **hooks/**: React-like hooks for state and side effects
  - **styles/**: Styling system with utilities
- **examples/**: Complete example applications (wordle.py, chess.py, etc.)
- **tests/**: Test suites organized by module
- **docs/**: MkDocs documentation with examples and API reference

## Key Dependencies

- **pydantic**: Data validation and settings
- **typer**: CLI interface
- **structlog**: Structured logging
- **parsy**: Parser combinators for terminal input
- **more-itertools**: Extended iteration utilities

## Code Style Guidelines
- Line length: 120
- Strict typing: All functions must be fully typed
- Formatting and linting: Run `uv run pre-commit` to enforce
- Use pathlib instead of os.path
- Follow PEP 8 conventions for naming
- Use rich for terminal output
- Use frozen dataclasses for data modeling (pydantic has been removed)
- Use pytest for testing
- No implicit optional types
- Don't write lots of comments; the code and test names should be self-explanatory.
