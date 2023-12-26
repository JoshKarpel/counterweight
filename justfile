#!/usr/bin/env just --justfile

alias t := test
alias w := watch
alias wt := watch-test
alias ds := docs-screenshots
alias wds := watch-docs-screenshots
alias d := docs

test:
  mypy
  pytest -vv --failed-first --cov --durations=10

watch CMD:
  watchfiles '{{CMD}}' counterweight/ tests/ docs/ examples/

watch-test: (watch "just test")

docs-screenshots:
  docs/examples/generate-screenshots.sh

watch-docs-screenshots: (watch "just docs-screenshots")

docs:
  mkdocs serve
