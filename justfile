#!/usr/bin/env just --justfile

alias t := test
alias w := watch

test:
  mypy
  pytest -v --cov --durations=10

watch CMD:
  watchfiles '{{CMD}}' reprisal/ tests/ docs/ examples/
