#!/usr/bin/env just --justfile

alias t := test
alias tw := test-watch

test:
  mypy
  pytest -v --cov --durations=10

test-watch:
  watchfiles 'just test' reprisal/ tests/ docs/ examples/ justfile
