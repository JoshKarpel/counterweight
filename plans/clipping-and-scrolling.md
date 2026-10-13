# Plan: Clipping and Scrolling

This plan covers clipping painting to containers with hidden overflow (#388),
the hit testing that has to agree with it,
a way for a popup such as an autocomplete list to escape the clip,
and scroll containers (#389), with their input, keyboard scrolling (part of #390),
and scroll anchoring, driven by the `agent` benchmark's transcript.
They share one mechanism: a walk down the tree after layout that places each node on the screen,
carrying a scroll offset and a clip.
It also settles how border healing treats a clip edge, which touches #74.
It doesn't cover a top layer for modals (see [Open questions](#open-questions)),
or a visible scrollbar (see [No scrollbar](#no-scrollbar)).

## Problems

- **Overflow lays out clipped but paints unclipped.**
  `paint_layout` (`paint.py:189`) paints every element into the full-screen `Paint`,
  so a container with `overflow: hidden` lets its children paint over its border
  and over whatever lies beyond it (the example in #388).
  The constraint utilities (`length`, `percentage`, `ratio`, `fill`) set hidden overflow on every item
  (`_constraint` in `styles/utilities.py`), so any constrained child with too much content hits this.
- **Hit testing ignores clipping.**
  `RoutingTable.target_at` (`routing.py:134`) takes the topmost element whose border box contains the mouse,
  and `use_hovered` (`hooks.py:199`) tests the mouse against the whole box,
  so once clipping lands, an element would receive clicks and hover in cells it doesn't paint.
- **A popup can't escape a clipping ancestor.**
  On the web, an absolutely positioned box is placed against its nearest positioned ancestor,
  so a dropdown escapes a clip by being positioned against an ancestor outside it.
  Here an absolutely positioned box is always placed against its parent,
  so every clipping ancestor clips it, whatever its `z`,
  and an autocomplete list inside a scroll container would be cut off at the container's edge.
- **Nothing scrolls.**
  Apps keep an offset in `use_state` and render a slice of their data,
  which works for lists of equal-height rows and nothing else (wrapped text, mixed heights, wide tables).
  The `agent` benchmark (`benchmarks/agent.py`) shows the cost:
  its transcript can only show the newest messages,
  so `visible` drops older ones by estimating each message's wrapped height from its line lengths,
  and there's no way to read back.
- **There are no overflow utilities.**
  The only way to set overflow is a raw `waxy.Style`.

## What the probes established

Run against the pinned `waxy`, with a 20×6 container with a border of 1, horizontal padding of 3,
vertical padding of 1, `overflow_y=Scroll`, `scrollbar_width=2`, and ten one-row children:

```text
content_box x/y/w/h 4.0 2.0 12.0 2.0
child 0 Point(x=4, y=2) Size(width=10, height=1)
scroll w/h 0.0 8.0
scrollable_overflow_rect Rect(left=0, right=16, top=0, bottom=12)
```

- **Taffy narrows the children by the gutter but doesn't say where it is.**
  `content_box_width()` is 12, the box minus border and padding,
  yet the children are 10 wide.
  Child positions come out the same whether the scrollbar sits just inside the border
  or just inside the padding, so the renderer chooses.
  CSS puts it between the border and the padding box,
  so the padding box, and with it the clip, excludes the gutter.
- **`_resolve_layout` (`layout.py:411`) ignores the gutter.**
  It derives `padding` and `content` from border and padding widths alone,
  so a scroll container's `content` is 12 wide where taffy laid its children out in 10.
- **`scroll_height()` is the maximum scroll offset**:
  the 12 rows of the children and the container's padding, minus the 4-row padding box.
- **An absolutely positioned child is placed against the padding box and counts toward the scroll extent.**
  One with `inset_top=Length(30)` lands at `y=31` and raises `scroll_height()` to 27.
- **Percentage insets resolve against the padding box, as in CSS.**
  `inset_top=Percent(1.0)` on a child of a 3-row parent lands at `y=3` with no border,
  and at `y=2`, on the bottom border row, with a border of 1.
- **`waxy.Overflow` has no `Auto`.**
  Its members are `Visible`, `Clip`, `Hidden` and `Scroll`,
  so a scroll container whose `scrollbar_width` isn't 0 always reserves its gutter, whether or not its content overflows.
- **`scrollbar_width` defaults to 0**, so a scroll container reserves no gutter unless its style sets one.
- **Effects start after the frame paints.**
  `handle_effects` runs at `app.py:479`, after `paint_layout` at `app.py:446`,
  so anything an app does in an effect in response to a layout shows up a frame late.

## Design

### The placement walk

After taffy lays the tree out, `Layout.compute` walks the shadow tree from the root down,
carrying two values:

- **The offset**: the sum of the scroll offsets of every scroll container above the node,
  which translates the node's boxes from where taffy put them to where they are on the screen.
- **The clip**: the intersection of the padding boxes, after translation,
  of every ancestor whose overflow is `Hidden`, `Clip` or `Scroll` on that axis, starting from the screen.
  Each axis is separate: `overflow_x=Hidden` with `overflow_y=Visible` bounds only left and right.
  A node's own overflow clips its descendants, not itself.

The walk follows the tree, not paint order.
`paint_order` (`layout.py:271`) reorders nodes by stacking context,
so a `z(1)` dropdown paints after siblings of its ancestors,
and a clip stack built while painting would have dropped those ancestors' clips by then.

The offset and the clip are separate because an element's `clip_to` changes one and not the other.
Computing each clip from translated boxes makes nested scroll and clipping containers compose:
a hidden container inside a scroll container moves its clip with the scroll.

Scrolling changes only the walk's input, not taffy's,
so a scroll leaves taffy's layout cache intact and costs a walk and a repaint.

The walk runs after the offsets for that layout are settled.
Anchoring, `ScrollIntoView` and clamping read taffy's unscrolled positions and extents,
so they run between `compute_layout` and the walk, and the walk translates by the offsets they produce.
When settling focus lays the tree out a second time (`app.py:435`), they run again on that layout,
so the routing table and the paint see the same positions.

### The box model on the screen

`Rects` describes where an element is on the screen:

- **Scrolled.** The walk translates every box by the node's offset,
  so `use_rects`, `Receiver.rects` and hit testing all see the positions that are painted.
- **Whole.** The boxes aren't cut down by the clip.
  A box partly scrolled out of view is still physically at its position, with part of it covered,
  and cutting it down would break what reads it:
  `content` would no longer be the region text wrapped to,
  a dropdown anchored to a half-hidden input would move,
  and an element scrolled entirely out of view would have no position at all.
- **With what's visible.** A `visible` field holds the border box intersected with the clip,
  `None` when the element is clipped out entirely, as `Region.intersection` returns.
  A component that wants to know whether it's on screen reads that.
  A `clip` field holds the clip itself, since the margin box lies outside the border box
  and can't be bounded by `visible`.

`_resolve_layout` subtracts `layout.scrollbar_size` from the right and bottom of the padding box,
so `padding` and `content` match what taffy laid out,
though nothing paints in the gutter (see [No scrollbar](#no-scrollbar)).
`border_fills` takes the sides it draws from the style's border widths rather than from the padding box,
so a gutter beside a side with no border draws no border there.

### Painting within the clip

Every cell an element paints goes through `Paint.fill` or `Paint.write_row`.
Both already bound their writes by the screen; they take a clip region and bound by that instead.
`write_row` already trims a row at the screen's edges and erases the visible half
of a two-cell-wide cluster that straddles one, so text clipping, wide clusters included, comes from
generalizing its left and right bounds.
The cached `border_fills`, `edge_fills` and `text_lines` stay position-independent and keep their caches,
which matters more under scrolling, since every scrolled element moves.

### Border healing across a clip edge

A healing hint whose cell is outside the clip of the element that made it is dropped:
`heal_borders` only checks that the cell under a hint is a border character,
so a hint whose own cell was clipped would rewrite whatever border lies beneath it.
Without that rule, a list item's corner scrolled under the container's top border
would turn the container's `─` into a `┬` that flickers as the list scrolls.
`paint_element` drops it before `paint_layout` merges the element's hints into the rest,
since hints are keyed by position and a later element's clipped hint would otherwise replace
an earlier element's live hint at the same cell.

A hinted cell that survives joins any neighbor, inside its clip or not.
Restricting it to neighbors inside its clip would break the documented border-collapse grid
(`docs/examples/border_healing.py`): its rows and columns are `fill(1)` items, which clip,
so a box's corner at the left edge of its column couldn't join the box beside it in the next column.
A child's border flush against its container's padding box doesn't need the restriction either:
the container's edge cells beside it, `─` and `│`, don't point toward the child's corner, so they never join it.

This doesn't decide #74, whether healing should also require matching styles and `z`.
It's a separate rule about clips, and it leaves an unclipped popup free to join borders beneath it,
since its clip is the screen.

### Hit testing

`target_at` tests each node's `visible` region in place of its border box,
so the mouse over a clipped-off part of an element reaches whatever is painted there.
`use_hovered` intersects each of its rectangles with the clip.
`on_click` tests its release against `visible` in place of the border box,
so a press released over a clipped-off part of the element, where something else is painted, doesn't click it.

### Escaping the clip

A style field, `clip_to`, on the child names what clips it:

- **`"padding"`**, the default: the parent's padding box, intersected with every clip above the parent.
- **`"border"`**: the parent's border box, intersected with every clip above the parent,
  so the element can paint on its parent's border and is still cut off wherever that border is
  (see [Border titles](#border-titles)).
- **`"screen"`**: the element is **unclipped**: no ancestor clips it.
  Its clip resets to the screen.

A parent whose overflow is `Visible` on an axis adds no clip on that axis, so there `"padding"` and `"border"` agree.
The element's descendants' clips start from its clip.

It's a field on the child because the parent's content and its title want different clips from the same parent:
the content stops at the padding box, which is what fixes #388, and only the title reaches the border.
CSS's nearest property, [`overflow-clip-margin`](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow-clip-margin),
is set on the container and widens the clip for every child, so it can't make that split.

Everything else about an unclipped element is as usual:

- **It's positioned against its parent**, so an autocomplete list sits under its input
  with `inset_top=Percent(1.0)`, and it keeps its offset, so it moves when its scroll container scrolls.
- **It paints in the usual stacking order.** It rises above its neighbors with `z`, as any element does,
  so a modal elsewhere with a higher `z` still covers it,
  and a stacking context above it still confines it, as on the web.

Absolute positioning and escaping the clip are independent.
Absolute positioning decides where the list goes and keeps it out of the flow,
so it overlays the content below instead of pushing it down;
being unclipped decides that no ancestor cuts it off.
An autocomplete list uses both.

This is what `position: fixed` with a `z-index` does for a dropdown on the web:
overflow clips only boxes positioned inside the clipping element,
and a fixed box is positioned against the viewport, so it escapes every clip but keeps its place in stacking.
The web then has to compute the box's position from its anchor,
in script or with [anchor positioning](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_anchor_positioning);
here an unclipped box keeps its parent as its containing block, so it's anchored already.

#### Border titles

The documented way to title a border is an absolutely positioned `Text` at `inset_top(-1)`,
which sits on the parent's border row (`docs/examples/border_titles.py`, `docs/examples/layout_alignment.py`).
The clip is the padding box, so in a box with hidden overflow, which every `fill(1)` and other constraint item has,
clipping would erase the title.
Titles set `clip_to="border"`, and the examples and docs say so.
The web clips the same way, and titles a border with `<fieldset>` and `<legend>`, which overflow doesn't clip.

A title clipped to its parent's border box is cut off with that border,
so in a list of titled panels inside a scroll container,
a panel scrolled partly out of view loses the same part of its title as of its border.
An unclipped title would paint past the scroll container's edge instead.

A title on a scroll container's own border doesn't work either way.
It's positioned inside the container, so it scrolls away with the content on the first wheel tick,
and a probe against the pinned `waxy` shows one at `inset_bottom(-1)` adds a row to the container's scroll extent
(`scroll_height()` goes from 0 to 1 with content that fits), though one at `inset_top(-1)` doesn't.
The scrolling docs put the border and title on a wrapper and scroll a child for a titled pane.

### Scroll containers

An element whose overflow is `Scroll` on an axis is a **scroll container** on that axis.
Only a `Div` can be one: a `Text` whose overflow is `Scroll` raises,
since scrolling its own lines would need paint to draw them past its content box,
and horizontally past the width it wraps to, where a `Div` around it scrolls it already.

#### Where the offset lives

The framework holds each scroll container's offset, keyed by its node, as it holds which node is focused,
and controls change it, as `FocusOn` changes focus.
A container scrolls with no component state, as on the web, where `scrollTop` belongs to the element.

The alternative was a controlled offset: a `use_scroll` hook returning the offset and a setter,
with the component passing the offset back to its element.
That puts every scroll in component state, so it re-renders the component on every wheel tick,
and it leaves the framework unable to scroll anything itself.
Moving focus to an element scrolled out of view has to scroll each container above it,
and keeping the reader's place as content changes (see [Scroll anchoring](#scroll-anchoring))
has to adjust offsets between layout and paint, where no component runs.

A scroll still re-renders some components:
`use_rects` re-renders its caller after its rects move,
so a component inside a scroll container that calls `use_rects`, or `use_hovered`, which calls it,
renders again after each scroll that moves it.

#### Extent and clamping

The maximum offset on each axis is taffy's `scroll_width()` and `scroll_height()`.
That includes absolutely positioned descendants, unclipped or not,
so a dropdown that reaches past the bottom of its scroll container extends how far the container scrolls,
as an absolutely positioned dropdown does on the web.
The framework clamps every offset to the extent after each layout.
Offsets of nodes that unmount are dropped.

#### Reading and setting it

`use_scroll(handle=None)` returns a `Scroll` for the calling component's top-level element,
or for the element `handle` names (see [Naming elements](#naming-elements)),
as a React component reads another element's `scrollTop` through a ref:
its offset, its maximum offset, and the size of its padding box (the part of the content in view).
`Receiver` carries the same `Scroll` for a receiving element that's a scroll container, or `None`.
Two controls change an offset, clamped to the extent:
`ScrollTo(target, x=None, y=None)` and `ScrollBy(target, x=0, y=0)`,
where `target` names the scroll container (see [Naming elements](#naming-elements)).
They take each axis separately, as the web's `scrollTo({left, top})` and `scrollBy` do,
so `ScrollTo` leaves an axis it isn't given where it is.

#### Naming elements

The scroll controls, and [`ScrollIntoView`](#scrolling-an-element-into-view), name an element that
isn't necessarily the component's top-level one: an option in a list, a message in a transcript.
On the web that's a DOM node, which React reaches through a ref.

An `ElementHandle` names one, as a `FocusHandle` names a focusable component:
an identity token, created with `use_state(ElementHandle)` and passed to an element's `handle` field,
on `Div` and `Text`, as React passes a ref to an element's `ref` prop.
Two mounted elements given the same handle raise, as two components given the same focus handle do,
and a control whose handle names no mounted element does nothing, as `FocusOn` does.

A control's `target` is an `ElementHandle` or a `Subtree`,
which a handler gets from its `Receiver`, so a library handler can name the element it's on
without the app giving that element a handle.

#### Scrolling an element into view

`ScrollIntoView(target, block="start", inline="nearest")` is the web's
[`scrollIntoView`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView):
it scrolls each scroll container above `target` so the target's border box is in view,
aligned on each axis by `"start"`, `"center"`, `"end"`, or `"nearest"`
(the least scroll that brings it into view, or none if it's already in view),
with the web's defaults.
It works from the innermost container out, as the CSSOM View algorithm does,
each container bringing the box into view where the containers inside it left it.
It stops at an unclipped element, since no container above one clips it:
the autocomplete list's highlighted match scrolls the list, not the form around it,
as the web doesn't scroll a container to show a fixed element its clip doesn't cut off.
The target is resolved against the next render's tree,
so a handle that moves onto the newly highlighted element names that one.

It applies after the next layout and before that layout paints,
after anchoring and before the final clamp.
A handler that moves a highlight returns it beside the state change,
so the scroll shows in the same frame as the new highlight,
where an effect would show it a frame late.
That's the timing React gets from calling `scrollIntoView` in a `useLayoutEffect`,
which runs after the DOM updates and before the browser paints,
as a combobox does when it keeps focus in its input, marks the highlighted option with
`aria-activedescendant`, and scrolls the option into view each time the highlight moves.

Its uses:

- Moving the highlight in a long autocomplete list, with `block="nearest"`.
- Jumping to an earlier message in the agent transcript, such as the previous prompt, with `block="start"`.
- A link within a document, such as a Markdown viewer's table of contents, with `block="start"`.
- Moving focus, which scrolls the newly focused element into view with `block="nearest"`, as browsers do.

The web's `behavior: "smooth"` waits:
animating an offset across frames needs a frame schedule and an easing,
and it has several plausible designs, from a fixed number of frames to a fixed duration.

#### Input

Library handlers, composed onto the scroll container's element like `tab_focus` and `on_click`:

- **`scroll_on_wheel(lines)`** scrolls by `lines` for each `MouseScrolledUp`, `Down`, `Left` and `Right`.
- **`scroll_on_keys(page=0.875)`** scrolls for arrow keys, `PageUp` and `PageDown`, and `Home` and `End`,
  when the container, or an element inside it, is focused, since keys bubble from the focused element.
  A page is `page` times the padding box's height, as `page_up` and `page_down` compute it.

The wheel and key handlers return `None` when the container can't move any further that way,
so the event bubbles to the next scroll container out, the web's scroll chaining.
Each raises, as `focus_receiver_on_press` does, when its receiver isn't a scroll container.

Paging is also available on its own, for apps that bind it to other keys:
`page_down(target, scroll, fraction=0.875)` and `page_up(target, scroll, fraction=0.875)` return the `ScrollBy`
that moves the container `target` names, scrolled as `scroll` says,
by `fraction` of its padding box's height, rounded down and at least one line.
They take the target as `ScrollBy` does, since a `Scroll` doesn't say which container it describes.
The default is Chrome's page step (`kMinFractionToStepWhenPaging` in Chromium's `ScrollableArea`),
so the last lines of one page stay in view at the top of the next to read on from:
on a 24-row pane, a page is 21 rows and 3 stay in view.
`fraction=0.5` is `less`'s half window for `d` and `Ctrl+D`,
and `fraction=1.0` its whole window for `Space`, `f` and `Ctrl+F`, with no overlap.

#### No scrollbar

Counterweight doesn't draw a scrollbar (#417 tracks adding one).
Most TUIs don't draw one either: Claude Code's transcript, `less`, and vim by default;
Ratatui makes one an explicit widget, and Textual is the exception in showing one by default.
A column is expensive in a terminal, and the web's default is platform-specific too:
macOS overlay scrollbars take no space.
An app moves with the wheel and keyboard handlers,
and can show that the reader has scrolled back as Claude Code's transcript does:
a "jump to end" button over the last line, shown while `use_scroll(handle)` reports the log isn't at its end.
The button is a sibling of the scroll container, in a box around it,
since everything inside a scroll container moves with its offset, absolutely positioned elements included.

A scrollbar has several plausible designs and no app yet to choose between them,
and it's purely additive, since nothing in the scrolling API depends on it:

- **Painted by the framework** into the gutter, from the same layout as the content, so the thumb never lags,
  with style fields for its colors and a `use_scrollbar()` hook whose handler drags the thumb,
  keeping the drag's grab in a ref inside the hook.
- **Headless**, like Radix's `ScrollArea`: a hook returns styles and handlers for a track and a thumb
  that the app renders beside the container.
  The hook would read the scroll from `use_scroll`, which reports the previous frame,
  so the thumb would trail every scroll by a frame, since effects and re-renders come after paint.

#### Scroll anchoring

An offset that only gets clamped keeps the content at the top of the view where it is
while content changes around it.
The `agent` benchmark's transcript, rebuilt as a scroll container holding a fixed number of the newest messages
in place of `visible`'s row estimate, shows where that's right and where it isn't,
for a reader either following the stream at the bottom or scrolled back to read an earlier tool call:

| Situation | Following | Reading back |
|---|---|---|
| The streaming message grows | Must stay at the bottom; clamping leaves the new lines below the view | Holding the offset is right |
| A message above the view is dropped to bound the transcript | Must stay at the bottom | The view jumps up by that message's height |
| A tool call above the view expands or collapses | Must stay at the bottom | The view jumps by the change in its height |
| The terminal narrows, rewrapping every message | Must stay at the bottom | The view jumps to somewhere else in the transcript |

Holding the offset is right in one cell of the eight.
The app can't fix the rest itself without a visible jump:
`use_scroll` reports the extent from the last layout, and effects start after the frame paints,
so the frame with the change paints before any `ScrollTo` from the app arrives.
The correction has to happen in the framework, between layout and paint, where offsets are clamped.

A flag that pins a container to its end fixes the left column and nothing in the right.
The right column needs **scroll anchoring**, CSS's
[`overflow-anchor`](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow-anchor):

- Before each layout, the framework picks each scroll container's **anchor**
  from the last frame's layout, moved by any scroll since:
  the first node in tree order whose border box is in view,
  where a node wholly in view is the anchor, a node partly in view is descended into for a better one
  (and is the anchor if none of its children is in view),
  and a nested scroll container is never descended into.
  Unclipped nodes are never anchors.
- After the layout, it adjusts the offset so the anchor's top edge is as far from the top of the container's
  padding box as it was, then clamps.
- If the anchor unmounted or was hidden, the offset is only clamped.
- A container scrolled to the top doesn't anchor, so content added above it pushes the rest down,
  as the [spec](https://drafts.csswg.org/css-scroll-anchoring/) skips anchor selection at a zero offset.
- Only the vertical offset is anchored, as the spec anchors only the block axis.

Browsers anchor by default, and so does this, with a style field to turn it off, as `overflow-anchor: none` does:
a scroll container that sets it only clamps,
and a node inside one that sets it is never an anchor, nor is anything inside it.

The left column is opt-in, through a second style field that makes a container **stick to its end** on an axis:
when it's scrolled to its end before a layout, it's scrolled to its end after.
A container whose content fits is at its end, since its offset and its maximum are both zero,
so a transcript that starts short follows its end from the first message,
and a container that mounts already overflowing starts at its end.
Sticking by default would make every list or document that starts short and then grows follow its end,
which is right for a transcript or a log and wrong for most other things.
The web has no property for it either:
a page opts in by placing an anchor element last, or by reversing a column's direction so it starts at the end.
A container that sticks to its end still anchors once it's scrolled back from the end.

The anchor's top edge stays put, not the line inside it,
so when a long paragraph that's the anchor rewraps, the line the reader was on can still move within it.
That's the web's behavior too.

### Utilities and docs

Generated overflow utilities, for both axes and each axis alone:
`overflow_visible`, `overflow_hidden`, `overflow_clip` and `overflow_scroll`, with `_x` and `_y` variants,
turning scroll anchoring off, sticking to the end on each axis,
and a utility for each value of `clip_to`.

Docs pages, with screenshot examples:

- **Clipping**: the #388 container, clipping on one axis, each value of `clip_to`,
  a list of titled panels in a scroll container,
  and what `inset_top=Percent(1.0)` means against a bordered parent
  (the percentage resolves against the padding box, so it lands on the bottom border row).
- **Scrolling**: a scroll container with each of the handlers, `use_scroll`, a "jump to end" button that reads a log's scroll by handle,
  scroll anchoring and sticking to the end, with the agent transcript's situations,
  and a titled pane that scrolls a child inside its border.

### Cookbook: autocomplete

A cookbook page, `docs/cookbook/autocomplete.md`, with its example in `docs/examples/autocomplete.py`,
builds a field that suggests completions as you type, in a form panel that clips.
It's the case unclipped elements exist for, and it exercises them alongside focus, `z` and `use_rects`.
There's no text input element (`docs/ecosystem.md`), so the recipe builds a minimal one:
a focusable component holding its text in state, with a key handler for characters and `Backspace`.

The recipe covers:

- **Matching.** A candidate matches when the typed letters appear in it in order,
  with anything between them: the pattern puts a `*` between and around the typed letters,
  each escaped with `glob.escape`, so typing `cwt` matches `counterweight`
  and a typed `[` or `?` matches itself.
  It lowercases both sides and uses `fnmatch.fnmatchcase`,
  since `fnmatch.fnmatch` normalizes case only on case-insensitive platforms.
- **The list.** The matches for the text, in a `Div` that's absolutely positioned at `inset_top=Percent(1.0)`, unclipped, and raised with `z`,
  rendered only while the field is focused and has matches,
  so it closes when focus moves away.
- **Choosing.** `Down` and `Up` move a highlighted match, kept in state,
  `Enter` or `Tab` replaces the text with it, and `Escape` closes the list until the text changes.
  A click on a match chooses it, and keeps focus in the field.
- **Escaping the panel.** The panel is a `fill(1)` item, whose hidden overflow would cut the list off.
  The screenshots show the list reaching past the panel's border,
  and the same field with the default `clip_to`, cut off at the border, to show what `"screen"` does.
- **Opening upward.** A field near the bottom of the screen puts the list above it,
  at `inset_bottom=Percent(1.0)`, when there's more room above than below,
  comparing the field's `use_rects` with the screen's height from the root's `use_rects`.
- **Inside a scroll container**:
  the form scrolls, and the open list moves with its field and extends how far the form scrolls.
- **A long list**: the list is a scroll container with a maximum height,
  one `ElementHandle` sits on whichever match is highlighted,
  and every key the field handles returns `ScrollIntoView(handle, block="nearest")` beside its state change,
  while focus stays in the field.
  The handle names the newly highlighted match because the control resolves it after the render.

## Steps

Each phase is its own PR, and each leaves the app working.

1. **Clipping (#388).**
   Subtract the scrollbar gutter in `_resolve_layout`.
   Compute each node's clip in the placement walk, with an offset of zero, and add `Rects.visible`.
   Clip `Paint.fill` and `Paint.write_row`, and pass each node's clip from `paint_layout`.
   Drop healing hints outside their element's clip.
   Clip hit testing in `target_at`, `use_hovered` and `on_click`.
   Add `clip_to` with `"padding"` and `"border"`, and their utilities,
   and set `clip_to="border"` on the border titles in the examples and docs.
   Add the `visible`, `hidden` and `clip` overflow utilities and the clipping docs.
   Regenerate every screenshot and review each change:
   the constraint utilities' hidden overflow means some existing screenshots will change,
   and each change should be overflow that was painting over something.
2. **Unclipped elements.**
   `clip_to="screen"`, the clip reset in the walk, its utility, and the autocomplete cookbook page.
3. **Scroll offsets (#389).**
   Offsets held by the app loop, clamped after each layout,
   the walk's offset, `use_scroll` with and without a handle, `Receiver.scroll`, `ElementHandle`, `ScrollTo` and `ScrollBy`,
   `scroll_on_wheel`, and the `overflow_scroll` utilities.
   Rebuild the `agent` transcript as a scroll container holding a fixed number of the newest messages,
   replacing `visible`'s row estimate, so a live run (`live_root`) can wheel back through it.
   The count bounds it as `visible` does, so each frame's cost stays flat across a run
   and messages still drop off the top, the table's second row.
   Put the autocomplete recipe's form in a scroll container, with a screenshot of the list scrolled with it.
4. **Scroll anchoring.**
   Choosing anchors before layout, adjusting offsets after it,
   the style field and utility to turn it off,
   and the style field and utilities to stick to the end, which the `agent` transcript sets.
   Add an `agent` workload whose autopilot, which already takes events and controls,
   scrolls back partway, so the benchmark measures a transcript read back while it streams.
5. **Scrolling into view and keyboard scrolling (part of #390).**
   `ScrollIntoView`, scrolling focused elements into view,
   `scroll_on_keys`, `page_up` and `page_down`, and the scrolling docs.
   Give the live `agent` run a key that jumps back through earlier messages,
   and the autocomplete recipe its long list.
   The workload's only user prompt is its first message, which drops off once the transcript is full,
   so the key, `[`, steps back through the tool calls instead, the transcript's other landmarks,
   rather than changing `step` and with it the benchmark's baseline.

## Testing

- The #388 example paints within its border, and `below` is intact.
- Clipping on one axis leaves the other unbounded.
- Nested clipping containers clip to the intersection.
- A `z(1)` descendant of a clipping container is still clipped.
- A two-cell-wide cluster straddling a clip edge leaves a space on the visible side.
- A border clipped by an ancestor leaves no healing hint behind,
  a border flush against its container's padding box doesn't join the container's border,
  and collapsed borders of clipping items still join across their edges.
- The mouse over a clipped-off part of an element targets the element painted there,
  `use_hovered` reports it outside, and a press released there doesn't click the element.
- A clipped healing hint doesn't displace another element's live hint at the same cell.
- A border title in a `fill(1)` box still paints on the border row.
- A titled panel scrolled partly out of a scroll container loses its title where it loses its border,
  and nothing it paints reaches past the container's padding box.
- An unclipped element escapes every ancestor's clip, receives the mouse there,
  moves with its scroll container, and is covered by a later sibling of its ancestor with a higher `z`.
- A scrolled container paints its children translated and clipped,
  `use_rects` reports the translated boxes, and a click lands on the child painted under it.
- An offset is clamped when the content shrinks, and dropped when the container unmounts.
- A wheel event at the end of a scroll container's range scrolls the container outside it.
- `page_down` moves by 87.5% of the padding box by default, and with a fraction by that share of it,
  at least one line, and clamps at the end.
- Each cell of the agent transcript's table, as a test against a small transcript that sticks to its end:
  following stays at the bottom, and reading back keeps the anchor's top edge in place.
- A container that doesn't stick to its end, and whose content starts short and then grows, stays at the top.
- A container that sticks to its end and starts short follows its end once its content overflows.
- A container with anchoring turned off only clamps.
- Focusing an element scrolled out of view scrolls it into view through nested containers.
- `ScrollIntoView` aligns its target by each of `"start"`, `"center"`, `"end"` and `"nearest"`,
  leaves an element already in view alone under `"nearest"`,
  and shows in the same frame as the state change returned beside it.
- `use_scroll(handle)` reports the named element's scroll, and a component reading two scrolls
  renders again once either changes.
- Two mounted elements with the same `ElementHandle` raise,
  and a control naming an unmounted handle does nothing.
- Run `just mutate` over the new code, and profile a render-heavy workload before and after each phase
  (`cw-profile`), with the scrolled `agent` workload added in phase 4.

## Open questions

- **Naming `clip_to` and its values.** `clip_to` names what clips the element;
  the web's nearest names are `overflow-clip-margin`, which is set on the container,
  and `position: fixed` for `"screen"`, which also changes what the box is positioned against,
  so both would mislead here.
- **A top layer for modals.** A modal or command palette declared deep in the tree
  needs to escape stacking contexts as well as clips, which the web does with its
  [top layer](https://developer.mozilla.org/en-US/docs/Glossary/Top_layer),
  ordered by when each element was opened, so the newest is on top.
  An unclipped element with a high `z` covers the cases where no ancestor forms a stacking context.
  Ordering a top layer by tree order or by opening order are both plausible,
  and the second means the framework tracking when each one appeared,
  so it waits for an app that needs one.
