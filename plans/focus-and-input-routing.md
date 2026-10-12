# Plan: Focus and Input Routing

This plan covers how key and mouse events reach elements:
one handler for both kinds of input (#124),
routing each event to one target and bubbling it through the target's ancestors,
and focus, which picks the target for keys (#390).
Tab navigation, click-to-focus, and the like are library handlers that apps compose,
not defaults built into the framework.
It is the design that step 5 of `plans/react-features.md` asked for.
It doesn't cover the text input hook (#391), scroll containers (#389), or text selection (#399),
though all three depend on it and the design is checked against them below.

## Problems

- **Every key reaches every handler.** `render_loop` (`app.py:362`) calls each element's `on_key`
  in reverse tree order. Two components that both handle arrow keys both act on every arrow key,
  so apps thread "which one is active" through shared state.
  `examples/stopwatch.py` does exactly this: each `stopwatch` takes a `selected` prop
  and its `on_key` ignores keys unless it's selected.
- **Every mouse event reaches every element under the pointer.**
  `app.py:366` calls `on_mouse` on each element whose border contains the current _or previous_
  position, so overlapping elements (a child and every ancestor, or absolutely positioned siblings)
  all act on one click, with no way for the innermost to claim it.
- **There is no way to stop an event.** A handler's return value is at most one control,
  and nothing else.
- **Keys and mouse events are split across two fields.** A `less`-like view that scrolls on both `Down`
  and the wheel writes the logic in both handlers,
  or passes one function as both `on_key` and `on_mouse` (#124),
  which type-checks because handler parameters are contravariant, but which nothing in the API suggests.
  `examples/wordle.py` builds fake `KeyPressed` events in its mouse handlers to reuse the key handler.
  Each routed event kind to come, starting with paste (#391), would add another field.

## Desired state

### One handler per element

`Div` and `Text` have a single `on_input` field in place of `on_key` and `on_mouse`:

```python
InputResponse = Union[AnyControl, tuple[AnyControl, ...], None]

on_input: Callable[[InputEvent], InputResponse] | None = None
```

`InputEvent` is the union of the routed event types described below.
Both aliases are `Union` assignments like `MouseEvent` and `AnyEvent` in `events.py`,
rather than PEP 695 `type` statements, which `isinstance` can't take.
`TerminalResized` and `StateSet` aren't in it and never reach a handler.
A later `Pasted` event (#391) joins the union and routes like a key.

A handler matches on the event, so one case covers both kinds of input:

```python
def on_input(event: InputEvent) -> InputResponse:
    match event:
        case KeyPressed(key=Key.Down) | MouseScrolledDown():
            set_offset(lambda o: o + 1)
            return ()
        case KeyPressed(key=Key.Up) | MouseScrolledUp():
            set_offset(lambda o: o - 1)
            return ()
        case _:
            return None
```

The alternative is to keep `on_key` and `on_mouse` and give both the routing below.
An event is either a key or a mouse event, so it would reach exactly one field,
with no ordering between them, and existing handlers would keep working.
It gives up having one way to write a handler that covers both kinds of input,
and adds a field for each routed event kind to come.

The cost of one field is that a handler interested in only one kind of input
receives the others, and every existing `on_key=`/`on_mouse=` breaks.
Receiving the others is cheap: a handler that falls off the end returns `None`,
and a key-only handler sees a `MouseMoved` in a call that falls through its cases.
The root, an ancestor of every hit target, sees every pointer move that nothing below it stops,
since the app turns on any-motion tracking (`output.py:28`).
A root handler that matches many keys can return early on any other event with a guard clause,
which the events docs should recommend.
The break is loud: constructing an element with `on_key=` raises a `TypeError`,
and a handler annotated `Callable[[KeyPressed], ...]` fails type checking against `on_input`,
because parameters are contravariant.

### Routing: one target, then bubble

Each input event has one **target** node in the shadow tree.
The app calls the target element's `on_input`, then each ancestor's in turn up to the root.
Ancestry is the shadow tree's, not geometry's,
so an absolutely positioned child bubbles to its parent even when drawn outside it, as in the DOM.

A handler's return value decides whether the event keeps bubbling:

- `None` means "not mine": the event continues to the parent.
- Anything else means "mine": the event stops, and the controls are applied.
  That is a control (`return Quit()`),
  a tuple of controls applied in order (`return Bell(), Screenshot.to_file(path)`),
  or `()`, a tuple of no controls, when there's nothing else to do.

`()` is the one way to write the commonest response, "I changed some state and this event is mine".
A no-op control named for it would be a second spelling of the same thing.
Dispatch and the combinators below test a response with `is not None`, never for truthiness,
because `()` is falsy; for the same reason,
the docs should warn against chaining handlers with `or`, which treats `()` as unhandled.
Dispatch raises on any other return value, such as a list, rather than ignoring it.

One rule covers when an event stops: whenever the response isn't `None`.
A handler that wants to issue a control without stopping the event
sends it with `use_send_control` (`plans/react-features.md` step 2).

Bubbling is the default, and stopping is explicit, because the opposite default is worse.
If running a handler stopped the event, every handler that matches a few keys
would need a `case _: return Propagate()`,
and forgetting it in a focused text input would swallow the app's `ctrl+c` quit binding on the root.
Under bubble-by-default, the failure is a handler that changes state without returning `()`
while an ancestor binds the same key, so both act.
That is the deliberate override case (a focused list claiming `Down` from a scrolling page),
and focus already removes the common case of two _siblings_ both acting.
The docs should recommend returning `()` (or the controls) from every case that does something.

There is no capture phase. Nothing in the examples or the issues needs one.

### What a handler receives

Each handler receives the event with the routing context of its own element attached:

- `rects`: the receiving element's `Rects`, as `use_rects` returns them.
- `is_target`: whether the receiving element is the event's target, rather than an ancestor it bubbled to.
- For mouse events, `relative`: the pointer's position relative to the top-left of the receiving element's content box.
- `focus_handle`: the receiving element's `FocusHandle` if its component called `use_focus`, or `None`.
- `is_focused`: whether the receiving element is the focused node.
  For a key it's the same as `is_target`;
  for a mouse event it tells a text input whether a click is the one that focuses it.

Each element on the path receives its own copy, so a parent sees its own rects, not its child's.
`on_click` uses `rects` to tell a release inside the element from one outside,
since press capture delivers both;
`focus_on_press` uses `focus_handle` to name the element to focus;
a text input uses `relative` to place its cursor;
a scroll container pages by its own height.
A handler that doesn't need the context ignores it.

The hooks stay, because render has no event to read:
`use_focus` declares the component focusable and gives it `is_focused` to draw a focus ring,
and `use_rects` and `use_hovered` serve layout and hover that change what renders.
The event repeats what the router already knows at the moment a handler runs,
so a handler needs no hook just to get data the router has,
and a component doesn't thread a hook's result into its handlers.

The input parser and the autopilot produce events without routing context,
since they don't know where an event will go.
The router delivers a routed subclass of each event type,
such as `RoutedMouseUp(MouseUp)` with the fields above, and `InputEvent` is the union of those.
Handlers match on the base classes as they do now:
`case MouseUp(button=1)` matches a `RoutedMouseUp`, and mypy narrows it to the routed type,
so the extra fields are available without changing how a handler is written.
A separate type keeps every routed event's fields required,
rather than defaulted for events that were never routed.
A routed event isn't equal to the raw event it came from,
so a test that records events compares their fields rather than the events.
`Rects` moves from `counterweight.hooks` to `counterweight.geometry`, re-exported from `counterweight.hooks`,
and `FocusHandle` is defined outside the hooks package too,
since `events.py` can't import from the hooks package, which imports `events.py`.

### No built-in behavior

Nothing happens to an input event except what handlers do.
Tab doesn't move focus, a click doesn't focus, and a drag doesn't select,
unless a handler on the event's path says so.
The library ships those behaviors as handlers in `counterweight.handlers`,
and the framework keeps only the mechanism they drive:
routing, press capture, focus state, and (with #399) selection state.

Event handling is among the hardest parts of a UI framework to understand,
and a built-in default is behavior that no handler on the path mentions.
Browsers pair their defaults with a second bit to cancel them, `preventDefault` alongside `stopPropagation`,
because a native default runs after the handlers and outside their control.
With no defaults, a handler's response only says whether the event stops, and which controls to apply.
The combinations browsers express with two bits come from composition instead:
keeping a behavior means composing its handler in, and preventing it means leaving it out.
A non-selectable element doesn't opt out of selection; it just doesn't have `select_text`.

The library handlers are pure functions from an event to a response, testable without running an app:

- `tab_focus` returns `FocusNext()` for Tab and `FocusPrevious()` for Shift+Tab.
  An app puts it on its root, which is last on every key's bubble path,
  so a focused component that wants Tab (indenting in a text area) claims it with `()` first.
- `focus_on_press` returns `FocusOn(event.focus_handle)` for a `MouseDown`.
  It raises if `focus_handle` is `None`, which means it's attached to an element that isn't focusable:
  either the component never called `use_focus`,
  or the handler is on an inner element rather than the component's top-level one.
  It stops the event, so of nested focusables, the nearest to the pointer takes focus.
- `on_click(action)` claims every event of a button 1 press that reaches it,
  and on the release calls `action` if the release is inside the element's border,
  returning the controls `action` returns, or `()` if it returns `None`.

Two combinators compose handlers into the one an element takes:

- `first(*handlers)` calls each in turn and returns the first response that isn't `None`, or `None`.
- `each(*handlers)` calls all of them, and if any responded with something other than `None`,
  returns a tuple of every control they returned, in handler order; otherwise it returns `None`.

The common shapes, with `select_text` from #399:

```python
# A transcript message: selectable, not focusable.
Text(content=message, on_input=select_text)

# A composer: focusable and selectable. Both handlers claim MouseDown, so each runs both.
focus = use_focus()
Div(style=ring if focus.is_focused else plain, on_input=each(focus_on_press, select_text))

# A button: focusable, not selectable.
focus = use_focus()
Text(content="Send", style=ring if focus.is_focused else plain, on_input=each(on_click(send), focus_on_press))

# The root: Tab navigation is opt-in, and its precedence over the app's own bindings is explicit.
Div(..., on_input=first(app_shortcuts, tab_focus))
```

Every library handler that acts on a press (`on_click`, `focus_on_press`, and `select_text`)
claims its `MouseDown` rather than letting it bubble.
So the innermost element with a press handler owns the press,
the same rule that makes the nearest focusable take focus,
and a press on a button can't also start an ancestor's selection or drag
(dragging a panel by its title bar when the press lands on the title bar's close button).
Press capture routes the rest of a press by the node it landed on, whoever claimed it,
so claiming only decides whether ancestors see the press too.
Two press handlers on one element therefore compose with `each`, as the composer and the button do,
and an ancestor's press handler never runs for a press on a descendant that has its own.
A text input that renders its own clear button,
and wants a click on that button to focus the input,
composes a handler returning `FocusOn(focus.handle)` for a `MouseDown` into the button's handler too,
using the handle from its own `use_focus`,
since the button's copy of the event carries the button's `focus_handle`, which is `None`.
That wiring is explicit and lives in user space, which is the point:
the alternative, letting presses bubble, makes a click on a button also select or drag
whenever an ancestor has a press handler, and nothing at the button's call site would show it.

The costs:

- **A missing handler fails silently.** A focusable component without `focus_on_press` just doesn't focus on click,
  and an app without `tab_focus` has no Tab navigation.
  Higher-level pieces come with their handlers composed in (the text input hook from #391 returns one handler),
  so most apps wire the primitives only for their own components.
- **Composition order is the user's to get right.** In `first(select_text, my_drag)`, `my_drag` never sees a press.
  The mistake is visible at the call site and deterministic,
  unlike a browser default interacting with a handler.
- **An element can't suppress one ancestor's handler while letting the event reach that ancestor's other handlers.**
  Browsers do that with `preventDefault` without `stopPropagation`; here the only lever is stopping.
  The guideline is to put a handler on the narrowest element it applies to,
  such as `select_text` on each message rather than on the transcript,
  so an element that shouldn't trigger it isn't on its path.

### Mouse targets

The target of a mouse event is the topmost visible element whose border rectangle
contains the pointer: the last such element in paint order.
Paint order is the `(z, order)` sort that `paint_layout` applies (`paint.py:195`),
not the tree order `LayoutTree.compute` returns,
so hit-testing shares that sort key with painting,
and an element raised with `z` takes clicks from a later sibling it covers.
Hidden elements have no layout, so they're never hit.

While a button is held, from `MouseDown` to `MouseUp`, every mouse event targets
the node that received the `MouseDown`, wherever the pointer is.
This is the implicit pointer grab that X11, Win32, and DOM pointer capture all provide.
It replaces today's "current or previous position" rule,
which exists so a drag keeps reaching its element for one more event after the pointer leaves it,
but loses the drag entirely when the pointer outruns a render
(the TODO in `examples/mouse.py`'s `draggable_text`).
If the captured node unmounts mid-press, the remaining events of that press route by hit-testing.
A `MouseDown` that arrives while a press is captured ends the capture and hit-tests afresh,
so a release the terminal never reported (focus switched away mid-drag)
holds the capture only until the next press.

An element no longer sees the move that leaves it.
`use_hovered` already covers hover state from `use_mouse`, which is unchanged:
it's a broadcast of the pointer's state, not a routed event.

### Key targets and focus

The target of a key event is the **focused** node, or the root component's node when nothing is focused.
That is the node of the component passed to `app()`,
not the `screen` element the app wraps it in (`app.py:164`), which has no handler and no ancestors.
"Nothing focused" therefore means "the root is focused":
handlers on the root and only the root receive keys,
with no broadcast fallback for apps that never call `use_focus`.
A fallback would be a second routing mode whose interaction with the first
every app with one focusable component would have to reason about.

The cost is that a component deep in the tree can't own a global shortcut.
A help overlay toggled with `?` puts that binding on the root,
or on an ancestor of whatever is focused, rather than on itself.
Ink's `useInput` broadcasts every key and uses focus only to gate handlers;
routing here follows the DOM instead,
and the Ink rules cited below are only about how focus moves.

A component becomes focusable by calling a hook:

```python
def use_focus(auto_focus: bool = False) -> Focus: ...

@dataclass(frozen=True, slots=True)
class Focus:
    is_focused: bool
    handle: FocusHandle
```

The focusable node is the component's own node, whose element is the one the component returned,
as with `use_rects` and `use_hovered`.
Handlers on elements inside that one never see keys,
since they're descendants of the focused node rather than ancestors,
so a component that handles keys puts its handler on its top-level element.
Calling `use_focus` twice in one component raises,
since both calls would name the same node.

`handle` is an opaque `FocusHandle`, created once per component instance and compared by identity,
so a control can name the component, and it is safe to put in an effect's deps.

Focus moves only through controls, `auto_focus`, and the focused component going away:

- **`FocusNext()` and `FocusPrevious()`** move to the next or previous visible focusable node in tree order,
  wrapping at the ends; from nothing focused, they go to the first or the last.
- **`FocusOn(handle)`** focuses that component.
  It does nothing if the component has unmounted or is hidden, as a `use_state` setter does after unmount.
- **`ClearFocus()`** clears focus, so keys go to the root.
- **`auto_focus=True`** takes focus when the component mounts visible and nothing is focused.
  When several mount in the same render, the first in tree order wins (Ink's rule).
- **Unmounting or hiding the focused component clears focus**,
  and an `auto_focus` component mounted in the same render can take it.
  Ink and the browser both do this.
  Moving to the next focusable instead would send keys to a component the user never chose,
  possibly one that just shifted into the departed one's place.

No key or click has a built-in effect on focus.
An app that wants Escape to clear focus, as Ink's does, binds it to `ClearFocus()`.
One that wants a click outside every focusable to blur, as browsers do,
puts a handler on its root that returns `ClearFocus()` for a `MouseDown`:
`focus_on_press` stops every press that lands on a focusable, so the root sees only the others.

Focus is held by the render loop as a reference to the focused component's `UseFocus` hook slot,
which lives as long as the component instance does.
After each render, the warmup render included, the loop reconciles it against the new tree:
it collects the focusable slots of visible nodes in tree order,
clears focus if its slot is no longer among them, and applies `auto_focus`.
Visible means laid out this render:
`Layouts.by_key` holds only visible nodes, since waxy's `absolute_layouts` omits hidden subtrees (`layout.py:232`).
A focus change sets `is_focused` on the old and new slots and triggers a render,
the way a `use_state` setter does, so `is_focused` reads correctly in the next render.

Because the warmup render reconciles too, an `auto_focus` component present at startup
is focused on the first visible frame.
One mounted later paints a single frame with `is_focused=False` before the render its focus triggers.
Reconciling between the shadow update and painting would avoid that frame,
at the cost of a second render pass inside one cycle.

### Routing reads the last render's tree

Every event in a drained batch routes against the shadow tree from the last render.
A key that moves focus followed by a letter in the same batch delivers the letter to the newly focused node,
since focus only moves among nodes already mounted.
A key that mounts a new `auto_focus` component doesn't route the next key in its batch there,
because the component won't exist until the render; that is the same batching every state change
already has.

The routing table (each visible node's ancestor path and rects, the paint order for hit-testing,
and the focus order) is built once per render,
in a pure function over the shadow tree and the layouts, not per event.
It keys nodes by `ShadowNode.key`.
`update_shadow` builds a new `ShadowNode` for every node on the path to a component that re-ran (`shadow.py:213`),
so a node object can't name the same element from one render to the next,
but its key, which its `Hooks` carry, lasts as long as the element does and is never reused.
`ShadowTree.parents` and `Layouts.by_key` are already keyed by it.
Press capture holds a key for the same reason:
a drag re-renders on every move, and a captured node object would call the previous render's handler.
A captured key missing from the current table means the node unmounted.

### How the dependents fit

- **Text input (#391)**: the hook calls `use_focus` and returns `is_focused` for styling,
  along with one handler that composes `focus_on_press` with its own key handling,
  so an app wires a single handler.
  It returns `()` for the keys it consumes and `None` for the rest,
  so the app's shortcuts on ancestors keep working while it's focused,
  and it places the cursor on a click from the event's `relative` position.
  It no longer needs to "ignore keys while unfocused", since unfocused inputs don't receive them.
- **Scroll containers (#389)**: wheel events target the element under the pointer and bubble
  to the nearest scroll container, which handles them and stops them,
  so nested scroll containers scroll innermost-first.
  Keys reach a scroll container when it or a descendant is focused,
  and it pages by the height in the event's `rects`.
- **Elm recipe** (`plans/react-features.md` step 4): its single `on_input` on the root
  is Elm's global keyboard subscription, and receives every key no focused handler stops.
  It composes `tab_focus` in if the app wants Tab navigation.
- **Text selection (#399)**: `select_text` is a library handler like the ones above.
  It claims the press on `MouseDown`, extends the selection as press capture delivers the drag,
  and on release copies it with OSC 52, so no key binding is involved.
  An element is selectable when its handler, or an ancestor's, composes `select_text` in,
  and the guideline to attach it to the narrowest element (each message, not the transcript)
  keeps buttons and draggable elements off its path.
  Which content a selection includes is a separate question from which presses start one:
  the first version includes every text cell that isn't a border,
  and excluding other content later is a property of that content, read by the selection code.
  Skipping borders needs to know which element and box painted each cell,
  which is the paint's concern rather than routing's.

## Steps

Each step leaves the test suite passing and is a separate PR.
Each updates `docs/input-handling/events.md`, the changelog,
and every example, doc example, test, and `benchmarks/harness.py` call site it breaks.

### 1. Replace `on_key` and `on_mouse` with `on_input`

**Status:** Not started

Add the `InputEvent` type, rename the fields, and keep routing exactly as it is:
keys to every handler, mouse events to every element under the current or previous position.
`InputEvent` is `Union[KeyPressed, MouseEvent]` until step 2 adds routed events,
and handlers keep returning `AnyControl | None` until step 2 adds tuples of controls.
This is a mechanical migration that closes #124 on its own,
and keeps the routing change in step 2 reviewable without a rename mixed into it.

`examples/wordle.py` drops the fake `KeyPressed` events its mouse handlers build:
`letter_box` and the menu buttons call the shared logic directly, or share one `on_input`.
The events docs gain a recommendation for a guard clause at the top of a root handler that matches many keys,
since the root already receives every pointer move.

Tests: one `on_input` receives both a `KeyPressed` and a `MouseScrolledDown`;
the existing `tests/inputs/test_on_key.py` and `test_on_mouse.py` port to `on_input`.

### 2. Route mouse events to a target and bubble them

**Status:** Not started

Add tuple responses, the routing table, the bubbling dispatch, hit-testing, press capture,
and the routed mouse event types, with `Rects` moved to `counterweight.geometry`.
Add `counterweight.handlers` with `first`, `each`, and `on_click`,
and a `docs/input-handling/handlers.md` page for it in `mkdocs.yml`.
`Layouts.in_paint_order` carries each node's key alongside its element,
so the loop can go from a hit to an ancestor path through `ShadowTree.parents`; painting keeps taking elements.
It is renamed for tree order, which is what it holds, since `paint_layout` does the paint-order sort.
Existing handlers that return a control keep working,
and `docs/input-handling/controls.md` describes returning a tuple of controls, `()` included.
Keys keep going to every handler in this step, unrouted:
their controls are applied, and the stop is ignored until step 3.

The click handlers written by hand move to `on_click`:
`wordle.py`'s menu buttons and `text_wrap.py`'s `mode_button`.

Tests: of two overlapping absolutely positioned siblings, only the topmost receives a click;
a sibling raised with `z` receives a click over a later sibling in tree order;
an event on a child reaches its parent's handler;
`()` from the child keeps it from the parent;
a single control from the child is applied and keeps it from the parent;
a tuple of two controls applies both, in order, and stops the event;
a handler returning a list raises;
the parent's copy of a bubbled event carries the parent's rects and `is_target=False`;
`relative` is the pointer's position from the receiving element's content box;
a drag whose `MouseMoved` lands outside the element still reaches it until `MouseUp`,
including when each move re-renders the element;
after `MouseUp`, an event outside the element doesn't reach it;
if the pressed node unmounts mid-drag, later events route by position;
a `MouseDown` during a capture routes by position.
The "previous position" case in `test_on_mouse.py` is replaced by the capture tests.
The library handlers are pure, so their tests call them directly:
`first` stops at the first response that isn't `None`, `()` included, and returns `None` when none respond;
`each` calls every handler and collects their controls in order, and returns `()` when every response is `()`;
`on_click` claims the press, calls its action for a release inside the element but not outside it,
and returns the action's controls, or `()` when it returns none.

Profile a render-heavy workload with the `cw-profile` skill before and after,
since the routing table is rebuilt on every render.
Per event, walking an ancestor path costs no more than today's flat list.

### 3. Add `use_focus` and route keys to the focused node

**Status:** Not started

Add the `UseFocus` slot, the hook, `Focus`, `FocusHandle`,
and the `FocusNext`, `FocusPrevious`, `FocusOn`, and `ClearFocus` controls,
the focus order in the routing table, the focus reconciliation after each render,
and key routing through the same bubbling dispatch, with `RoutedKeyPressed`.
Every routed event, mouse events included, gains `focus_handle` and `is_focused`.
Add `tab_focus` and `focus_on_press` to `counterweight.handlers`.
Add `docs/hooks/use_focus.md` to the hooks section of `mkdocs.yml`,
the controls to `docs/input-handling/controls.md`, and the new handlers to their page.
The docs gain a note that a component's key handler goes on its top-level element,
and that a deep component's global shortcut goes on the root.

The examples that put key handlers below the root move to focus:
`stopwatch.py` drops its `selected` prop and its root's `Tab`/`Shift+Tab` bindings
for `use_focus` on each stopwatch and `tab_focus` on the root;
`end_to_end.py`'s `textpad` becomes focusable with `auto_focus=True`, so it takes focus each time it remounts,
and its root keeps swapping `textpad` and `time` on `Tab`, which has no built-in meaning;
`suspend.py`'s `picker` and `wordle.py`'s `play` use `auto_focus=True`
with their handler on the component's top-level element.

`tests/controls/test_screenshot.py`'s
`test_screenshots_requested_in_one_cycle_receive_the_same_frame` gets two screenshots into one cycle
by having two sibling handlers act on one key, which is what this step removes.
Its root handler returns both `Screenshot`s as a tuple instead.

Tests:
with nothing focused, only the root component's handler receives a key;
a key reaches the focused node, then its ancestors, and not its siblings;
the focused node's copy of a key has `is_target=True` and `is_focused=True`, and its ancestors' copies don't;
a focusable element's copy of an event carries its component's `handle` as `focus_handle`,
and a non-focusable element's carries `None`;
a click on the focused element carries `is_focused=True`;
`FocusNext()` focuses the first focusable in tree order from nothing focused, and wraps from the last;
`FocusPrevious()` moves backwards;
`FocusNext()` skips a focusable in a hidden subtree;
`FocusOn(handle)` focuses that component, and does nothing once it has unmounted;
`ClearFocus()` sends keys to the root;
`auto_focus` takes focus only when nothing is focused, and the first in tree order wins;
an `auto_focus` component present at startup is focused on the first frame;
unmounting the focused component clears focus;
hiding the focused component clears focus;
a focus change re-renders so `is_focused` is current;
`handle` is the same object across renders;
calling `use_focus` twice in one component raises;
with `tab_focus` on the root, a focused handler returning `()` for Tab keeps focus where it is;
with `focus_on_press` on nested focusables, a click focuses the innermost.
`tab_focus` and `focus_on_press` themselves are tested by calling them directly,
including `focus_on_press` raising for a `MouseDown` whose `focus_handle` is `None`.

Profile the same render-heavy workload again, since reconciliation adds a pass per render.

### 4. Focus a component from outside it

**Status:** Needs design

`FocusOn(handle)` focuses any component whose handle the caller has,
but only the component itself gets its handle from `use_focus`.
A parent that moves focus among its children (a form's "next field", a modal trapping Tab)
needs a way to get theirs, and the two shapes trade differently:

- The child passes its handle up through a callback prop.
  Nothing new is needed, but the parent learns the handle only after the child's first render.
- The parent creates a handle and passes it down, and `use_focus` accepts it, like a React ref.
  The parent has it from the start, at the cost of a second way to call `use_focus`.

No example or dependent issue needs this yet, so it waits for one.
The same goes for a way to make a component conditionally unfocusable
(Ink's `isActive`), which hooks' fixed call order requires as a parameter rather than a skipped call.

## Not in scope

- **A capture phase.** Add it when a handler needs to see events before its descendants.
- **Focus traps** (keeping Tab inside a modal). A modal does it with its own Tab handler and `FocusOn`,
  once step 4 gives it its children's handles.
