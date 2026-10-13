# Plan: Clipping and Scrolling

This plan covers clipping painting to containers with hidden overflow (#388),
the hit testing that has to agree with it,
a way for a popup such as an autocomplete list to escape the clip,
and scroll containers (#389), with their input, scrollbar, keyboard scrolling (part of #390),
and scroll anchoring, driven by the `agent` benchmark's transcript.
They share one mechanism: a walk down the tree after layout that places each node on the screen,
carrying a scroll offset and a clip.
It also settles how border healing treats a clip edge, which touches #74.
It doesn't cover a top layer for modals (see [Open questions](#open-questions)).

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
  so a scroll container always reserves its gutter, whether or not its content overflows.
- **Effects start after the frame paints.**
  `handle_effects` runs at `app.py:479`, after `paint_layout` at `app.py:447`,
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

The offset and the clip are separate because an unclipped element resets one and not the other.
Computing each clip from translated boxes makes nested scroll and clipping containers compose:
a hidden container inside a scroll container moves its clip with the scroll.

Scrolling changes only the walk's input, not taffy's,
so a scroll leaves taffy's layout cache intact and costs a walk and a repaint.

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
  empty when the element is clipped out entirely.
  A component that wants to know whether it's on screen reads that.

`_resolve_layout` subtracts `layout.scrollbar_size` from the right and bottom of the padding box,
so `padding` and `content` match what taffy laid out,
and `Rects` gains the **gutter** regions between the border and the padding box,
where the scrollbar paints.
`border_fills` and `edge_fills` take the padding box as the inner edge,
so a border with a gutter inside it must still fill only the border.

### Painting within the clip

Every cell an element paints goes through `Paint.fill` or `Paint.write_row`.
Both already bound their writes by the screen; they take a clip region and bound by that instead.
`write_row` already trims a row at the screen's edges and erases the visible half
of a two-cell-wide cluster that straddles one, so text clipping, wide clusters included, comes from
generalizing its left and right bounds.
The cached `border_fills`, `edge_fills` and `text_lines` stay position-independent and keep their caches,
which matters more under scrolling, since every scrolled element moves.

### Border healing across a clip edge

Each healing hint carries the clip of the element that made it.
A hint whose cell is outside that clip is dropped:
`heal_borders` only checks that the cell under a hint is a border character,
so a hint whose own cell was clipped would rewrite whatever border lies beneath it.
A hinted cell joins only neighbors inside its clip,
so a child's border clipped flush against its container never joins the container's border.
Without that rule, a list item's border scrolled under the container's top border
would sprout a `┬` that flickers as the list scrolls.

This doesn't decide #74, whether healing should also require matching styles and `z`.
It's a separate rule about clips, and it leaves an unclipped popup free to join borders beneath it,
since its clip is the screen.

### Hit testing

`target_at` tests each node's `visible` region in place of its border box,
so the mouse over a clipped-off part of an element reaches whatever is painted there.
`use_hovered` intersects each of its rectangles with the clip.

### Escaping the clip

A style field makes an element **unclipped**: no ancestor clips it.
Its clip resets to the screen, and its descendants' clips start from there.
Everything else about it is as usual:

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

### Scroll containers

An element whose overflow is `Scroll` on an axis is a **scroll container** on that axis.

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

#### Extent and clamping

The maximum offset on each axis is taffy's `scroll_width()` and `scroll_height()`.
That includes absolutely positioned descendants, unclipped or not,
so a dropdown that reaches past the bottom of its scroll container extends how far the container scrolls,
as an absolutely positioned dropdown does on the web.
The framework clamps every offset to the extent after each layout.
Offsets of nodes that unmount are dropped.

#### Reading and setting it

`use_scroll()` returns a `Scroll` for the calling component's top-level element:
its offset, its maximum offset, and the size of its padding box (the part of the content in view).
`Receiver` carries the same `Scroll` for a receiving element that's a scroll container, or `None`.
Two controls change an offset, clamped to the extent:
`ScrollTo(target, position)` and `ScrollBy(target, delta)`,
where `target` names the scroll container (see [Naming elements](#naming-elements)).

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
- **`scroll_on_keys(page=1.0)`** scrolls for arrow keys, `PageUp` and `PageDown`, and `Home` and `End`,
  when the container is focused.
  A page is `page` times the padding box's height, as `page_up` and `page_down` compute it.
- **`scroll_on_scrollbar`** claims a press on the scrollbar: on the thumb it drags,
  on the track it pages toward the press.

The wheel and key handlers return `None` when the container can't move any further that way,
so the event bubbles to the next scroll container out, the web's scroll chaining.
Each raises, as `focus_receiver_on_press` does, when its receiver isn't a scroll container.

Paging is also available on its own, for apps that bind it to other keys:
`page_down(scroll, fraction=1.0)` and `page_up(scroll, fraction=1.0)` return the `ScrollBy`
that moves `scroll` by `fraction` of its padding box's height, rounded down and at least one line.
The default is a whole window, as `less` moves for `Space`, `f` and `Ctrl+F`,
and `fraction=0.5` is its half-window `d` and `Ctrl+D`.
`less` keeps no lines of overlap between pages; a fraction below 1 does that.

#### The scrollbar

The framework paints a scrollbar into each gutter of a scroll container that can scroll on that axis:
a track the length of the gutter, and a thumb whose length and position are the padding box's share
of the scrollable extent and the offset's share of the maximum, at least one cell long.
A gutter whose axis can't scroll is painted as the track.
Style fields set the thumb and track colors, as CSS's `scrollbar-color` does.

#### Scroll anchoring

An offset that only gets clamped keeps the content at the top of the view where it is
while content changes around it.
The `agent` benchmark's transcript, rebuilt as a scroll container holding every message
in place of `visible`'s estimate, shows where that's right and where it isn't,
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

- Before each layout, the framework picks each scroll container's **anchor**:
  the first node in tree order whose border box is at least partly in view,
  descending into it while one of its children is, and not descending into a nested scroll container.
  Unclipped nodes are never anchors.
- After the layout, it adjusts the offset so the anchor's top edge is where it was on the screen,
  then clamps.
- A container scrolled to its end on an axis stays at its end,
  which is the left column, and is what the web gets by putting an anchor element last.
- If the anchor unmounted, the offset is only clamped.

Browsers anchor by default, and so does this, with a style field to turn it off for a container,
as `overflow-anchor: none` does.
A container that turns it off only clamps.

The anchor's top edge stays put, not the line inside it,
so when a long paragraph that's the anchor rewraps, the line the reader was on can still move within it.
That's the web's behavior too.

### Utilities and docs

Generated overflow utilities, for both axes and each axis alone:
`overflow_visible`, `overflow_hidden`, `overflow_clip` and `overflow_scroll`, with `_x` and `_y` variants,
the scrollbar width and colors, turning scroll anchoring off, and a utility for unclipped elements.

Docs pages, with screenshot examples:

- **Clipping**: the #388 container, clipping on one axis, unclipped elements,
  and what `inset_top=Percent(1.0)` means against a bordered parent
  (the percentage resolves against the padding box, so it lands on the bottom border row).
- **Scrolling**: a scroll container with each of the handlers, `use_scroll`, the scrollbar styles,
  and scroll anchoring, with the agent transcript's situations.

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
  and the same field without `unclipped`, cut off at the border, to show what the field does.
- **Opening upward.** A field near the bottom of the screen puts the list above it,
  at `inset_bottom=Percent(1.0)`, when there's more room above than below,
  comparing the field's `use_rects` with the screen's height from the root's `use_rects`.
- **Inside a scroll container**, once phase 3 lands:
  the form scrolls, and the open list moves with its field and extends how far the form scrolls.
- **A long list**, once phase 6 lands: the list is a scroll container with a maximum height,
  each match carries an `ElementHandle`, and `Down` and `Up` return
  `ScrollIntoView(match, block="nearest")` beside the highlight change, while focus stays in the field.
  Until then, the recipe shows at most a fixed number of matches.

## Steps

Each phase is its own PR, and each leaves the app working.

1. **Clipping (#388).**
   Subtract the scrollbar gutter in `_resolve_layout`.
   Compute each node's clip in the placement walk, with an offset of zero, and add `Rects.visible`.
   Clip `Paint.fill` and `Paint.write_row`, and pass each node's clip from `paint_layout`.
   Carry clips in healing hints and apply the clip rule.
   Clip hit testing in `target_at` and `use_hovered`.
   Add the `visible`, `hidden` and `clip` overflow utilities and the clipping docs.
   Regenerate every screenshot and review each change:
   the constraint utilities' hidden overflow means some existing screenshots will change,
   and each change should be overflow that was painting over something.
2. **Unclipped elements.**
   The style field, the clip reset in the walk, its utility, and the autocomplete cookbook page.
3. **Scroll offsets (#389).**
   Offsets held by the app loop, clamped after each layout,
   the walk's offset, `use_scroll`, `Receiver.scroll`, `ElementHandle`, `ScrollTo` and `ScrollBy`,
   `scroll_on_wheel`, and the `overflow_scroll` utilities.
   Rebuild the `agent` transcript as a scroll container holding every message and delete `visible`,
   so a live run (`live_root`) can wheel back through it.
   Put the autocomplete recipe's form in a scroll container, with a screenshot of the list scrolled with it.
4. **Scroll anchoring.**
   Choosing anchors before layout, adjusting offsets after it, staying at the end,
   and the style field and utility to turn it off.
   Add an `agent` workload whose autopilot, which already takes events and controls,
   scrolls back partway, so the benchmark measures a transcript read back while it streams.
5. **The scrollbar.**
   Painting it, its style fields and utilities, and `scroll_on_scrollbar`.
6. **Scrolling into view and keyboard scrolling (part of #390).**
   `ScrollIntoView`, scrolling focused elements into view,
   `scroll_on_keys`, `page_up` and `page_down`, and the scrolling docs.
   Give the live `agent` run a key that jumps to the previous prompt,
   and the autocomplete recipe its long list.

## Testing

- The #388 example paints within its border, and `below` is intact.
- Clipping on one axis leaves the other unbounded.
- Nested clipping containers clip to the intersection.
- A `z(1)` descendant of a clipping container is still clipped.
- A two-cell-wide cluster straddling a clip edge leaves a space on the visible side.
- A border clipped by an ancestor leaves no healing hint behind,
  and a border flush against its container's padding box doesn't join the container's border.
- The mouse over a clipped-off part of an element targets the element painted there,
  and `use_hovered` reports it outside.
- An unclipped element escapes every ancestor's clip, receives the mouse there,
  moves with its scroll container, and is covered by a later sibling of its ancestor with a higher `z`.
- A scrolled container paints its children translated and clipped,
  `use_rects` reports the translated boxes, and a click lands on the child painted under it.
- An offset is clamped when the content shrinks, and dropped when the container unmounts.
- A wheel event at the end of a scroll container's range scrolls the container outside it.
- `page_down` with a fraction moves by that share of the padding box, at least one line,
  and clamps at the end.
- Each cell of the agent transcript's table, as a test against a small transcript:
  following stays at the bottom, and reading back keeps the anchor's top edge in place.
- A container with anchoring turned off only clamps.
- Focusing an element scrolled out of view scrolls it into view through nested containers.
- `ScrollIntoView` aligns its target by each of `"start"`, `"center"`, `"end"` and `"nearest"`,
  leaves an element already in view alone under `"nearest"`,
  and shows in the same frame as the state change returned beside it.
- Two mounted elements with the same `ElementHandle` raise,
  and a control naming an unmounted handle does nothing.
- Run `just mutate` over the new code, and profile a render-heavy workload before and after each phase
  (`cw-profile`), with the scrolled `agent` workload added in phase 4.

## Open questions

- **Naming the unclipped field.** `unclipped` says what it does to the element;
  the web's nearest name is `position: fixed`, which also changes what the box is positioned against,
  so it would mislead here.
- **A top layer for modals.** A modal or command palette declared deep in the tree
  needs to escape stacking contexts as well as clips, which the web does with its
  [top layer](https://developer.mozilla.org/en-US/docs/Glossary/Top_layer),
  ordered by when each element was opened, so the newest is on top.
  An unclipped element with a high `z` covers the cases where no ancestor forms a stacking context.
  Ordering a top layer by tree order or by opening order are both plausible,
  and the second means the framework tracking when each one appeared,
  so it waits for an app that needs one.
