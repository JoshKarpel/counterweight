# Changelog

## Next

### Removed

- [#165](https://github.com/JoshKarpel/counterweight/pull/165)
  Dropped support for Python `3.11`.

### Added

- [#123](https://github.com/JoshKarpel/counterweight/pull/123)
  Add styling for content area background color.

### Fixed

- [#125](https://github.com/JoshKarpel/counterweight/pull/125)
  Mouse wheel scroll events are now captured correctly
  (they were previously reported as mouse presses).
  The `check-input` CLI subcommand is also fixed
  (was broken by [#86](https://github.com/JoshKarpel/counterweight/pull/86)).

## `0.0.9`

Released `2024-02-27`

### Fixed

- [#121](https://github.com/JoshKarpel/counterweight/pull/121)
  A change in effect reconciliation introduced in `0.0.8` caused a regression in the behavior of `use_effect`,
  where if the `setup` function `return`ed (i.e., stopped itself),
  Counterweight would crash when trying to cancel the effect.
  This now works again.

## `0.0.8`

Released `2024-02-17`

### Changed

- [#110](https://github.com/JoshKarpel/counterweight/pull/110)
  Calling a `use_state` setter with a `value` equal to the current value of the state
  no longer emits a `SetState` event, to avoid triggering unnecessary render cycles.
- [#111](https://github.com/JoshKarpel/counterweight/pull/111)
  Border healing is now more efficient, especially when there are many non-border characters in the UI.
- [#112](https://github.com/JoshKarpel/counterweight/pull/112)
  Major, backwards-incompatible changes to how Counterweight handles mouse interactions.
  The `on_mouse_down` and `on_mouse_up` event handlers have been removed;
  use the new combined `on_mouse` event handler instead, which receives all mouse events
  ([`MouseMoved`][counterweight.events.MouseMoved],
  [`MouseDown`][counterweight.events.MouseDown], and
  [`MouseUp`][counterweight.events.MouseUp]).
  The `on_hover` style attribute on elements has been removed;
  use the new
  [`use_mouse`](hooks/use_mouse.md),
  [`use_rects`](hooks/use_rects.md),
  and [`use_hovered`](hooks/use_hovered.md)
  hooks instead, and calculate the desired style in your component.
  The goal of these changes is to provide more flexibility and control over mouse interactions
  to application authors while minimizing the work that Counterweight needs to do while rendering,
  at the cost of more complex application code for simple cases like detecting hover state.

## `0.0.7`

Released `2024-02-02`

### Changed

- [#105](https://github.com/JoshKarpel/counterweight/pull/105)
  `Screenshot` and `Suspend` handlers can now be `async` functions.

## `0.0.6`

Released `2024-01-28`

### Added

- [#92](https://github.com/JoshKarpel/counterweight/pull/92)
  Added an `inset` attribute to [`Absolute`][counterweight.styles.Absolute] that chooses which corner
  of the parent's context box to use as the origin for the absolute positioning.
- [#98](https://github.com/JoshKarpel/counterweight/pull/98)
  Added a `z` attribute to [`Flex`][counterweight.styles.Flex] that controls the stacking order of elements.

### Changed

- [#101](https://github.com/JoshKarpel/counterweight/pull/101)
  The `initial_value` of [`use_ref`][counterweight.hooks.use_ref] may now be a `Callable[[], T]` instead of just a `T`.

### Removed

- [#96](https://github.com/JoshKarpel/counterweight/pull/96)
  `Chunk`s can no longer be created with `CellPaint`s directly.

## `0.0.5`

Released `2024-01-06`

### Added

- [#86](https://github.com/JoshKarpel/counterweight/pull/86)
  Added a `Suspend` control which suspends the Counterweight application while a user-supplied callback function runs.
  Counterweight will stop controlling the terminal while the callback runs, and will resume when the callback returns.
  This can be used to run a subprocess that also wants control of the terminal (e.g., a text editor).
- [#88](https://github.com/JoshKarpel/counterweight/pull/88)
  [#90](https://github.com/JoshKarpel/counterweight/pull/90)
  Implemented [`Absolute`][counterweight.styles.Absolute] and [`Fixed`][counterweight.styles.Fixed]
  positioning, which allow for precise placement of elements outside the normal layout flow.

## `0.0.4`

Released `2023-12-31`

### Fixed

- [#83](https://github.com/JoshKarpel/counterweight/pull/83)
  Fixed virtual terminal escape code parsing for mouse tracking when the moues coordinates are large (>94 or so).
  Mouse tracking should now work for any terminal size.
  Various `Key` members that aren't currently parseable have been removed to avoid confusion.

## `0.0.3`

Released `2023-12-30`

### Changed

- [#71](https://github.com/JoshKarpel/counterweight/pull/71)
  Controls are now a union over different `@dataclass`es (instead of an `Enum`) to allow for more flexibility.
  The `Screenshot` control now takes a callback function which will be called with the SVG screenshot as an XML tree.
- [#81](https://github.com/JoshKarpel/counterweight/pull/81)
  The minimum Python version has been raised to `3.11.2` due to a [bug in CPython `3.11.1`](https://github.com/python/cpython/issues/100098)

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
