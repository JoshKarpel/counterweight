#!/usr/bin/env just --justfile

alias t := test
alias w := watch
alias wt := watch-test
alias d := docs-serve
alias db := docs-build
alias ds := docs-screenshots
alias p := pre-commit

install:
  uv sync --extra dev

test:
  uv run mypy
  uv run pytest -vv --failed-first --cov --durations=10

watch CMD:
  uv run watchfiles '{{CMD}}' counterweight/ tests/ docs/ examples/

watch-test: (watch "just test")

docs-serve:
  uv run mkdocs serve

docs-build:
  uv run mkdocs build --strict

docs-screenshots:
  uv run docs/examples/generate-screenshots.sh

pre-commit:
  git add -u
  uv run pre-commit
  git add -u

profile FILE DURATION:
  austin --output profile.austin --exposure {{DURATION}} python {{FILE}}
  austin2speedscope profile.austin profile.ss
  reset
