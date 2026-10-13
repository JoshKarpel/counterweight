# Handlers

`counterweight.handlers` holds handlers for common behaviors,
and combinators that compose several handlers into the one an element's `on_input` takes.
Nothing happens to an input event unless a handler on its path does it,
so a behavior an element should have is a handler composed onto it.

```python
from counterweight.handlers import each, first, on_click

# A button that sends a message when clicked.
Text(content="Send", on_input=on_click(send))

# A row that both selects itself when clicked and handles its own keys.
Div(children=..., on_input=first(row_keys, on_click(select)))
```

Each library handler is a pure function of the event and the receiver,
so it can be tested by calling it, without running an app.

## Composing Handlers

`first` tries handlers in order and stops at the first that handles the event,
so the order states their precedence.
In `first(on_click(open_menu), drag_panel)`, `drag_panel` never sees a button `1` press, which `on_click` handles.
`each` runs every handler and combines their controls,
which is how two handlers that both act on a `MouseDown` share one element:
only the element that stops a press's `MouseDown` [receives the rest of it](events.md#presses),
so they can't sit on an element and its parent.

::: counterweight.handlers.first
::: counterweight.handlers.each

## Clicks

::: counterweight.handlers.on_click
