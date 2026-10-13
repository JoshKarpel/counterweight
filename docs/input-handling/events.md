# Events

## Handling Input

`Div` and `Text` elements take an `on_input` handler,
which Counterweight calls with key presses and mouse events,
along with a [`Receiver`][counterweight.events.Receiver] describing the element the event is delivered to.
A handler matches on the event, so one case can cover a key and a mouse event alike:

```python
def on_input(event: InputEvent, _: Receiver) -> InputResponse:
    match event:
        case KeyPressed(key=Key.Down) | MouseScrolledDown():
            set_offset(lambda o: o + 1)
            return ()
        case KeyPressed(key=Key.Up) | MouseScrolledUp():
            set_offset(lambda o: o - 1)
            return ()
        case _:
            return None
```

A handler's return value says whether the event was its to handle:

- `None` means it wasn't, and the event [bubbles](#routing-input-events) on to the element's parent.
- Anything else means it was, and the event stops there.
  That is a [control](controls.md) for Counterweight to apply (`return Quit()`),
  a tuple of controls applied in order (`return Bell(), Screenshot.to_file(path)`),
  or `()`, a tuple of no controls, when there's nothing else to do.
  A `None` inside a tuple is skipped, so a control can be conditional
  (`return Bell() if is_full else None, Screenshot.to_file(path)`),
  and a tuple still stops the event when every item in it is `None`.

Return `()` (or the controls) from every case that does something,
so an ancestor that handles the same event doesn't act on it too.

!!! warning "Don't chain handlers with `or`"

    `()` is falsy, so `handler_a(event, receiver) or handler_b(event, receiver)`
    calls `handler_b` even when `handler_a` handled the event.
    Compose handlers with [`first` and `each`](handlers.md) instead.

A handler that only cares about keys still receives mouse events,
including every movement of the pointer over its element.
One that matches many keys can return early on anything else, which keeps its cases about keys alone:

```python
def on_input(event: InputEvent, _: Receiver) -> InputResponse:
    if not isinstance(event, KeyPressed):
        return None

    match event.key:
        case Key.ControlC:
            return Quit()
        case Key.Tab:
            set_tab(lambda t: (t + 1) % len(TABS))
            return ()
        case _:
            return None
```

The receiver describes the element the event is delivered to.
Its rectangles tell a handler where in the element a mouse event landed:

```python
def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
    match event:
        case MouseDown(absolute=position, button=1):
            set_clicked(receiver.relative(position))
            return ()
        case _:
            return None
```

Its `is_focused`, `focus_handle` and `subtree` serve the [focus](../hooks/use_focus.md) handlers:
whether the element is focused, the handle that names its component if the component is focusable,
and the element and its descendants, for moving focus among them.

::: counterweight.events.InputEvent
::: counterweight.events.InputResponse
::: counterweight.events.InputHandler
::: counterweight.events.Receiver

## Routing Input Events

Each input event has one **target** element.
Counterweight calls the target's `on_input` handler,
then each of its ancestors' in turn, up to the root component's element,
until one returns something other than `None`.
The ancestors are the element tree's, not the screen's,
so an absolutely positioned child bubbles to its parent even where it's drawn outside it.
Each element receives the same event, with its own receiver:
a parent's `rects` are its own, and its `is_target` is `False`.

### Key Presses

The target of a key press is the [focused](../hooks/use_focus.md) element,
or the root component's element when nothing is focused.
A key press bubbles from the focused element through its ancestors, and never reaches its siblings,
so two components that handle the same keys don't both act on one press.
When nothing is focused, only the root component's handler receives key presses,
and its receiver's `is_target` is `True`, though its `is_focused` is `False`.

A focusable component's key handler goes on the element the component returns,
which is the one that's focused.
Handlers on the elements inside it never receive key presses,
and a component deep in the tree can't own a global shortcut:
put the shortcut on the root component's element, which every key press bubbles to
unless a handler on the way stops it.

### Mouse Events

The target of a mouse event is the element drawn on top at the pointer:
the last element in [paint order](../layout/layering.md) whose border box contains it.
An element's margin isn't part of it, so a press in a margin reaches whatever lies beneath.
A pointer over none of the root component's elements,
when the root's element is smaller than the terminal,
targets the root's element, though its rectangles don't contain the pointer.

#### Presses

A **press** runs from a `MouseDown` to its `MouseUp`.
The `MouseDown` is routed like any mouse event,
and the element whose handler stops it **captures** the press:
the press's later events, each `MouseMoved` with a button held and the `MouseUp`,
go to that element alone, as their target, wherever the pointer is,
and stop there whatever its handler returns.
So a drag keeps reaching the element it started on however fast the pointer moves,
and a release outside the element still reaches it,
which a handler can tell from its receiver's rectangles.

The rest of a press that nothing stopped, or whose element has since unmounted, reaches no handler,
so an element never receives the end of a press it didn't see begin:
a release over a button after a press somewhere else doesn't click it.
A handler that wants a press's moves stops its `MouseDown`, even with nothing to do for it:

```python
def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
    match event:
        case MouseDown(button=1):
            return ()
        case MouseMoved(absolute=position, button=1):
            set_end(receiver.relative(position))
            return ()
        case _:
            return None
```

A `MouseMoved` with no button held ends a press whose release the terminal never reported,
such as when focus moves to another window mid-drag, and so does another `MouseDown`.
Both are routed by the pointer's position, and the `MouseDown` starts a new press.
Scroll wheel events aren't part of a press,
so they always target the element under the pointer, even mid-drag.

Since the press goes to whichever element stops its `MouseDown`,
the innermost element with a handler for presses owns the whole press:
a press on a button inside a draggable panel clicks the button and doesn't drag the panel.
[`on_click`](handlers.md) builds a handler for the commonest case.

## Handling Keyboard Events

Each time a key is pressed, Counterweight emits a `KeyPressed` event that holds which key was pressed,
and [routes](#key-presses) it to the focused element.

::: counterweight.events.KeyPressed

## Handling Mouse Events

Each time the state of the mouse changes,
Counterweight emits a _single_ mouse event,
one of `MouseMoved`, `MouseDown`, `MouseUp`, `MouseScrolledDown`, or `MouseScrolledUp`.

::: counterweight.events.MouseEvent

::: counterweight.events.MouseMoved
::: counterweight.events.MouseDown
::: counterweight.events.MouseUp

::: counterweight.events.MouseScrolledDown
::: counterweight.events.MouseScrolledUp

For example, consider the following series of mouse actions and corresponding events:

| Action                                                                           | Event                                                  |
|----------------------------------------------------------------------------------|--------------------------------------------------------|
| Mouse starts at position `(0, 0)`                                                | No event emitted                                       |
| Mouse moves to position `(1, 0)`                                                 | `MouseMoved(position=Position(x=1, y=0), button=None)` |
| Mouse button `1` is pressed                                                      | `MouseDown(position=Position(x=1, y=0), button=1)`     |
| Mouse moves to position `(1, 1)`                                                 | `MouseMoved(position=Position(x=1, y=1), button=1)`    |
| Mouse button `1` is released                                                     | `MouseUp(position=Position(x=1, y=1), button=1)`       |
| Mouse button `3` is pressed                                                      | `MouseDown(position=Position(x=1, y=1), button=3)`     |
| Mouse moves to position `(2, 2)` and mouse button `3` is released simultaneously | `MouseUp(position=Position(x=2, y=2), button=3)`       |

!!! tip "Mouse Button Identifiers"

    Mouse buttons are identified by numbers instead of names (e.g., "left", "middle", "right") because
    the button numbers are the same regardless of whether the mouse is configured for left-handed or right-handed use.

    | Number | Button for Right-Handed Mouse | Button for Left-Handed Mouse |
    |--------|-------------------------------|------------------------------|
    | `1`    | Left                          | Right                        |
    | `2`    | Middle                        | Middle                       |
    | `3`    | Right                         | Left                         |

    You should always use the numbers instead of names to refer to mouse buttons to ensure that your application works
    as expected for both left-handed and right-handed users.

!!! tip "`use_mouse` vs. `on_input`"

    `use_mouse` and an element's `on_input` handler both see the mouse, but `use_mouse` is a hook and `on_input` is an event handler.
    `use_mouse` is more efficient when a component depends only on the *current* state of the mouse
    (e.g., the current position, or whether a button is currently pressed),
    while `on_input` is more convenient when a component needs to respond to *changes* in the mouse state,
    (e.g., a button release [`MouseUp`][counterweight.events.MouseUp]).
    `use_mouse` sees every change, while a handler sees only the events [routed](#routing-input-events) to its element.
