#!/usr/bin/env just --justfile

test:
  mypy
  pytest --cov
