#!/usr/bin/env just --justfile

set ignore-comments := true

[default]
[doc('List available recipes')]
list:
    just --list

[doc('Run a recipe whenever source files change')]
watch CMD:
    uv run watchfiles --verbosity warning 'just {{ CMD }}' counterweight/ tests/ docs/ examples/

alias w := watch

[doc('Stage updated files and run pre-commit hooks')]
pre-commit:
    git add --update
    uv run pre-commit

alias p := pre-commit

[doc('Run type checking and tests with coverage')]
test:
    uv run mypy
    uv run pytest -vv --failed-first --cov --durations=10

alias t := test

[doc('Serve documentation locally')]
docs-serve:
    uv run mkdocs serve

alias d := docs-serve

[doc('Build documentation with strict mode')]
docs-build:
    uv run mkdocs build --strict

alias db := docs-build

[doc('Profile a Python file with austin and convert to speedscope format')]
profile FILE DURATION:
    austin --output profile.austin --exposure {{ DURATION }} python {{ FILE }}
    austin2speedscope profile.austin profile.ss
    reset

[doc('Upgrade all dependencies')]
upgrade:
    uv lock --upgrade

alias update := upgrade
alias u := upgrade
