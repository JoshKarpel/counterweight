# Scrolling

A box whose overflow is `Scroll` is a **scroll container**:
its content can be larger than it, and it shows the part its offset scrolls into view.
This page covers making one, scrolling it with the wheel and from handlers,
and reading how far it's scrolled.
[Clipping](clipping.md) covers how a scroll container cuts off what's outside its padding box,
which it does as a box with hidden overflow does.

## Scroll containers

`overflow_scroll` makes a box a scroll container on both axes,
and `overflow_x_scroll` and `overflow_y_scroll` on one,
as CSS's [`overflow: scroll`](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow) does.
On an axis it scrolls, the box clips its children to its padding box,
and moves them up and left by its offset.

Counterweight holds each scroll container's offset, as a browser holds an element's `scrollTop`,
so a box scrolls without any state in the component that renders it.
It starts at 0, the start of the content, and is clamped after every layout to how far the content reaches,
so when the content shrinks, the box scrolls back as far as it has to.
A scroll container that unmounts or is hidden loses its offset, and starts at 0 again when it comes back.

How far a box can scroll is how far its content reaches past its padding box, as on the web.
That includes its absolutely positioned descendants, so a dropdown that opens past the bottom of a scrolling form
lets the form scroll down to show it
(see the [autocomplete recipe](../cookbook/autocomplete.md#inside-a-scroll-container)).

A scroll container's automatic minimum size is 0, as one with hidden overflow's is
(see [Content sets a minimum size](how-layout-sizes-things.md#content-sets-a-minimum-size)),
so a flex item that scrolls shrinks to fit beside its siblings instead of growing to fit its content.
That's usually what a scrolling pane wants;
give it a size, or `shrink(0)`, when it should be as large as its content up to some limit.

A `Text` doesn't scroll its own text, so a `Text` whose overflow is `Scroll` raises `ValueError`:
put a long `Text` in a `Div` that scrolls.

## Scrolling with the wheel

Nothing scrolls unless a handler scrolls it, as with every other input,
so a scroll container that the wheel should scroll composes
[`scroll_on_wheel`](../input-handling/handlers.md#scrolling) into its `on_input`.
A titled pane puts its border and title on a box around the part that scrolls,
so they stay put while the content moves:

```python
--8<-- "scrolling.py:pane"
```

=== "Before"

    ![A titled pane showing the first lines of a log](../assets/scrolling-pane.svg)

=== "After two wheel notches"

    ![The pane scrolled six lines down](../assets/scrolling-pane-wheeled.svg)

A wheel event goes to the element under the pointer and bubbles from there,
so of nested scroll containers, the innermost under the pointer scrolls.
`scroll_on_wheel` lets an event that would move its container past either end of its range bubble on,
so once the inner one reaches its end, the wheel scrolls the one around it,
as the web chains scrolling from one container to the next.

## Scrolling from a handler

The [`ScrollTo`](../input-handling/controls.md#scrolling) and `ScrollBy` controls scroll a container
to an offset, or by an amount, clamped to its range.
A handler on the scroll container itself names it by its receiver's `subtree`, as `scroll_on_wheel` does.
A handler anywhere else names it by an `ElementHandle`, as a React component reaches a DOM node through a ref:
create one with `use_state(ElementHandle)`, and pass it to the element's `handle`.

```python
--8<-- "scrolling.py:controls"
```

![The log scrolled to its end by the Bottom button](../assets/scrolling-controls.svg)

Two mounted elements given the same handle raise `DuplicateElementHandle`,
and a control whose handle names no mounted scroll container does nothing.

## Reading the scroll

[`use_scroll`](../hooks/use_scroll.md) returns a [`Scroll`][counterweight.hooks.Scroll]: how far the calling component's top-level element is scrolled,
how far it can be, and the size of its padding box, the part of the content in view.
A handler's [`Receiver`][counterweight.events.Receiver] carries the same for a receiving element that's
a scroll container, which is how `scroll_on_wheel` knows whether its container can move any further.

Like [`use_rects`](../hooks/use_rects.md), `use_scroll` reports the previous frame's scroll,
and a component that calls it renders again as soon as it changes.
A list too long to render whole can render only the rows in view, with empty boxes above and below them
so the content is as tall as every row would make it, as React's windowing libraries do:

```python
--8<-- "scrolling.py:windowed"
```

![Rows six to nine of a hundred thousand](../assets/scrolling-windowed.svg)

The rows on each side of the view cover the frame between a scroll and the render that follows it,
which would otherwise show the empty boxes.

## Where scrolled boxes are

Scrolling moves boxes, so everything that reports where a box is reports where it's painted:
[`use_rects`](../hooks/use_rects.md), a receiver's `rects`, the element the mouse is over,
and [`use_hovered`](../hooks/use_hovered.md).
A box scrolled partly out of view is still whole there, with its `visible` region the part in view,
as for any box that's [clipped](clipping.md#clipping-and-the-mouse).

## API

::: counterweight.focus.ElementHandle
::: counterweight.shadow.DuplicateElementHandle
