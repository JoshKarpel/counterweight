# `use_rects`

`use_rects` tells a component where the element it returns is on the screen,
as [`Rects`][counterweight.geometry.Rects]: the regions of its content, padding, border and margin boxes,
and how much of it its ancestors' clips leave visible.
A component can fit what it shows to the space layout gives it,
as a CSS [container query](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries) does.
Here each label shortens a path to fit its own width:

<!-- example: use_rects_path_label.py:example -->

![A wide pane showing the whole path, and a narrow one showing only focus.py](../assets/use-rects-path-label.svg)

Left and Right move the border between the panes, and each label follows its pane's width:

<!-- cast: use-rects-path-label -->

The label's width comes from its pane, never from its text, so the path it shows can't change the width it reads.
`full_width` stretches it across its pane, and `min_width(0)` lets it be narrower than its text
(see [Content sets a minimum size](../layout/how-layout-sizes-things.md#content-sets-a-minimum-size)).

!!! tip "Use `use_hovered` for detecting hover state"

    `use_rects` is a low-level hook.
    For the common use case of detecting whether the mouse is hovering over an element,
    use the higher-level [`use_hovered`](./use_hovered.md) hook instead.

## Measuring another element

Given an [`ElementHandle`][counterweight.focus.ElementHandle], `use_rects` reports the rectangles of the element
with that handle instead of the calling component's own top-level element,
as a React component measures an element through a ref and a `ResizeObserver`.
That's how a component measures an element a child component draws,
such as the viewport of a [`scroll_area`](../headless/use_scroll_area.md) it passes the handle to as `viewport`.
The handle comes from `use_state(ElementHandle)`, so it's the same on every render.
A handle that names no visible element reports empty rectangles,
as a component's first render does.

## Measuring the room around an element

`Rects.screen` is the region the app lays out in, in the same coordinates as the element's own boxes:
the terminal in [`FullScreen`][counterweight.FullScreen], and the region in [`Inline`][counterweight.Inline].
Beside the element's border box, it says how much room there is on each side of it,
as an `IntersectionObserverEntry` carries `rootBounds`, the viewport, beside `boundingClientRect`.
A popup that opens below its field while it fits there, and above it otherwise, decides from it:

```python
rects = use_rects()
below = rects.screen.bottom - rects.border.bottom
above = rects.border.top - rects.screen.top
opens_above = below < shown_rows and above > below
```

There's no anchor positioning to flip the popup in layout, as CSS's `position-try-fallbacks: flip-block` does,
so the decision comes from the last layout, and the popup moves when the component
[renders again](#when-it-renders-again), before the frame is painted.
The screen is the same for every element, and a component that reads it renders again when it changes,
even when none of its own boxes move: after the terminal resizes, and in `Inline`, whenever the root's height does.

## When it renders again

`use_rects` reports the rectangles as of the last layout,
and a component that calls it renders again as soon as any of the rectangles it read move,
whether its own state changed or something else, such as a sibling growing, moved them.
That happens before the frame is painted,
as a browser delivers [`ResizeObserver`](https://developer.mozilla.org/en-US/docs/Web/API/ResizeObserver)
notifications between layout and paint:
the render loop lays the tree out, re-renders the components whose rectangles moved,
and lays it out again, until nothing they read moves.
So in the example, the labels fit their new widths in the frame that moves the border between the panes,
and a component that mounts reads empty rectangles in its first render but is drawn from its real ones.

A component whose size depends on the rectangles it reads should settle:
one that grows whenever it reads its own size never does.
A frame re-renders a few times at most before it paints anyway,
leaving the rest to the next frame and logging a warning,
which it doesn't repeat until a frame settles,
and with `app`'s `check_purity` on, the app raises
[`UnsettledMeasurements`][counterweight.hooks.UnsettledMeasurements] instead.

Browsers bound that loop differently:
each round of `ResizeObserver` notifications reaches only the observers of elements
deeper in the tree than the shallowest the last round reached,
so a chain of elements nested inside each other settles however long it is,
but an element observed again at the same depth waits for the next frame,
with the "ResizeObserver loop completed with undelivered notifications" error.
A component re-renders when any of the rectangles it read move,
so one that lays out its rows from its own width, and so changes its own height,
as [`text_area`](../headless/use_text_area.md#a-styled-text-area) does,
would wait for the next frame every time it mounted.
Counting passes lets it settle on its second,
at the cost of cutting off a longer chain of components that each measure the last.

## API

::: counterweight.hooks.use_rects
::: counterweight.hooks.UnsettledMeasurements
::: counterweight.geometry.Rects
::: counterweight.geometry.Region
::: counterweight.geometry.Position
