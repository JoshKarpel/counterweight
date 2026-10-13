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

- **Every key reaches every handler.** `render_loop` (`app.py:401`) calls each element's `on_key`
  in reverse tree order. Two components that both handle arrow keys both act on every arrow key,
  so apps thread "which one is active" through shared state.
  `examples/stopwatch.py` does exactly this: each `stopwatch` takes a `selected` prop
  and its `on_key` ignores keys unless it's selected.
- **Every mouse event reaches every element under the pointer.**
  `app.py:405` calls `on_mouse` on each element whose border contains the current _or previous_
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
InputEvent = Union[KeyPressed, MouseEvent]
InputResponse = Union[AnyControl, tuple[AnyControl, ...], None]
InputHandler = Callable[[InputEvent, Receiver], InputResponse]

on_input: InputHandler | None = None
```

A handler takes the event and a `Receiver`, which describes the element the event is being delivered to
(see [What a handler receives](#what-a-handler-receives)).
`InputEvent` and `InputResponse` are `Union` assignments like `MouseEvent` and `AnyEvent` in `events.py`,
rather than PEP 695 `type` statements, which `isinstance` can't take.
That keeps `InputEvent` usable with `isinstance`, but not `InputResponse`:
`isinstance(response, InputResponse)` raises `TypeError` for `None`, `()`, and anything else that isn't a control,
because the union contains the parameterized `tuple[AnyControl, ...]`,
and it passes for a control only because the check stops at the first member that matches.
Dispatch checks a response by hand instead: `None`, an `AnyControl`, or a `tuple` whose every item is an `AnyControl`.
`TerminalResized` and `StateSet` aren't in `InputEvent` and never reach a handler.
A later `Pasted` event (#391) joins the union and routes like a key.

A handler matches on the event, so one case covers both kinds of input:

```python
def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
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
The root, an ancestor of every mouse target (see [Mouse targets](#mouse-targets)),
sees every pointer move that nothing below it stops,
since the app turns on any-motion tracking (`output.py:28`).
A root handler that matches many keys can return early on any other event with a guard clause,
which the events docs should recommend.
The break is loud: constructing an element with `on_key=` raises a `TypeError`,
a handler that takes only the event fails type checking against `on_input` and raises when called,
and one whose event parameter is annotated `KeyPressed` fails type checking,
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
So a handler can't return a control and let the event keep bubbling.
Nothing in the examples or the dependents needs to:
a handler that issues a control is acting on the event, so it owns it.
If one ever does, it can call the send function from `use_send_control` (`plans/react-features.md` step 2)
and return `None`.
That hook exists for code with no response to return a control through
(effects, spawned tasks, and the Elm recipe's `dispatch`),
so routing doesn't wait on it.

Bubbling is the default, and stopping is explicit, because the opposite default is worse.
If running a handler stopped the event, every handler that matches a few keys
would need a `case _: return Propagate()`,
and forgetting it in a focused text input would swallow the app's `ctrl+c` quit binding on the root.
Under bubble-by-default, the failure is a handler that changes state without returning `()`
while an ancestor binds the same key, so both act.
That is the deliberate override case (a focused list claiming `Down` from a scrolling page),
and focus already removes the common case of two _siblings_ both acting.
The docs should recommend returning `()` (or the controls) from every case that does something.

There is no capture phase, which waits on its own design (#405):
whether it's a second handler field or a phase on the receiver, and how it meets press capture.

### What a handler receives

A handler takes two arguments: the event, unchanged from what the input parser or the autopilot produced,
and a `Receiver` describing the element the event is being delivered to:

```python
@dataclass(frozen=True, slots=True)
class Receiver:
    rects: Rects
    is_target: bool
    focus_handle: FocusHandle | None
    is_focused: bool
    subtree: Subtree

    def relative(self, position: Position) -> Position: ...
```

- `rects`: the receiving element's `Rects`, as `use_rects` returns them.
- `is_target`: whether the receiving element is the event's target, rather than an ancestor it bubbled to.
- `focus_handle`: the receiving element's `FocusHandle` if its component called `use_focus`, or `None`.
- `is_focused`: whether the receiving element is the focused node.
  For a key it's the same as `is_target`, except when nothing is focused:
  the root is then the target, and no receiver has `is_focused`.
  For a mouse event it tells a text input whether a click is the one that focuses it.
- `subtree`: an opaque `Subtree` naming the receiving element and its descendants,
  so a handler can move focus without leaving them (see [Key targets and focus](#key-targets-and-focus)).
  Every element is a shadow node with its own key, plain elements included,
  so any receiver can name its subtree, whether or not a component returned its element.
- `relative(position)`: `position` relative to the top-left of the receiving element's content box,
  as in `receiver.relative(event.absolute)` for a mouse event.
  It's computed from `rects`, so it's a method rather than a field that only mouse events would fill.

Each element on the path receives the same event with its own `Receiver`,
so a parent sees its own rects, not its child's.
`on_click` uses `rects` to tell a release inside the element from one outside,
since press capture delivers both;
`focus_receiver_on_press` uses `focus_handle` to name the element to focus;
`tab_focus` uses `subtree` to keep focus inside the element it's attached to;
a text input uses `relative` to place its cursor;
a scroll container pages by its own height.
A handler that doesn't need the receiver still takes it, and ignores it.

A case that depends on the receiver uses a guard,
since the receiver's fields aren't on the event and can't appear in its class pattern:

```python
def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
    match event:
        case MouseDown(button=1) if receiver.is_target:
            set_cursor(receiver.relative(event.absolute))
            return ()
        case _:
            return None
```

Matching on `event, receiver` as a tuple also works, and narrows the event as a plain match does.

The hooks stay, because render has no event to read:
`use_focus` declares the component focusable and gives it `is_focused` to draw a focus ring,
and `use_rects` and `use_hovered` serve layout and hover that change what renders.
The receiver repeats what the router already knows at the moment a handler runs,
so a handler needs no hook just to get data the router has,
and a component doesn't thread a hook's result into its handlers.

The alternative is to put the receiver's fields on the event.
The input parser and the autopilot produce events before anything knows where they'll go,
so that needs a routed subclass of every input event type (`RoutedMouseUp(MouseUp)`),
which the router delivers in place of the event it came from.
Handlers could still match on the base classes, since mypy narrows `case MouseUp()` to `RoutedMouseUp`
when the subject is a union of routed types,
and a routing field could appear in the class pattern.
But it's a second hierarchy kept in step with the first, growing with each event kind,
and its names surface wherever a helper extracted from a handler wants the routing fields.
A routed event wouldn't equal the raw event it came from,
so a test couldn't compare the events its handler recorded with the ones it sent.

A separate argument means a handler receives the types the autopilot sends and tests construct,
and a helper is annotated with the type it was matched as (`def drag_to(event: MouseMoved, receiver: Receiver)`).
Anything a later handler needs from the router is a new field on `Receiver`,
rather than a change to any event type or handler signature.
The cost is the second parameter on every handler, including the many that never read it,
such as `lambda event, _: Quit()`.

`Receiver` lives in `events.py`, beside `InputEvent`.
`Rects` moves from `counterweight.hooks` to `counterweight.geometry`, re-exported from `counterweight.hooks`,
and `FocusHandle` and `Subtree` are defined outside the hooks package too,
since `events.py` can't import from the hooks package, which imports `events.py`.
`Subtree` wraps a `NodeKey`, which stays in `counterweight.hooks.impls`:
its module imports it under `TYPE_CHECKING` only, as `layout.py` does,
since nothing there constructs a `NodeKey`, and annotations aren't evaluated.

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

The library handlers are pure functions from an event and a receiver to a response,
testable without running an app:

- `tab_focus` returns `FocusNext(within=receiver.subtree)` for Tab
  and `FocusPrevious(within=receiver.subtree)` for Shift+Tab,
  so Tab cycles through the focusables inside the element it's attached to.
  An app puts it on its root, whose subtree holds every focusable,
  and which is last on every key's bubble path,
  so a focused component that wants Tab (indenting in a text area) claims it with `()` first.
  A modal traps Tab by putting it on its own element too (see [Key targets and focus](#key-targets-and-focus)).
- `focus_receiver_on_press` returns `FocusOn(receiver.focus_handle)` for a `MouseDown`,
  focusing the component whose element received the press.
  It raises if `focus_handle` is `None`, which means it's attached to an element that isn't focusable:
  either the component never called `use_focus`,
  or the handler is on an inner element rather than the component's top-level one.
  It stops the event, so of nested focusables, the nearest to the pointer takes focus.
- `focus_on_press(handle)` returns `FocusOn(handle)` for a `MouseDown`,
  so a press on one element can focus another component,
  such as a label focusing the input beside it, with a handle its parent created (see below).
- `clear_focus` returns `ClearFocus()` for a `MouseDown`.
  It's how a click blurs: on the root for presses nothing below it claimed,
  and composed into a non-focusable element's own press handler for the presses it claims.
- `on_click(action)` claims a button 1 `MouseDown` and every later event of the press,
  and on the release calls `action` if the release is inside the element's border,
  returning the controls `action` returns, or `()` if it returns `None`.
  It needs no state to know the press began on its element,
  since only the node that claimed a press's `MouseDown` receives its release (see [Mouse targets](#mouse-targets)).

Two combinators compose handlers into the one an element takes:

- `first(*handlers)` calls each in turn with the same event and receiver, and returns the first response that isn't `None`, or `None`.
- `each(*handlers)` calls all of them, and if any responded with something other than `None`,
  returns a tuple of every control they returned, in handler order; otherwise it returns `None`.

The common shapes, with `select_text` from #399:

```python
# A transcript message: selectable, not focusable.
Text(content=message, on_input=select_text)

# A composer: focusable and selectable. Both handlers claim MouseDown, so each runs both.
focus = use_focus()
Div(style=ring if focus.is_focused else plain, on_input=each(focus_receiver_on_press, select_text))

# A button: focusable, not selectable.
focus = use_focus()
Text(content="Send", style=ring if focus.is_focused else plain, on_input=each(on_click(send), focus_receiver_on_press))

# The root: Tab navigation is opt-in, and its precedence over the app's own bindings is explicit.
Div(..., on_input=first(app_shortcuts, tab_focus))
```

Every library handler that acts on a press (`on_click`, `focus_receiver_on_press`, `focus_on_press`, `clear_focus`, and `select_text`)
claims its `MouseDown` rather than letting it bubble,
and the node that claims it receives the rest of the press, which bubbles no further.
So the innermost element with a press handler owns the whole press,
the same rule that makes the nearest focusable take focus,
and a press on a button can't also start an ancestor's selection or drag,
or reach an ancestor's `on_click` on release
(dragging a panel by its title bar when the press lands on the title bar's close button).
Two press handlers on one element therefore compose with `each`, as the composer and the button do,
and an ancestor's press handler never sees any event of a press on a descendant that has its own.
A text input that renders its own clear button,
and wants a click on that button to focus the input,
composes `focus_on_press(focus.handle)` into the button's handler,
using the handle from its own `use_focus`,
since the button's receiver carries the button's `focus_handle`, which is `None`:
`each(on_click(clear), focus_on_press(focus.handle))`.
That wiring is explicit and lives in user space, which is the point:
the alternative, letting presses bubble, makes a click on a button also select or drag
whenever an ancestor has a press handler, and nothing at the button's call site would show it.

The costs:

- **A missing handler fails silently.** A focusable component without `focus_receiver_on_press` just doesn't focus on click,
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

The target of a mouse event is the topmost visible element of the root component's tree
whose border rectangle contains the pointer: the last such element in paint order.
An element's margin isn't part of it, as on the web,
so a press in a margin reaches whatever lies beneath, usually the parent, even where `margin_color` paints it.
Hit-testing walks the same paint order that painting does (see [step 3](#3-scope-z-to-stacking-contexts)),
so the element drawn on top of a cell is the one a click on it reaches,
and an element raised with `z` takes clicks from a later sibling it covers.
Hidden elements have no layout, so they're never hit.
A pointer over no element of the root's tree, when the root's element is smaller than the terminal,
targets the root component's node, as a key does when nothing is focused.
The `screen` element the app wraps the root in is never a target,
so the root is an ancestor of every target and sees every pointer event nothing below it stops.
Its receiver then has `is_target=True`, and rects that don't contain the pointer.

A press runs from a `MouseDown` to its `MouseUp`.
The `MouseDown` hit-tests and bubbles like any event,
and the node whose handler claims it **captures** the press:
the press's remaining events (each `MouseMoved` with a button held, and the `MouseUp`)
go to that node as their target, wherever the pointer is,
and stop there whatever its handler returns.
This is the implicit pointer grab that X11, Win32, and DOM pointer capture all provide.
It replaces today's "current or previous position" rule,
which exists so a drag keeps reaching its element for one more event after the pointer leaves it,
but loses the drag entirely when the pointer outruns a render
(the TODO in `examples/mouse.py`'s `draggable_text`).
Wheel events aren't part of a press, so they always target the element under the pointer,
and a wheel turned mid-drag scrolls the container it's over.

The rest of a press that nothing claimed, or whose capturing node has unmounted, reaches no handler.
Routing it by hit-testing instead would hand an element the end of a press it never saw begin:
a release over a button after a press elsewhere would click it,
which browsers rule out by firing `click` only where the down and the up both landed.
So a handler that wants a press's moves claims its `MouseDown`, even with nothing to do for it.
The cost is that nothing but the capturing node sees a press's moves:
not an ancestor watching a drag a descendant claimed,
nor an element between the one the press landed on and the one that claimed it.

A release the terminal never reported (focus switched away mid-drag) mustn't leave the press stuck.
Any-motion tracking reports the held button with every move,
so a `MouseMoved` with no button held ends the press, as does a `MouseDown`,
and either one hit-tests afresh.

An element no longer sees the move that leaves it.
`use_hovered` already covers hover state from `use_mouse`, which is unchanged:
it's a broadcast of the pointer's state, not a routed event.

### Key targets and focus

The target of a key event is the **focused** node, or the root component's node when nothing is focused.
That is the node of the component passed to `app()`,
not the `screen` element the app wraps it in (`app.py:164`), which has no handler and no ancestors.
With nothing focused, handlers on the root and only the root receive keys,
though the root isn't focused, so its receiver has `is_target=True` and `is_focused=False`.
There is no broadcast fallback for apps that never call `use_focus`.
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
def use_focus(
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Focus: ...

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

`handle` is an opaque `FocusHandle` that a control uses to name the component.
It's an identity token, not a wrapper around the component's key,
so it can exist before the component it names has mounted.
`use_focus` creates one on its first run and keeps it for the component's lifetime,
unless the caller passes one in, which is how a component focuses another one it renders:

```python
@component
def labelled_input(label: str) -> Div:
    input_handle, _ = use_state(FocusHandle)
    return Div(
        children=[
            Text(content=label, on_input=focus_on_press(input_handle)),
            text_input(focus_handle=input_handle),
        ],
    )
```

The parent has the handle from its first render, and passes it down like any other prop,
so a child that can be focused from outside takes a `FocusHandle | None` parameter
and forwards it to `use_focus`.
A handle is safe to put in an effect's deps, since it never changes for a mounted component:
`use_focus` raises if the handle passed to it differs from the one it was given on its first run,
which catches a parent that builds a `FocusHandle()` inline on every render
instead of keeping one in `use_state`.
Two mounted components given the same handle also raise, when the routing table is built,
as sibling components that share a key do (`DuplicateKey`).
Ink names focusables with a string `id` that must be unique among them,
which is a namespace that two unrelated components can collide in;
a token is unique by construction, and only code it was handed can name it.

Two parameters take a mounted, visible component partly or wholly out of focus,
each mirroring a browser attribute:

- **`is_focusable=False`** makes it unfocusable, as `disabled` does,
  for a field that's disabled until another is filled in (Ink's `isActive`).
  Nothing can focus it, and if it's focused, it loses focus.
  An unfocusable component still receives the mouse events routed to it,
  so its press handler still claims a press, and the `FocusOn` that `focus_receiver_on_press` returns does nothing.
- **`in_focus_order=False`** takes it out of the focus order only, as `tabindex="-1"` does,
  for a component that should take focus when clicked or named, but isn't a Tab stop,
  such as a read-only panel whose keys scroll it.
  `FocusNext` and `FocusPrevious` skip it, while `FocusOn`, `auto_focus`, and a press still focus it,
  and it keeps focus once it has it.

Either way, the component keeps its handle and its place in tree order,
so it returns to the focus order where it was when the parameter flips back.
`in_focus_order` only matters for a focusable component,
since an unfocusable one is out of the focus order already.
They're parameters rather than a skipped `use_focus` call,
because hooks' fixed call order doesn't allow a conditional call,
and because a component that stopped calling `use_focus` would lose its handle.

Focus moves only through controls, `auto_focus`, and the focused component going away:

- **`FocusNext(within)` and `FocusPrevious(within)`** move to the next or previous visible node in the focus order,
  in tree order inside the `Subtree` `within`, wrapping at its ends;
  from nothing focused, or from focus outside the subtree, they go to its first or its last.
  From a focused component that's out of the focus order, they move from its place in tree order,
  as browsers do from a focused `tabindex="-1"` element.
  `within` defaults to `None`, meaning the whole tree, for code with no receiver to name a subtree from
  (an effect sending a control through `use_send_control`).
  They do nothing if the subtree has unmounted or holds no visible node in the focus order.
- **`FocusOn(handle)`** focuses that component.
  It does nothing if the component hasn't mounted yet, has unmounted, is hidden, or is unfocusable,
  as a `use_state` setter does after unmount.
- **`ClearFocus()`** clears focus, so keys go to the root, which isn't focused.
- **`auto_focus=True`** takes focus when the component mounts visible and focusable and nothing is focused.
  When several mount in the same render, the first in tree order wins (Ink's rule).
  A component that mounts unfocusable doesn't take focus when it becomes focusable later.
- **Unmounting, hiding, or making the focused component unfocusable clears focus**,
  and an `auto_focus` component mounted in the same render can take it.
  Ink does this for all three, and the browser does it for unmounted, hidden, and disabled elements.
  Moving to the next focusable instead would send keys to a component the user never chose,
  possibly one that just shifted into the departed one's place.
  Making a component focusable again doesn't focus it.

No key or click has a built-in effect on focus.
An app that wants Escape to clear focus, as Ink's does, binds it to `ClearFocus()`.
One that wants a click outside every focusable to blur, as browsers do,
puts `clear_focus` on its root,
which sees only the presses nothing below it claimed.
`focus_receiver_on_press` claims every press that lands on a focusable, which is the point,
but `on_click` and `select_text` claim presses on non-focusable elements too,
so a click on a non-focusable button or a selectable message would keep focus where it was.
Each of those elements composes `clear_focus` in alongside its press handler
(`each(on_click(send), clear_focus)`), which keeps the blur visible at the call site
of every element that causes it.

Scoped movement is what a group of focusables needs to steer focus among its own members,
without holding a handle for each:

- A form moves to its next field on Enter
  by returning `FocusNext(within=receiver.subtree)` from its top-level element's handler,
  which the focused field's Enter bubbles to.
- A modal traps Tab by putting `tab_focus` on its top-level element.
  Tab from a focused field inside it bubbles to the modal before the root,
  and cycles only through the modal's focusables.
  The handler that opens the modal returns `ClearFocus()` alongside its state change,
  and the modal's first field uses `auto_focus=True`,
  so it takes focus in the render that mounts the modal, since nothing is focused then.
  Returning focus to the opener when the modal closes is a `FocusOn`
  with a handle that the component rendering both creates and passes to each.

Scoping keeps Tab inside a modal, but nothing else is blocked:
a click behind the modal still lands,
and if focus clears while the modal is open (its focused field unmounts),
keys go to the root, whose `tab_focus` can move focus behind the modal.
Making the content behind a modal inert is out of scope.

Focus is held by the render loop as the focused node's `NodeKey`, or `None`,
the same identity press capture and the routing table use (see below).
A focused key missing from the current routing table's focusable keys
means the component unmounted, is hidden, or is unfocusable.
The routing table maps each visible focusable's `FocusHandle` to its key,
so `FocusOn(handle)` resolves its handle there, and a miss means there's nothing to focus.
The check for a handle shared by two components covers unfocusable ones too.
A `Subtree` wraps its element's `NodeKey`,
and scoped movement keeps the focusables that are that node or have it on their ancestor path in the table.
The `UseFocus` slot records only that the component called `use_focus`, and the arguments it passed;
it doesn't store whether the component is focused.
`use_focus` reads that during render by comparing its own key with the focused key,
which `update_shadow` takes as an input the way it takes `layouts`.
After each render, the warmup render included, the loop reconciles focus against the new routing table:
it clears focus if the focused key isn't among the table's focusable keys, and applies `auto_focus`.
The table's focusable keys are the visible nodes whose last run called `use_focus` with `is_focusable=True`,
in tree order, each marked with its `in_focus_order`.
The focus order is the marked ones;
movement keeps the others in the list so it can start from a focused one's place.
Visible means laid out this render:
`Layouts.by_key` holds only visible nodes, since waxy's `absolute_layouts` omits hidden subtrees (`layout.py:232`).
A focus change adds the old and new keys to `dirty` and triggers a render,
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
the focus order, and each focusable's key by its handle) is built once per render,
in a pure function over the shadow tree and the layouts, not per event.
It keys nodes by `ShadowNode.key`.
`update_shadow` builds a new `ShadowNode` for every node on the path to a component that re-ran (`shadow.py:222`),
so a node object can't name the same element from one render to the next,
but its key, which its `Hooks` carry, lasts as long as the element does and is never reused.
`ShadowTree.parents` and `Layouts.by_key` are already keyed by it.
Press capture holds a key for the same reason:
a drag re-renders on every move, and a captured node object would call the previous render's handler.
A captured key missing from the current table means the node unmounted.

### How the dependents fit

- **Text input (#391)**: the hook calls `use_focus` and returns `is_focused` for styling,
  along with one handler that composes `focus_receiver_on_press` with its own key handling,
  so an app wires a single handler.
  It returns `()` for the keys it consumes and `None` for the rest,
  so the app's shortcuts on ancestors keep working while it's focused,
  and it places the cursor on a click at `receiver.relative(event.absolute)`.
  It no longer needs to "ignore keys while unfocused", since unfocused inputs don't receive them.
- **Scroll containers (#389)**: wheel events target the element under the pointer and bubble
  to the nearest scroll container, which handles them and stops them,
  so nested scroll containers scroll innermost-first.
  Keys reach a scroll container when it or a descendant is focused,
  and it pages by the height in its receiver's `rects`.
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
and every example, doc example, benchmark workload, and test it breaks,
including the code blocks written inline in the docs' Markdown, which no build or test runs.

### 1. Replace `on_key` and `on_mouse` with `on_input`

**Status:** Done

Add `InputEvent`, `InputHandler`, and `Receiver`, rename the fields, and keep routing exactly as it is:
keys to every handler, mouse events to every element under the current or previous position.
`Receiver` has only `rects` and `relative` in this step,
built from the resolved layout the dispatch loop already pairs with each element (`app.py:401`),
with `Rects` moved to `counterweight.geometry`.
Steps 4 and 5 add its other fields, which changes no handler's signature.
Handlers keep returning `AnyControl | None` until step 4 adds tuples of controls.
This is a mechanical migration that closes #124 on its own,
and keeps the routing change in step 4 reviewable without a rename mixed into it.

`examples/wordle.py` drops the fake `KeyPressed` events its mouse handlers build:
`letter_box` and the menu buttons call the shared logic directly, or share one `on_input`.
`grep -rn 'on_key\|on_mouse' docs` finds the inline snippets and prose the rename breaks,
such as `docs/hooks/use_mouse.md`'s comparison with `on_mouse`
and the `use_memo`-wrapped handlers in `docs/performance.md`, which gain the receiver parameter.
The events docs gain a recommendation for a guard clause at the top of a root handler that matches many keys,
since the root already receives every pointer move.

Tests: one `on_input` receives both a `KeyPressed` and a `MouseScrolledDown`;
the receiver carries the element's rects;
`Receiver.relative` gives a position relative to the content box's top-left;
the existing `tests/inputs/test_on_key.py` and `test_on_mouse.py` port to `on_input`.

### 2. Paint margins only where they're colored

**Status:** Done

`paint_element` fills an element's whole margin box with its background (`paint.py:274`),
and its margin strips with `margin_color`, which resolves to black when unset,
so every element with a margin erases what lies beneath that margin.
That's harmless in flow, where siblings' margins don't overlap,
but an absolutely positioned box with `auto` margins erases its whole parent.
Instead, the background fills the border box,
and the margin strips paint only when the element's own style sets `margin_color`,
read from the unresolved style as `content_color` already is (`paint.py:271`).
A margin paints nothing on the web, where backgrounds stop at the border box;
`margin_color` keeps its use for showing the box model.

With margins transparent, a box centers itself over its parent the way CSS does,
with insets of 0, `auto` margins, and a fit-content size:

```python
dialog = position_absolute | inset(0) | margin_auto | fit_content_width | fit_content_height
```

A probe with waxy 0.7.0 lays this out centered in a `col` parent that doesn't center its children,
at the dialog's own size; it's today's paint that blanks the rest of the parent.
The layering docs' dialog recipe becomes this,
replacing the full-parent overlay `Div` it wraps the dialog in today.
That overlay is a box the size of the parent, there only so that ordinary alignment can center the dialog,
and it would be the topmost element under every cell of the parent,
taking every click once hit-testing arrives in step 4.
The dialog's own box covers only the dialog, so hit-testing needs no way to make an element click-through.

Add `inset(n)`, `inset_x(n)`, and `inset_y(n)`, which set all four, the left and right, and the top and bottom insets,
alongside `margin(n)` and `pad(n)`;
`inset_sides(top, right, bottom, left)`, `margin_sides`, and `pad_sides`, which set each side separately,
in the order of CSS's four-value shorthands;
and `auto` margins for each side and each pair of sides as `margin_auto`, `margin_x_auto`, `margin_top_auto`, and so on.
Each goes in `docs/styles/utilities.md`'s markers.

Tests: a margin without `margin_color` leaves what lies beneath it visible;
a margin with `margin_color` paints it;
a content color fills the border box, not the margin box;
the dialog recipe centers a box in a parent that doesn't center its children,
and leaves the parent's other children visible around it.

### 3. Scope `z` to stacking contexts

**Status:** Done

`paint_layout` orders every element in one flat sort by `(z, order)` (`paint.py:195`),
so a `z(1)` element paints after its own children, whose `z` defaults to 0,
and a content color on it covers them entirely.

Instead, `z` follows CSS's stacking contexts.
An element whose style sets `z`, `z(0)` included, forms a **stacking context**:
it and its descendants paint as a unit at its `z`, and its descendants' `z` orders them only within it.
An element that doesn't set `z` forms none,
so its descendants join the nearest context above it, alongside it.
Each context paints its own element first,
then its members in a stable sort by `(z, order)`, where a member that doesn't set `z` counts as 0,
and a member that forms a context paints its whole context in its place.
The root forms a context whatever it sets.
CSS's `z-index` forms a context only on a positioned element or a flex or grid item,
which every Counterweight element is.

So a `z(1)` dropdown inside a toolbar that sets no `z` paints over the content below the toolbar,
while the same dropdown inside a toolbar that sets `z(0)` paints only over the toolbar's own content,
beneath the toolbar's later siblings.
A `z(-1)` member paints after its context's own element, so over that element's background, as in CSS,
where the flat sort puts it before every element today.

The resolved style keeps whether `z` was set, which `resolve_style` drops today (`styles.py:741`),
so `ResolvedStyle.z` becomes `int | None`.
`LayoutTree.compute` builds the order from the shadow tree,
so `Layouts.in_paint_order` holds paint order, as its name says, and `paint_layout` drops its sort.
Hit-testing in step 4 walks the same tuple, so a click reaches whatever is drawn on top.

The rule is harder to state than "`z` orders siblings", so the layering docs show it with the dropdown,
once escaping a toolbar without `z` and once scoped by a toolbar with `z(0)`.
The changelog lists the change in paint order for apps that set `z` on nested elements, or a negative `z`.

Clipping is by ancestry, not stacking order:
a clipping container (#388) cuts off a dropdown inside it however high its `z`, as on the web.
Since an absolutely positioned box's containing block is always its parent here,
a popup can't escape a clip by being positioned against an ancestor outside it, as it can on the web,
so it has to render outside the clipping container.

Tests: a `z(1)` element's children paint over it, including children with a content color of their own;
a child with a lower `z` than its parent that sets `z` still paints over it;
a `z(1)` child of an element without `z` paints over that element's later siblings;
a `z(1)` child of a `z(0)` element paints beneath that element's later siblings;
a `z(-1)` member paints over its context's element and beneath the context's other members.
The `z.py` and layering screenshots are regenerated and checked for changes.

### 4. Route mouse events to a target and bubble them

**Status:** Not started

Add tuple responses, the routing table, the bubbling dispatch, hit-testing, press capture,
and `Receiver.is_target`.
Add `counterweight.handlers` with `first`, `each`, and `on_click`,
and a `docs/input-handling/handlers.md` page for it in `mkdocs.yml`.
`Layouts.in_paint_order` carries each node's key alongside its element,
so the loop can go from a hit to an ancestor path through `ShadowTree.parents`; painting keeps taking elements.
Existing handlers that return a control keep working,
and `docs/input-handling/controls.md` describes returning a tuple of controls, `()` included.
Keys keep going to every handler in this step, unrouted, each with `is_target=True`:
their controls are applied, and the stop is ignored until step 5.

The click handlers written by hand move to `on_click`:
`wordle.py`'s menu buttons and `text_wrap.py`'s `mode_button`.
`examples/mouse.py`'s `last_dragged_box` returns `()` for the `MouseDown` it already handles,
and `draggable_text` gains a case that claims its `MouseDown`,
since otherwise the moves of their drags reach no handler.

Tests: of two overlapping absolutely positioned siblings, only the topmost receives a click;
a sibling raised with `z` receives a click over a later sibling in tree order;
a child of an element raised with `z` receives a click over its parent;
a click outside the root component's element, when that element is smaller than the terminal,
targets the root's node, with `is_target=True`;
an event on a child reaches its parent's handler;
`()` from the child keeps it from the parent;
a single control from the child is applied and keeps it from the parent;
a tuple of two controls applies both, in order, and stops the event;
a handler returning a list raises, and so does one returning a tuple containing something that isn't a control;
the parent receives the same event as the child, with a receiver carrying the parent's rects and `is_target=False`;
a drag whose `MouseMoved` lands outside the element still reaches it until `MouseUp`,
including when each move re-renders the element;
after `MouseUp`, an event outside the element doesn't reach it;
the rest of a press goes to the node that claimed its `MouseDown`, with `is_target=True`,
and not to a descendant it landed on or to the claimer's ancestors, whatever the claimer's handler returns;
the held moves and release of a press nothing claimed reach no handler,
so a release over an `on_click` element after an unclaimed press elsewhere doesn't call its action;
if the capturing node unmounts mid-press, the rest of the press reaches no handler;
a wheel event during a capture routes by position, and the capture continues;
a `MouseDown` during a capture routes by position;
a `MouseMoved` with no button held during a capture routes by position and ends the capture.
The "previous position" case in `tests/inputs/test_on_input.py` is replaced by the capture tests.
The library handlers are pure, so their tests call them directly:
`first` stops at the first response that isn't `None`, `()` included, and returns `None` when none respond;
`each` calls every handler and collects their controls in order, and returns `()` when every response is `()`;
`on_click` claims the press, calls its action for a release inside the element but not outside it,
and returns the action's controls, or `()` when it returns none.

Profile a render-heavy workload with the `cw-profile` skill before and after,
since the routing table is rebuilt on every render.
Per event, walking an ancestor path costs no more than today's flat list.

### 5. Add `use_focus` and route keys to the focused node

**Status:** Not started

Add the `UseFocus` slot, the hook with its `handle`, `is_focusable`, and `in_focus_order` parameters,
the focused key as an input to `update_shadow`, `Focus`, `FocusHandle`, `Subtree`,
and the `FocusNext`, `FocusPrevious`, `FocusOn`, and `ClearFocus` controls,
the focus order and the handle-to-key map in the routing table, the focus reconciliation after each render,
and key routing through the same bubbling dispatch.
`Receiver` gains `focus_handle`, `is_focused`, and `subtree`, for mouse events as well as keys.
Add `tab_focus`, `focus_receiver_on_press`, `focus_on_press`, and `clear_focus` to `counterweight.handlers`.
Add `docs/hooks/use_focus.md` to the hooks section of `mkdocs.yml`,
the controls to `docs/input-handling/controls.md`, and the new handlers to their page.
The docs gain a note that a component's key handler goes on its top-level element,
and that a deep component's global shortcut goes on the root.
Inline snippets whose key handler sits below the root stop receiving keys without failing anything:
`docs/hooks/use_ref.md`'s `line_entry` and `docs/performance.md`'s `key_log` call `use_focus(auto_focus=True)`.
`docs/ecosystem.md` drops focus from its list of gaps.

`docs/examples/focus_form.py` is the `use_focus` page's example, and exercises every way focus moves.
It's an order form whose fields are focusable components that take keys rather than text,
since the text input is #391's:
a size cycled with Left and Right, a quantity stepped with Up and Down, a gift wrap toggle flipped with Space,
and a wrapping paper cycled with Left and Right, which is drawn dimmed and passes `is_focusable=False`
while gift wrap is off.
Below the fields, a help panel pages through tips with Left and Right,
and passes `in_focus_order=False` with `focus_receiver_on_press`, so a press focuses it but Enter and Tab never stop on it.
The first field uses `auto_focus=True`.
The form's element returns `FocusNext(within=receiver.subtree)` for Enter,
and each field's label focuses it with `focus_on_press` and a handle the form keeps in `use_state(FocusHandle)`.
The submit button claims Enter for itself and opens a confirmation modal,
returning `ClearFocus()` so the modal's auto-focused Cancel button takes focus.
The modal is positioned with step 2's dialog recipe, so a press beside it reaches the form,
and traps Tab with `tab_focus` on its element,
and Enter on Cancel closes it, returning focus to the submit button through a handle the form passes to both.
Its `SCREENSHOTS` show the first field focused at startup, the second after Enter,
gift wrap after a press on its label,
the submit button after Enter skips the unfocusable wrapping paper and the help panel,
the modal open with Cancel focused after another Enter,
focus wrapped back to Cancel after two Tabs, still inside the modal,
the submit button focused again after Enter on Cancel closes the modal,
and the help panel focused after a press on it, showing its second tip after Right.

The examples that put key handlers below the root move to focus:
`stopwatch.py` drops its `selected` prop and its root's `Tab`/`Shift+Tab` bindings
for `use_focus(auto_focus=True)` on each stopwatch, styled by `is_focused`, and `tab_focus` on the root,
so the first stopwatch is focused at startup, as it's selected today,
and its help text says "focused" where it says "selected";
`end_to_end.py`'s `textpad` becomes focusable with `auto_focus=True`, so it takes focus each time it remounts,
and its root keeps swapping `textpad` and `time` on `Tab`, which has no built-in meaning;
`suspend.py`'s `picker` uses `auto_focus=True`;
`wordle.py`'s `play` does too, and moves its key handler from the guess rows' Div (`wordle.py:205`)
to its top-level Div, which keys reach.
So do two that a broken example wouldn't reveal:
`docs/examples/performance_process_table.py`'s `process_table`,
whose screenshot's `Down` would otherwise stop moving the selection,
and `benchmarks/dashboard_local.py`'s `key_frame_counter`,
which would otherwise stop counting frames and diverge from `dashboard`'s last frame.
The counter keeps falling through to `None`, so each key still bubbles to the root that times it.

`tests/controls/test_screenshot.py`'s
`test_screenshots_requested_in_one_cycle_receive_the_same_frame` gets two screenshots into one cycle
by having two sibling handlers act on one key, which is what this step removes.
Its root handler returns both `Screenshot`s as a tuple instead.

Tests:
with nothing focused, only the root component's handler receives a key,
and its receiver has `is_target=True` and `is_focused=False`;
a key reaches the focused node, then its ancestors, and not its siblings;
the focused node's receiver has `is_target=True` and `is_focused=True`, and its ancestors' receivers don't;
a focusable element's receiver carries its component's `handle` as `focus_handle`,
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
with `focus_receiver_on_press` on nested focusables, a click focuses the innermost.
Scoped movement:
`FocusNext(within=...)` and `FocusPrevious(within=...)` move only among the focusables in the subtree,
and wrap at its ends;
from focus outside the subtree, they go to its first or last focusable;
a subtree whose element is itself focusable includes it;
a scoped move does nothing for a subtree that has unmounted or holds no visible node in the focus order;
with `tab_focus` on both the root and an element below it, Tab from a focusable inside that element
cycles within it, and Tab from one outside it moves through the whole tree;
a parent and child on one bubble path receive different `subtree`s, each naming its own element.
Parent-created handles:
`FocusOn(handle)` focuses a child given that handle, including from the parent's first render;
`FocusOn(handle)` does nothing for a handle no mounted component was given;
`use_focus` returns the handle it was given as `Focus.handle`;
passing a different handle on a later render raises;
two mounted components given one handle raise, including when one is unfocusable.
Unfocusable components:
`FocusNext()` and `FocusPrevious()` skip an unfocusable component;
`FocusOn(handle)` does nothing for an unfocusable component;
`auto_focus` doesn't focus a component that mounts unfocusable, nor when it becomes focusable later;
making the focused component unfocusable clears focus;
making a component focusable again returns it to its place in the focus order without focusing it;
a component keeps its handle across the change;
a press on an unfocusable component with `focus_receiver_on_press` is claimed and leaves focus where it was.
Components out of the focus order:
`FocusNext()` and `FocusPrevious()` skip a component with `in_focus_order=False`;
`FocusOn(handle)`, `auto_focus`, and a press with `focus_receiver_on_press` each focus it;
taking the focused component out of the focus order leaves it focused;
from a focused component out of the focus order, `FocusNext()` and `FocusPrevious()` move to its neighbors in tree order;
`in_focus_order=False` changes nothing for an unfocusable component.
The library handlers themselves are tested by calling them directly,
including `focus_receiver_on_press` raising for a `MouseDown` whose receiver's `focus_handle` is `None`,
`focus_on_press(handle)` focusing `handle` whatever the receiver's `focus_handle`,
and `clear_focus` returning `ClearFocus()` for a `MouseDown` and `None` for anything else.

Profile the same render-heavy workload again, since reconciliation adds a pass per render.

## Not in scope

- **A capture phase** (#405), which has several plausible API shapes and an interaction with press capture to design.
- **Inert content behind a modal.** Scoped `tab_focus` keeps Tab inside a modal,
  but clicks and focus recovery can still reach what's behind it.
