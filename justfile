#!/usr/bin/env just --justfile

alias t := test
alias tw := test-watch

test:
  mypy
  pytest --cov

test-watch:
  watchfiles 'just test' reprisal/ tests/ docs/
