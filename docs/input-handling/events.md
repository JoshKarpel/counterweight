# Events

## Handling Input

`Div` and `Text` elements take an `on_input` handler,
which Counterweight calls with key presses, pastes, and mouse events,
along with a [`Receiver`][counterweight.events.Receiver] describing the element the event is delivered to.
A handler matches on the event, so one case can cover a key and a mouse event alike:

```python
def on_input(event: InputEvent, _: Receiver) -> InputResponse:
    match event:
        case KeyPressed(key=Key.Space) | MouseDown(button=1):
            set_is_open(toggle)
            return ()
        case _:
            return None
```

The [library handlers](handlers.md) cover the common cases,
such as `on_click` for a press released inside the element,
and `scroll_on_wheel` and `scroll_on_keys` for a [scroll container](../layout/scrolling.md).

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
whether the element is focused, the focus handle that names its component if the component is focusable,
and the element and its descendants, for moving focus among them.
The `subtree` also names the element for the [scroll controls](controls.md#scrolling),
and `scroll` says how far the element is scrolled if it's a [scroll container](../layout/scrolling.md),
which [`scroll_on_keys`](handlers.md#scrolling) reads to tell how far a page is and whether it's reached an end.

::: counterweight.events.InputEvent
::: counterweight.events.InputResponse
::: counterweight.events.InputHandler
::: counterweight.events.Receiver

A handler that calls another, as the [autocomplete recipe](../cookbook/autocomplete.md) calls a text field's,
reads what it returned with `response_controls`, which turns any response into a tuple of controls,
or `None` if the inner handler didn't handle the event.

::: counterweight.events.response_controls

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

A **press** runs from the first mouse button going down to the last one coming up,
as in the web's [Pointer Events](https://www.w3.org/TR/pointerevents/).
Its first `MouseDown` is routed like any mouse event,
and the element whose handler stops it **captures** the press:
the press's later events, each `MouseMoved` with a button held
and each `MouseDown` and `MouseUp` of the buttons pressed and released while it lasts,
go to that element alone, as their target, wherever the pointer is,
and stop there whatever its handler returns.
A second button pressed during a press joins it rather than starting a new one,
so a handler that acts on one button matches on `button`, as [`on_click`](handlers.md) does for button `1`.
So a drag keeps reaching the element it started on however fast the pointer moves,
and a release outside the element still reaches it,
which a handler can tell from its receiver's rectangles.

The rest of a press that nothing stopped, or whose element has since unmounted, reaches no handler,
and neither does a `MouseUp` for a button the press doesn't hold,
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
such as when focus moves to another window mid-drag,
and so does a `MouseDown` for a button the press already holds.
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
Enter and Ctrl+J are different keys, `Key.Enter` and `Key.ControlJ`,
so a [text area](../headless/use_text_area.md) can insert a line break on Ctrl+J
while Enter submits a form.

::: counterweight.events.KeyPressed

### Keys pressed with Alt

Terminals send a key pressed with Alt as `ESC` followed by what the key sends on its own
(xterm's `metaSendsEscape`, which most terminals do by default),
and Counterweight reads the two as one key press:
`Key.AltEnter` for Alt+Enter, `Key.AltBackspace` for Alt+Backspace, `Key.ControlAltA` for Ctrl+Alt+A,
and `"alt+b"` for Alt+B, which is `alt+` and the text the key types, so Alt+Shift+B is `"alt+B"`.
Arrow, navigation and function keys pressed with Alt are `Key.AltUp`, `Key.AltPageDown`, `Key.AltF1` and so on,
whether the terminal sends Alt in their escape sequence, as xterm does, or as an `ESC` before it, as rxvt does.

```python
def on_input(event: InputEvent, _: Receiver) -> InputResponse:
    match event:
        case KeyPressed(key=Key.Enter):
            send()
            return ()
        case KeyPressed(key="alt+n"):
            start_new_chat()
            return ()
        case _:
            return None
```

The DOM's `KeyboardEvent` reports Alt in `altKey`, beside a `key` that doesn't change,
as Counterweight's mouse events report it in `is_alt_held`.
A key press names Alt in its key instead, as it names Control and Shift (`Key.ControlLeft`, `Key.ShiftUp`),
so a handler that matches `Key.Enter` doesn't also take Alt+Enter,
and a [text field](../headless/use_text_input.md) never types the `b` of Alt+B,
since text is always one grapheme cluster, and `"alt+b"` isn't.

An Escape pressed on its own and then a key sends the same bytes as Alt with the key,
so Counterweight tells them apart by time, as terminal programs do:
an `ESC` at the end of the input that has arrived waits up to 50 milliseconds for more,
as it waits for the rest of an escape sequence,
and is Alt with the key that arrives in that time, or the Escape key once it passes.
Two `ESC`s are two presses of Escape rather than Alt+Escape, so pressing Escape twice quickly is never lost.
`ESC [` and `ESC O` also begin escape sequences,
so Alt+[ and Alt+Shift+O arrive as `"alt+["` and `"alt+O"` only when no key follows them within that time.

A terminal that doesn't send Alt as an escape never sends these keys.
One that sets the high bit of the byte for Alt instead (xterm with `metaSendsEscape` off and `eightBitInput` on)
sends another character, as does macOS's Option key, which types characters such as `∫` for Option+B
unless the terminal is set to send it as Meta (Terminal.app's "Use Option as Meta key",
or iTerm2's "Esc+" for the Option key).
Run `counterweight check-input` to see which events a terminal's keys arrive as.

### Keys the terminal would act on

A terminal acts on a few Ctrl keys itself unless the program reading it asks otherwise:
Ctrl+C and Ctrl+\\ send signals that interrupt and kill the program, Ctrl+Z one that stops it,
and Ctrl+S and Ctrl+Q pause and resume its output.
Counterweight asks otherwise, as tmux does: it reads the terminal raw,
so every one of those keys arrives as a key press (`Key.ControlC`, `Key.ControlBackslash`, `Key.ControlZ`,
`Key.ControlS` and `Key.ControlQ`), and an editor can save on Ctrl+S,
or an app can pass Ctrl+C on to a program it runs.

A key press that no handler on its path claims then takes its default from `app`'s `unclaimed_keys`,
as a browser takes a key's default action unless a listener prevents it.
[`DEFAULT_UNCLAIMED_KEYS`][counterweight.app.DEFAULT_UNCLAIMED_KEYS] gives Ctrl+C and Ctrl+Z
what they'd do in a terminal:
Ctrl+C quits, and Ctrl+Z suspends the app as a shell job, with
[`Suspend.to_shell()`][counterweight.controls.Suspend.to_shell], until the shell resumes it with `fg`.
A handler that claims one of them keeps it from taking its default,
and `unclaimed_keys` changes the defaults for the whole app:

```python
# No defaults: Ctrl+C and Ctrl+Z do nothing unless a handler handles them.
asyncio.run(app(root(), unclaimed_keys={}))

# Ctrl+Q quits too, as well as Ctrl+C.
asyncio.run(app(root(), unclaimed_keys=DEFAULT_UNCLAIMED_KEYS | {Key.ControlQ: Quit()}))
```

A key the terminal would turn into a signal only does something once the app reads it,
so an app whose render loop is stuck, such as in a handler that never returns, can't be quit with Ctrl+C.
Stop it from outside with `kill`: the first interrupt quits it as Ctrl+C would,
and a second one goes to whatever handled interrupts before the app started.
A focused component that claims every key, such as one that passes keys on to a program,
takes Ctrl+C and Ctrl+Z too, so an app that has one needs another way to quit, such as a key that it doesn't claim.

::: counterweight.app.DEFAULT_UNCLAIMED_KEYS

## Handling Pastes

Counterweight turns on the terminal's bracketed paste mode,
so text pasted into the terminal arrives as one `Pasted` event holding all of it,
rather than as a key press per character,
and it's [routed](#key-presses) to the focused element, as a key press is.
A handler that only matches key presses never sees it,
so a paste can't trigger a binding by holding the binding's key.
[`use_text_input`](../headless/use_text_input.md) and [`use_text_area`](../headless/use_text_area.md)
insert it in one edit.
Terminals without bracketed paste send pasted text as typed keys,
with its line breaks as Enter, or as Ctrl+J from a terminal that sends them as line feeds.

::: counterweight.events.Pasted

## Handling Mouse Events

Each time the state of the mouse changes,
Counterweight emits a _single_ mouse event,
one of `MouseMoved`, `MouseDown`, `MouseUp`,
`MouseScrolledDown`, `MouseScrolledUp`, `MouseScrolledLeft`, or `MouseScrolledRight`.

::: counterweight.events.MouseEvent

::: counterweight.events.MouseMoved
::: counterweight.events.MouseDown
::: counterweight.events.MouseUp

::: counterweight.events.MouseScrolledDown
::: counterweight.events.MouseScrolledUp
::: counterweight.events.MouseScrolledLeft
::: counterweight.events.MouseScrolledRight

Each mouse event says which modifier keys were held, as the DOM's `MouseEvent` does,
in `is_shift_held`, `is_alt_held` and `is_control_held`,
so a handler can match a modified press or turn of the wheel:

```python
def on_input(event: InputEvent, _: Receiver) -> InputResponse:
    match event:
        case MouseDown(button=1, is_control_held=True):
            set_selected(lambda selected: selected ^ {item})
            return ()
        case MouseDown(button=1):
            set_selected({item})
            return ()
        case _:
            return None
```

Terminals keep some combinations for themselves and never report them to the app:
most select text for Shift with a press, even while the app tracks the mouse,
and some scroll their own scrollback for Shift with the wheel or open links for Control with a press.
So a modifier works best as a shortcut for something the app offers another way too.
`counterweight check-input --mouse` shows the events a terminal reports.

For example, consider the following series of mouse actions and corresponding events:

| Action                                                                           | Event                                                  |
|----------------------------------------------------------------------------------|--------------------------------------------------------|
| Mouse starts at position `(0, 0)`                                                | No event emitted                                       |
| Mouse moves to position `(1, 0)`                                                 | `MouseMoved(absolute=Position(x=1, y=0), button=None)` |
| Mouse button `1` is pressed                                                      | `MouseDown(absolute=Position(x=1, y=0), button=1)`     |
| Mouse moves to position `(1, 1)`                                                 | `MouseMoved(absolute=Position(x=1, y=1), button=1)`    |
| Mouse button `1` is released                                                     | `MouseUp(absolute=Position(x=1, y=1), button=1)`       |
| Mouse button `3` is pressed                                                      | `MouseDown(absolute=Position(x=1, y=1), button=3)`     |
| Mouse moves to position `(2, 2)` and mouse button `3` is released simultaneously | `MouseUp(absolute=Position(x=2, y=2), button=3)`       |

!!! tip "Mouse Button Identifiers"

    Mouse buttons are identified by numbers instead of names (e.g., "left", "middle", "right") because
    the button numbers are the same regardless of whether the mouse is configured for left-handed or right-handed use.

    | Number | Button for Right-Handed Mouse | Button for Left-Handed Mouse |
    |--------|-------------------------------|------------------------------|
    | `1`    | Left                          | Right                        |
    | `2`    | Middle                        | Middle                       |
    | `3`    | Right                         | Left                         |
    | `8`    | Back                          | Back                         |
    | `9`    | Forward                       | Forward                      |

    You should always use the numbers instead of names to refer to mouse buttons to ensure that your application works
    as expected for both left-handed and right-handed users.

!!! tip "`use_mouse` vs. `on_input`"

    `use_mouse` and an element's `on_input` handler both see the mouse, but `use_mouse` is a hook and `on_input` is an event handler.
    `use_mouse` is more efficient when a component depends only on the *current* state of the mouse
    (e.g., the current position, or whether a button is currently pressed),
    while `on_input` is more convenient when a component needs to respond to *changes* in the mouse state,
    (e.g., a button release [`MouseUp`][counterweight.events.MouseUp]).
    `use_mouse` sees every change, while a handler sees only the events [routed](#routing-input-events) to its element.
