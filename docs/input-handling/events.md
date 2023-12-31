# Events

## API

::: counterweight.events.AnyEvent

::: counterweight.events.KeyPressed
::: counterweight.events.MouseMoved
::: counterweight.events.MouseDown
::: counterweight.events.MouseUp

## Mouse Event Semantics

Each time the state of the mouse changes, Counterweight emits a _single_ mouse event,
one of `MouseMoved`, `MouseDown`, or `MouseUp`.

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
