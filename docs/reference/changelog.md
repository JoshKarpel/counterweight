# Changelog

## Next

## `0.0.3`

Release `2023-12-30`

### Changed

- [#71](https://github.com/JoshKarpel/counterweight/pull/71)
  Controls are now a union over different `@dataclass`es (instead of an `Enum`) to allow for more flexibility.
  The `Screenshot` control now takes a callback function which will be called with the SVG screenshot as an XML tree.
- [#81](https://github.com/JoshKarpel/counterweight/pull/81)
  Minimum Python version has been raised to `3.11.2` due to a bug in CPython `3.11.1` (https://github.com/python/cpython/issues/100098)

## `0.0.2`

Released `2023-12-26`

### Added

- [#65](https://github.com/JoshKarpel/counterweight/pull/65)
  Added ability to take an SVG "screenshot" by returning `Control.Screenshot` from an event handler.
  The screenshot will be saved to the current working directory as `screenshot.svg`; more options will be added in the future.
- [#66](https://github.com/JoshKarpel/counterweight/pull/66)
  Added "border healing": when border elements for certain border types are adjacent to each other and appear as if they
  should "join up", but don't because they belong to different elements, they will now be joined up.

### Changed

- Various namespaces moved around to make more sense (especially in documentation)
  and separate concerns better as part of [#68](https://github.com/JoshKarpel/counterweight/pull/68).

## `0.0.1`

Released `2023-12-19`
