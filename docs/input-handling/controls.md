# Controls

**Controls** are objects that can be returned from an element's `on_input` handler
to instruct Counterweight to take some action during the render loop,
such as gracefully quitting the application or playing the
[terminal "bell" sound](https://en.wikipedia.org/wiki/Bell_character).

A handler returns one control (`return Quit()`),
or a tuple of controls, which Counterweight applies in order (`return Bell(), Screenshot.to_file(path)`),
skipping any `None` in it, as `merge` skips `None` styles.
Returning `()`, a tuple of no controls, says the handler handled the event with nothing more to do,
and returning any control or tuple stops the event, as `()` does (see [Events](events.md#handling-input)).

## API

::: counterweight.controls.AnyControl

::: counterweight.controls.Quit
::: counterweight.controls.Bell
::: counterweight.controls.Screenshot
::: counterweight.output.Frame
::: counterweight.controls.Suspend
::: counterweight.controls.ToggleBorderHealing
::: counterweight.controls.AdvanceClock

### Focus

These controls move [focus](../hooks/use_focus.md),
which decides the element that key presses go to.
The [focus handlers](handlers.md#focus) return them for Tab and for presses.

::: counterweight.controls.FocusNext
::: counterweight.controls.FocusPrevious
::: counterweight.controls.FocusOn
::: counterweight.controls.ClearFocus
