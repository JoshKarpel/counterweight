# Elements

Elements are what a [component](../components/index.md) returns: the boxes layout sizes and the screen draws,
as HTML elements are for a React component.
Each is an immutable value, a frozen dataclass, and there are three:

- [`Div`](div.md) is a box that holds other elements and components, as its `children`,
  and lays them out.
- [`Text`](text.md) is a leaf that holds text, as a string or as styled chunks,
  which layout measures and wraps.
- [`Canvas`](canvas.md) is a leaf whose cells a painter draws,
  for pictures, plots and anything else that isn't text.

All three take a `style` (see [Styles](../styles/index.md)),
an `on_input` handler that receives the [input events](../input-handling/events.md) delivered to them,
and a `handle` that names them for the [scroll controls](../layout/scrolling.md#scrolling-from-a-handler).

Below, a rounded `Div` lays out a `Canvas`, which draws a heart in half blocks,
beside a column `Div` of two `Text`s:
the first built from two chunks in different colors, and the second wrapping to the column's width.

<!-- example: elements_overview.py:example -->

![A Div holding a Canvas and two Texts](../assets/elements-overview.svg)

## API

::: counterweight.elements.AnyElement
