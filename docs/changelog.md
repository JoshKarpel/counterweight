# Changelog

## `Next`

### Added

- Added ability to take an SVG "screenshot" by returning `Control.Screenshot` from an event handler
  [#65](https://github.com/JoshKarpel/counterweight/pull/65).
  The screenshot will be saved to the current working directory as `screenshot.svg`; more options will be added in the future.
- Added "border healing": when border elements for certain border types are adjacent to each other and appear as if they
  should "join up", but don't because they belong to different elements, they will now be joined up
  [#66](https://github.com/JoshKarpel/counterweight/pull/66).

## `0.0.1`

Released `2023-12-19`
