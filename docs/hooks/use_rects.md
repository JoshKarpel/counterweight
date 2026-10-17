# `use_rects`

## API

::: counterweight.hooks.use_rects
::: counterweight.hooks.Rects
::: counterweight.geometry.Region

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
A handle that named no visible element in the previous render reports empty rectangles,
as the first render does.

## When it renders again

`use_rects` reports the previous frame's rectangles,
and a component that calls it renders again as soon as any of the rectangles it read move,
whether its own state changed or something else, such as a sibling growing, moved them.
A component whose size depends on the rectangles it reads should settle:
one that grows whenever it reads its own size renders without end.
