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
Code outside a handler, such as an effect, sends controls with [`use_controls`](../hooks/use_controls.md).

## API

::: counterweight.controls.AnyControl

::: counterweight.controls.Quit
::: counterweight.controls.Bell
::: counterweight.controls.SetTitle
::: counterweight.controls.RestoreTitle
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

### Scrolling

These controls scroll a [scroll container](../layout/scrolling.md).
[`scroll_on_wheel`](handlers.md#scrolling) returns `ScrollBy` for the wheel,
and [`scroll_on_keys`](handlers.md#scrolling) returns `ScrollBy` for the keys that scroll by a step or a page,
and `ScrollTo` for Home and End.
`ScrollIntoView` brings an element into view in every container above it:
moving focus applies it to the newly focused element,
[`use_text_area`'s handler](../headless/use_text_area.md#keeping-the-cursor-in-view) returns it for the cursor's row,
and the [autocomplete recipe](../cookbook/autocomplete.md#a-long-list) returns it for the highlighted match.

::: counterweight.controls.ScrollTo
::: counterweight.controls.ScrollBy
::: counterweight.controls.ScrollIntoView
