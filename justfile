#!/usr/bin/env just --justfile

set ignore-comments := true

[default]
[doc('List available recipes')]
list:
    just --list

alias l := list

[doc('Run a recipe whenever source files change')]
watch *CMD:
    uv run watchfiles --verbosity warning '{{ CMD }}' src/ tests/ docs/ examples/

alias w := watch

[doc('Stage updated files and run pre-commit hooks')]
pre-commit:
    git add --update
    uv run pre-commit

alias p := pre-commit

[doc('Run type checking and tests')]
test:
    uv run mypy
    uv run pytest --failed-first

alias t := test

[doc('Serve documentation locally')]
docs-serve:
    uv run mkdocs serve

alias d := docs-serve

[doc('Build documentation with strict mode')]
docs-build:
    uv run mkdocs build --strict

alias db := docs-build

[doc('Profile a Python file with scalene')]
profile FILE:
    -uv run scalene run --cpu-only --profile-all {{ FILE }}
    uv run scalene view --cli --reduced

[doc('Regenerate style utility constants from codegen/generate_utilities.py')]
codegen:
    uv run python codegen/generate_utilities.py

alias c := codegen

[doc('Run the counterweight devlog')]
devlog *ARGS:
    @uv run counterweight devlog {{ ARGS }}

alias dl := devlog

[doc('Upgrade all dependencies')]
upgrade:
    uv lock --upgrade

alias update := upgrade
alias u := upgrade
