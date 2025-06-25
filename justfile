#!/usr/bin/env just --justfile

alias t := test
alias w := watch
alias wt := watch-test
alias ds := docs-screenshots
alias d := docs

install:
  uv sync --extra dev

test:
  uv run mypy
  uv run pytest -vv --failed-first --cov --durations=10

watch CMD:
  watchfiles '{{CMD}}' counterweight/ tests/ docs/ examples/

watch-test: (watch "just test")

docs-screenshots:
  docs/examples/generate-screenshots.sh

docs:
  mkdocs serve

pre-commit:
  git add -u
  uv run pre-commit

profile FILE DURATION:
  austin --output profile.austin --exposure {{DURATION}} python {{FILE}}
  austin2speedscope profile.austin profile.ss
  reset
