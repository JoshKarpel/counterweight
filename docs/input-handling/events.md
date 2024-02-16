# Events

## Handling Keyboard Events

Each time a key is pressed,
Counterweight calls the `on_key` event handler
of every element with a `KeyPressed` event that holds
information about which key was pressed.

::: counterweight.events.KeyPressed


## Handling Mouse Events

Each time the state of the mouse changes,
Counterweight emits a _single_ mouse event,
one of `MouseMoved`, `MouseDown`, or `MouseUp`.

::: counterweight.events.MouseEvent

::: counterweight.events.MouseMoved
::: counterweight.events.MouseDown
::: counterweight.events.MouseUp

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
`on_mouse` event handler of each element whose border rectangle
contains the new mouse position or the previous mouse position
with the relevant mouse event object.

!!! tip "`use_mouse` vs. `on_mouse`"

    `use_mouse` and `on_mouse` provide similar functionality, but `use_mouse` is a hook and `on_mouse` is an event handler.
    `use_mouse` is more efficient when a component depends only on the *current* state of the mouse
    (e.g., the current position, or whether a button is currently pressed),
    while `on_mouse` is more convenient when a component needs to respond to *changes* in the mouse state,
    (e.g., a button release ([`MouseUp`][counterweight.events.MouseUp]).
