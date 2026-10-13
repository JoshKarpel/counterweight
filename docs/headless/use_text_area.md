# `use_text_area`

`use_text_area` edits text that wraps onto rows:
it handles typing, deleting, moving the cursor along a row and between rows, and pasting,
and leaves drawing to the component that calls it.
It wraps the value itself, at the width the component gives it,
so the cursor moves between the rows the value is drawn on.
For a ready-made box, use [`text_area`](#a-styled-text-area), which is built on this hook.

This page covers the hook and that component.
Selection isn't supported yet.

## Using the hook

As with [`use_text_input`](use_text_input.md), the calling component owns the value and passes it with its setter,
and the hook owns the cursor and makes the component [focusable](../hooks/use_focus.md).
It also takes the `width` to wrap at,
which here is the content width that [`use_rects`](../hooks/use_rects.md) reports for the box.
The box gets its width from its parent, not from its text,
since the text is wrapped to fit it.
The hook returns the rows, joined by line breaks, split around the cursor,
so the component draws them with `text_wrap_none`, without wrapping them again:

```python
--8<-- "text_area.py:hook"
```

Enter isn't an edit, so it [bubbles](../input-handling/events.md#routing-input-events),
and here the composer takes it to send the draft.
Ctrl+J inserts a line break:

![A chat composer holding a draft that wraps onto a second row, then a second line](../assets/text-area-chat-draft.svg)

Enter sends it, keeping its line break:

![The sent message above an empty composer](../assets/text-area-chat-sent.svg)

The conversation holds the messages and the draft together,
so `send` reads the latest draft from the conversation it updates,
rather than the draft this render saw, which misses keys typed since.

The messages are in a [scroll container](../layout/scrolling.md) that fills the space above the composer,
with [`stick_to_end_y`](../layout/scrolling.md#following-the-end), so it stays scrolled to the newest message,
and `justify_children_end`, so the first few messages sit just above the composer, as chats show them.
Older messages scroll up out of view, and the wheel scrolls back to them:

![Three sent messages, the first scrolled partly out of view](../assets/text-area-chat-scrolled.svg)

## Line breaks

Pass `enter_inserts_newline=True` for Enter to insert a line break, as in a text editor,
rather than bubble, as for a form or a chat that submits on Enter.
Ctrl+J inserts one either way.
Shift+Enter can't stand in for it: most terminals send Shift+Enter as plain Enter.

A paste keeps its line breaks, however they're written, and turns each tab into a space.

## How the text wraps

A row breaks after the last whitespace that fits, or wherever it fills when a word is wider than a row.
Rows are filled one at a time, as text editors fill them,
rather than evened out as [`text_wrap_pretty`](../styles/text-wrapping.md) evens out a paragraph,
so an edit rewraps its line only from the row above the cursor onward.
The whitespace at a break stays at the end of its row, taking its cells,
and a cell is kept after the end of each line,
so wherever the cursor is, there's a cell to draw it in:
a line that exactly fills its rows puts the cursor at its end on a row of its own.

## Keeping the cursor in view

A text area in a scroll container, such as one with a `max_height`, has to scroll as the cursor moves past its edge.
The hook returns a `cursor_row` [`ElementHandle`][counterweight.focus.ElementHandle]
for the element the component draws the cursor's row in,
and its handler returns [`ScrollIntoView`](../layout/scrolling.md#scrolling-an-element-into-view)
for that handle, with `block="nearest"`, for each key press and paste it handles.
That applies to the layout of the render the edit causes,
so the container scrolls in the same frame the cursor moves, and only as far as it takes,
as a browser's `<textarea>` scrolls to its caret.

To use it, draw the cursor's row as an element of its own and give it the handle.
`before_cursor` and `after_cursor` separate rows with line breaks,
so the rows above the cursor's are everything in `before_cursor` up to its last line break,
and the rows below are everything in `after_cursor` after its first.
The [styled text area](#a-styled-text-area) draws those as a `Text` each, around the cursor's row.
A component that draws all the rows in one element can leave out the handle,
and `ScrollIntoView` then scrolls nothing.

## Keys

The keys are [`use_text_input`'s](use_text_input.md#keys), with these acting on rows:

| Key            | Edit                                                                  |
|----------------|-----------------------------------------------------------------------|
| Up, Ctrl+P     | Move to the row above, at the same column, or to the start from the first row |
| Down, Ctrl+N   | Move to the row below, at the same column, or to the end from the last row    |
| Home           | Move to the start of the row                                          |
| Ctrl+A         | Move to the start of the row, or to the start from the start of a row |
| End            | Move to the end of the row                                            |
| Ctrl+E         | Move to the end of the row, or to the end from the end of a row       |
| Ctrl+U         | Delete to the start of the row                                        |
| Ctrl+K         | Delete to the end of the row                                          |
| Ctrl+J         | Insert a line break                                                   |
| Enter          | Insert a line break, with `enter_inserts_newline=True`                |

Up and Down keep aiming for the column they started from,
so the cursor comes back to it after passing through a shorter row.
The end of a row that wraps is the start of the next,
so End on one moves to its last character, usually the whitespace it wrapped at.
Left, Right, Backspace and Delete step over a line break as one character,
and the word keys treat it as whitespace.
Ctrl+T swaps characters within a line, so it does nothing at the start of one.

## Validating and transforming

The setter works as it does for [`use_text_input`](use_text_input.md#validating-and-transforming):
it's called with a function from the latest value to the edited one,
and wrapping it validates or transforms each edit.
The cursor stays where it is when the setter rejects an edit,
and moves to the end of the value when the value changes other than by an edit.

## A styled text area

[`text_area`][counterweight.widgets.text_area] draws a bordered box around the rows,
wrapped at the width of its box,
with the cursor highlighted while it's focused,
and takes focus when it's pressed.
It takes the hook's parameters, other than `width`, a `placeholder` to show in an empty box,
and a `style` merged over its own.
It's as wide as its parent or its `style` makes it, and grows to fit its rows,
up to a `max_height` in its `style`:

```python
--8<-- "text_area.py:widget"
```

![An empty notes box showing its placeholder](../assets/text-area-notes.svg)

![The notes box holding three lines](../assets/text-area-notes-filled.svg)

Past its `max_height` it scrolls, [keeping the cursor in view](#keeping-the-cursor-in-view),
and the wheel scrolls it too:

![The notes box scrolled to its last four of six lines, with the cursor on the last](../assets/text-area-notes-scrolled.svg)

## API

::: counterweight.headless.use_text_area
::: counterweight.headless.TextArea
::: counterweight.widgets.text_area
