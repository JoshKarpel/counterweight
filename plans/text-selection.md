# Plan: Selecting Text and Copying It over OSC 52

Artifact: https://claude.ai/code/artifact/bda67778-ca67-48db-85b3-eb6a579a50f1

This plan implements [#399](https://github.com/JoshKarpel/counterweight/issues/399):
dragging across text in an app selects it, draws it highlighted, and copies it to the clipboard
with OSC 52 when the button comes up.
Selection is a library handler, `select_text`, that an element composes into its `on_input`,
driving a selection the render loop holds through new controls.
It doesn't cover selecting text inside `use_text_input` or `use_text_area` (an editing selection the hooks own),
keyboard selection, or selections anchored to text rather than cells (see [Deferred](#deferred)).

It ships in two parts.
The first, `CopyToClipboard`, copies any text an app gives it,
and stands on its own for an app's "copy" buttons and key bindings:
it's [step 1](#steps), and it's done.
The rest, selecting text and copying the selection, is deferred to a later change (steps 2 to 5).

## The question

How does an app let a user drag across its text and copy it,
when the app has taken the mouse away from the terminal,
counterweight has no default actions for a press to fall back on,
and a terminal's own selection is a rectangle of cells that picks up borders and neighbouring panes?

## How the web does it

- **One selection per document.**
  [`Selection`](https://developer.mozilla.org/en-US/docs/Web/API/Selection) has an anchor, where it started,
  and a focus, where it ends now, which may come before the anchor.
  [`collapse`](https://developer.mozilla.org/en-US/docs/Web/API/Selection/collapse) starts one at a point,
  [`extend`](https://developer.mozilla.org/en-US/docs/Web/API/Selection/extend) moves its focus,
  and [`removeAllRanges`](https://developer.mozilla.org/en-US/docs/Web/API/Selection/removeAllRanges) clears it.
- **Which presses start one.** Starting a selection is the default action of `mousedown`,
  which [`user-select`](https://developer.mozilla.org/en-US/docs/Web/CSS/user-select) turns off with `none`.
  Its `contain` value, which only legacy Edge and IE shipped,
  keeps a selection that starts inside an element within that element's bounds.
- **How it's drawn.** The [`::selection`](https://developer.mozilla.org/en-US/docs/Web/CSS/::selection) pseudo-element
  sets the color and background of selected text, defaulting to the system's highlight colors.
  Only the text is highlighted, not the boxes around it.
- **What it holds.** A selection is a range of the DOM, in document order,
  so it follows the text however it's laid out, includes text scrolled out of view,
  and serializes block boundaries as line breaks and soft wraps as nothing.
- **How it's copied.** A browser copies on Ctrl+C, or a page calls
  [`navigator.clipboard.writeText`](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText).
  X11 sets the PRIMARY selection as soon as text is selected, and xterm and most terminals copy on release:
  the precedent for copying with no key binding.

Where counterweight differs, and what that changes:

- **No default actions.** Starting a selection is a handler, `select_text`, rather than a default `user-select` turns off.
  An element that shouldn't start one doesn't have `select_text` on its path,
  so there's no `select-none` utility and routing needs no prevent-default.
- **Handlers hold no state.** A handler is a pure function of the event and its receiver,
  so it can't remember where a drag started.
  The render loop holds the selection, and `select_text` drives it with controls named after `collapse` and `extend`.
- **Cells, not DOM offsets.** A selection is a range of screen cells in reading order, as a terminal's is,
  contained to the element whose `select_text` started it, as `user-select: contain` contains it,
  and holding only the cells that element's text paints.
  That keeps neighbouring panes, borders and padding out without the DOM's ranges.
  It also means a soft-wrapped line copies as several lines, and only the part of a selection on screen is copied.
- **No clipboard API.** The app asks the terminal to set the clipboard with OSC 52,
  which works only where the terminal supports it.

## Design

### The handler

`select_text(style=SELECTION_STYLE)` builds the handler, as `scroll_on_wheel(lines)` does,
so the highlight can be set per element, as `::selection` is:

| Event | Response |
| --- | --- |
| `MouseDown(button=1)` | `StartSelection(within=receiver.subtree, at=event.absolute, style=style)` |
| `MouseMoved(button=1)` | `ExtendSelection(to=event.absolute)` |
| `MouseUp(button=1)` | `(ExtendSelection(to=event.absolute), CopySelection())` |
| anything else | `None` |

Claiming the `MouseDown` captures the press, so the drag and the release reach `select_text` wherever the pointer goes.
The guideline in the docs is to put it on the narrowest element it applies to (each message, not the whole transcript),
so a press on a button or a draggable element never reaches it,
and the selection is contained to that message.

`clear_selection` is a handler that claims a `MouseDown` and returns `ClearSelection()`,
for the root to clear a selection on a press nothing below it claims, as `clear_focus` blurs.

### The controls

All in `counterweight.controls`, added to `AnyControl`:

- `StartSelection(within: ElementHandle | Subtree, at: Position, style: CellStyle = SELECTION_STYLE)`:
  replaces any selection with a collapsed one at `at`, an absolute position on the screen as last drawn,
  contained to the element `within` names, highlighted with `style`.
  It does nothing if `within` names no mounted, visible element.
  `style` must be solid, since a highlight has no box to map a gradient over; `StartSelection` raises `ValueError` otherwise.
- `ExtendSelection(to: Position)`: moves the selection's focus to `to`. It does nothing without a selection.
- `ClearSelection()`: clears the selection.
- `CopySelection()`: copies the selected text to the clipboard at the start of the next render cycle,
  as `Bell` rings, and does nothing if the selection is empty.
- `CopyToClipboard(text: str)`: copies `text`, as `navigator.clipboard.writeText` does,
  for an app's own "copy" buttons. It's what `CopySelection` does with the selected text.
  Copying `""` empties the clipboard, as `writeText("")` does.

`SELECTION_STYLE`, the default highlight, is `(text_color("slate", 50) | text_bg("blue", 700)).text_style`,
explicit on both colors so it reads on any theme.

### The selection the render loop holds

```python
@dataclass(frozen=True, slots=True)
class Selection:
    key: NodeKey  # the element the selection is contained to
    anchor: Position  # where it started, and
    focus: Position  # where it ends, both relative to the element's scrolled content
    style: CellStyle
```

Positions are relative to the element's content box, moved by its own scroll offset,
so the selection moves with the element when it, or a container above it, scrolls,
and stays on the same cells of the element when its content changes.
The loop converts the controls' absolute positions with the layouts of the frame on screen,
which is what the user pointed at.

A selection changes nothing in the shadow tree, so changing one renders without re-running any component, as a scroll does.
It's dropped when its element unmounts, and kept, drawing nothing, while its element is hidden or scrolled out of view.
A press with no movement leaves a collapsed selection, which selects nothing, so a click clears a selection
on any element with `select_text`.

### Which cells are selected

Each frame, the selection becomes a `SelectedCells` value (in a new `counterweight.selection` module):
the anchor and focus on the screen, ordered so the start comes first in reading order,
each moved onto the element's visible region if the pointer went outside it,
and the keys of the `Text` and `Canvas` elements in its subtree.

A selection covers from its start to its end, inclusive, row by row:
from the start's column to the region's right edge on the first row,
the region's full width on the rows between, and from the region's left edge to the end's column on the last.
A collapsed selection covers nothing.
Of those cells, the selected ones are the ones the subtree's `Text` and `Canvas` elements paint text into:
a `Text`'s wrapped rows, including the spaces its justification adds, and a `Canvas`'s painter's rows.
Borders, padding and backgrounds are never selected.
A cell inside a two-cell-wide cluster selects the whole cluster.

### Drawing the highlight

`paint_layout` takes the frame's `SelectedCells`, or `None`.
`paint_element` merges the highlight over the selected cells of each row it paints for a selected element,
in both its solid and gradient paths, before writing the row.
Highlighting the rows as they're painted, rather than recoloring the finished paint,
leaves borders and padding alone, and lets an element painted later, such as a popup over the transcript, cover the highlight.
The highlight is part of the paint, so screenshots and recordings show it.

Without a selection, the only added cost is checking `selected is None` per text element.

### What's copied

`selected_text(selected, layouts)` builds the text from the selected elements' rows, not from the paint,
so a popup painted over the selection isn't copied:

- each selected grapheme is placed at its column, and the gaps between a row's text are spaces,
  so text side by side in the element copies as it looks;
- the columns left of the selection's leftmost text are dropped, keeping relative indentation,
  except on the first row, which starts at the selection's start;
- each row's trailing whitespace is dropped, as terminals drop it, and rows are joined with `\n`;
- blank rows before the first row with text and after the last are dropped.

### Writing to the clipboard

`clipboard_instructions(text)` in `counterweight.output` is OSC 52 with the `c` (clipboard) target:
`ESC ] 52 ; c ; <base64 of the UTF-8 text> ESC \`.
Base64 can't hold a control character, so no text can end the sequence early.
The loop writes it at the start of the next render cycle, like `Bell`, and the last copy in a cycle wins.
A headless app writes nothing, and a recording doesn't record it:
it isn't screen output, and replaying it in a terminal would set the viewer's clipboard.

`CopyToClipboard`'s docstring says where OSC 52 works:
tmux passes it on only with `set -g set-clipboard on`
(its default, `external`, ignores applications' attempts),
and a terminal may turn it off or ask before letting a program set the clipboard.

## Steps

1. **Copying (done).** `clipboard_instructions`, `CopyToClipboard`, and the loop writing it at the start of a cycle,
   with the OSC 52 and tmux notes in its docstring, in `controls.md`, and a changelog entry.
   Tests: the encoding (non-ASCII text, control characters, empty text),
   a terminal test that the last copy in a cycle is written once per cycle,
   one that a headless app writes nothing, and one that a recording leaves the copy out.
   Exercised end to end in tmux with `set-clipboard on`: `tmux show-buffer` held the copied text.

Steps 2 to 5 are deferred to a later change.

2. **The selection core.** `counterweight.selection`: `Selection`, `SelectedCells` and `selected_text`, all pure.
   Tests: ordering anchor and focus both ways, clamping a focus outside the region on each side,
   a collapsed selection, the rows of a range, wide clusters at either end,
   gaps, indentation and trailing whitespace in the copied text, and a `Canvas`'s rows.
3. **The highlight.** `paint_layout` and `paint_element` take `SelectedCells`.
   Tests: the solid and gradient paths, a `Canvas`, a border and padding left alone,
   an element painted later covering the highlight, and a cluster split by the range's edge.
   Run `just profile` on a text-heavy workload before and after, to confirm the no-selection path costs nothing measurable.
4. **The controls and the handlers.** `StartSelection`, `ExtendSelection`, `ClearSelection`, `CopySelection`,
   the loop holding the selection, and `select_text` and `clear_selection` in `counterweight.handlers`.
   Tests: each handler's responses, and apps under an autopilot that drag across bordered text and screenshot it,
   scroll a selection, unmount its element, clear it with a click and with `ClearSelection`,
   and copy on release (a terminal test that reads the OSC 52 sequence).
5. **Docs.** A "Selecting text" section in `docs/input-handling/handlers.md`, a "Selection" section in `controls.md`,
   a `docs/examples/selecting_text.py` example with a screenshot of a selection across bordered messages
   and a cast of the drag, a pointer to `CopyToClipboard`'s OSC 52 and tmux notes, and a changelog entry.
   Exercise it end to end in tmux with `set-clipboard on`, checking `tmux show-buffer` after a drag.

## Deferred

- **Selections anchored to text.** A DOM-like range of (element, grapheme offset) would follow streaming content
  and copy text scrolled out of view, but there are several plausible designs
  (offsets into a `Text`'s content, into its chunks, or into its wrapped rows)
  and no way yet to choose between them.
- **Copying a soft-wrapped line as one line.** Layout knows which row breaks are wraps, but paint doesn't carry it.
  Cheap once a selection holds text rather than cells.
- **Double and triple clicks** to select a word or a line need click counting, and input events carry no time.
- **Shift+press to extend a selection.** The receiver doesn't say whether a selection exists,
  so the handler can't choose between extending one and starting one.
- **Scrolling a container while dragging past its edge**, as browsers do.
- **Keyboard selection**, and selecting inside the text editing hooks.
