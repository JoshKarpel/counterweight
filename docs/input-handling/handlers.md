# Handlers

`counterweight.handlers` holds handlers for common behaviors,
and combinators that compose several handlers into the one an element's `on_input` takes.
Nothing happens to an input event unless a handler on its path does it,
so a behavior an element should have is a handler composed onto it.

```python
from counterweight.handlers import each, first, on_click

# A button that sends a message when clicked.
Text(content="Send", on_input=on_click(send))

# A row that selects itself when clicked, and handles keys while focused
# (it's the top-level element of a component that calls use_focus).
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
only the element that stops a press's first `MouseDown` [receives the rest of it](events.md#presses),
so they can't sit on an element and its parent.

::: counterweight.handlers.first
::: counterweight.handlers.each

## Clicks

::: counterweight.handlers.on_click

## Focus

Nothing moves [focus](../hooks/use_focus.md) unless a handler returns a control that does,
so Tab navigation and click-to-focus are handlers an app composes in:

```python
from counterweight.handlers import clear_focus, each, first, focus_receiver_on_press, on_click, tab_focus

# The root: Tab navigation, after the app's own shortcuts,
# and a blur for presses that nothing below the root claims.
Div(children=..., on_input=first(app_shortcuts, tab_focus, clear_focus))

# A focusable button. Both handlers claim the press, so each runs both.
focus = use_focus()
Text(content="Send", style=ring if focus.is_focused else plain, on_input=each(on_click(send), focus_receiver_on_press))

# A button that isn't focusable, and blurs whatever is when it's clicked.
Text(content="Clear", on_input=each(on_click(clear), clear_focus))
```

`tab_focus` moves within the element it's attached to,
so on the root component's element it moves through the whole tree,
and on a dialog's element it keeps Tab inside the dialog.
A focused component that wants Tab for itself, to indent in a text area,
handles it and returns `()`, so it never bubbles to `tab_focus`.

Every handler here that acts on a press claims its `MouseDown`,
so of nested elements with press handlers, the innermost takes the press:
with `focus_receiver_on_press` on nested focusable components, a press focuses the innermost one under the pointer.
A press on a non-focusable element that claims presses, such as a button made with `on_click`,
leaves focus where it was, unless the element composes `clear_focus` in too.

::: counterweight.handlers.tab_focus
::: counterweight.handlers.focus_receiver_on_press
::: counterweight.handlers.focus_on_press
::: counterweight.handlers.clear_focus

## Scrolling

Nothing scrolls a [scroll container](../layout/scrolling.md) unless a handler returns a control that does,
so a container the wheel scrolls composes `scroll_on_wheel` in:

```python
from counterweight.handlers import scroll_on_wheel

Div(style=fill(1) | col | overflow_y_scroll, on_input=scroll_on_wheel(), children=...)
```

::: counterweight.handlers.scroll_on_wheel
