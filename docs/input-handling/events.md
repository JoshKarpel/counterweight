# Events

## Handling Input

`Div` and `Text` elements take an `on_input` handler,
which Counterweight calls with key presses and mouse events,
along with a [`Receiver`][counterweight.events.Receiver] describing the element the event is delivered to.
A handler matches on the event, so one case can cover a key and a mouse event alike:

```python
def on_input(event: InputEvent, _: Receiver) -> None:
    match event:
        case KeyPressed(key=Key.Down) | MouseScrolledDown():
            set_offset(lambda o: o + 1)
        case KeyPressed(key=Key.Up) | MouseScrolledUp():
            set_offset(lambda o: o - 1)
        case _:
            pass
```

A handler returns a [control](controls.md), such as `Quit()`, for Counterweight to apply, or `None`.

A handler that only cares about keys still receives mouse events,
including every movement of the pointer over its element.
One that matches many keys can return early on anything else, which keeps its cases about keys alone:

```python
def on_input(event: InputEvent, _: Receiver) -> AnyControl | None:
    if not isinstance(event, KeyPressed):
        return None

    match event.key:
        case Key.ControlC:
            return Quit()
        case Key.Tab:
            set_tab(lambda t: (t + 1) % len(TABS))
        case _:
            pass

    return None
```

The receiver carries the element's rectangles,
so a handler can tell where in the element a mouse event landed:

```python
def on_input(event: InputEvent, receiver: Receiver) -> None:
    match event:
        case MouseUp(absolute=position, button=1):
            set_clicked(receiver.relative(position))
        case _:
            pass
```

::: counterweight.events.InputEvent
::: counterweight.events.InputHandler
::: counterweight.events.Receiver

## Handling Keyboard Events

Each time a key is pressed,
Counterweight calls the `on_input` handler
of every element with a `KeyPressed` event that holds
information about which key was pressed.

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

Counterweight calls the
`on_input` handler of each element whose border rectangle
contains the new mouse position or the previous mouse position
with the relevant mouse event object.

!!! tip "`use_mouse` vs. `on_input`"

    `use_mouse` and an element's `on_input` handler both see the mouse, but `use_mouse` is a hook and `on_input` is an event handler.
    `use_mouse` is more efficient when a component depends only on the *current* state of the mouse
    (e.g., the current position, or whether a button is currently pressed),
    while `on_input` is more convenient when a component needs to respond to *changes* in the mouse state,
    (e.g., a button release [`MouseUp`][counterweight.events.MouseUp]).
