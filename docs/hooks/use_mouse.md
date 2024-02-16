# `use_mouse`

## API

::: counterweight.hooks.Mouse
::: counterweight.hooks.use_mouse

!!! tip "`use_mouse` vs. `on_mouse`"

    `use_mouse` and `on_mouse` provide similar functionality, but `use_mouse` is a hook and `on_mouse` is an event handler.
    `use_mouse` is more efficient when a component depends only on the *current* state of the mouse
    (e.g., the current position, or whether a button is currently pressed),
    while `on_mouse` is more convenient when a component needs to respond to *changes* in the mouse state,
    (e.g., a button release ([`MouseUp`][counterweight.events.MouseUp]).
