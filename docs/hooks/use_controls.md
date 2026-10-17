# `use_controls`

An input handler acts on the app by returning [controls](../input-handling/controls.md),
but an effect, or a callback that a program or a timer calls, has no event to return them for.
`use_controls` gives a component a sender that hands the app a control from anywhere:

```python
from asyncio import sleep

from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Text
from counterweight.hooks import use_controls, use_effect


@component
def farewell() -> Text:
    send_control = use_controls()

    async def quit_soon() -> None:
        await sleep(3)
        send_control(Quit())

    use_effect(quit_soon, deps=())

    return Text(content="Quitting in three seconds...")
```

The [multiplexer](https://github.com/JoshKarpel/counterweight/blob/main/examples/multiplexer.py) example
quits the same way when its last pane's shell exits,
and moves focus with `FocusNext` when the focused pane's shell exits.

The app handles a sent control as it handles one a handler returns, after the events already waiting,
so state set just before sending it changes the same frame the control does.
Every render returns an equal sender, so it can be left out of an effect's `deps`.

## API

::: counterweight.hooks.use_controls
::: counterweight.hooks.ControlSender
