# Plan: Parts for Pickers and Comboboxes

Artifact: https://claude.ai/code/artifact/ad723da1-a0f8-4971-a221-f0be22e0bbe9

This plan adds the parts every counterweight picker has written its own copy of,
and leaves wiring them to keys, state and drawing to the app.
It adds `Highlight`, `fuzzy_matches` and `substring_matches` to `counterweight.headless`,
a return value to `use_state`'s setter, the state it settled at,
so a handler can read the state as the updates since the last render left it,
and `combobox`, a widget that wires the parts the one way the WAI-ARIA combobox pattern does.
Everything else a picker does (an always-open list, Tab cycling, marks, keys of its own, previews)
is a recipe in the docs, built from the parts.
It rebuilds the cookbook's autocomplete and picker snippets on the parts,
and ends with every picker built on counterweight so far ported onto them.
It doesn't add a hook that wires the parts together (see [Why no wired hook](#why-no-wired-hook)),
choosing several options as a library feature, loading options asynchronously,
or a list you choose from without typing (a `<select>`), which `Highlight` serves when it comes.

## The question

Every counterweight app with a picker has written its own, and the copies have started to drift.
What part of them is behavior that belongs in the library,
and what part is drawing, or keys, or policy, that each app does its own way?

Ten copies exist, in two families.

The cookbook family copies the cookbook's autocomplete and builds on `use_text_input`:
the cookbook's `autocomplete.py` and `picker.py`, the inline apps page's `inline_picker.py`,
whats-new's `components/picker.py`,
and assess's `theme_picker.py` and `file_picker.py`'s `filter_list`.
These parts recur across them, nearly line for line:

- `matches`: the typed letters in order with anything between them, case folded, glob-escaped, the exact name first.
- A state of the typed text and the highlighted match's index (`Completion`, `Query`),
  whose `edited` resets the highlight to the first match when the text changes.
- A handler where Down and Up move the highlight, wrapping; Enter, and in three of them Tab, chooses;
  Escape closes; and every other event goes to `use_text_input`'s handler,
  with `ScrollIntoView(highlighted_row, block="nearest")` added to whatever it returns.
- An `ElementHandle` given to the highlighted row, and `on_click` on each row to choose it.
- In the four pickers, a `FocusHandle` passed in, so whatever opens one can focus it in the frame it opens in.

The command-line family is four scripts in the dotfiles, `wt`, `kube-pick`, `port-manage` and `zellij-pick-tab`,
which hand-roll the query instead of using `use_text_input`, and run every key through a pure `step`
applied to the latest state. They share:

- Substring matching with `casefold`, not fuzzy matching.
- Tab, Ctrl+N, Down to move down, and Shift+Tab, Ctrl+P, Ctrl+K, Up to move up; Ctrl+U clears the query.
- Ctrl+J choosing as Enter does, because a tty still in cooked mode turns an Enter typed ahead into a line feed.
- Keys typed ahead, before the first frame or between frames, landing as if each had been seen,
  which `wt`'s self-tests pin.

Beyond those, single copies need more:

- `port-manage` refreshes its rows every second, and holds the highlight by its row's key and by its position:
  the key keeps it on its port as rows above come and go, and the position is where it lands when its own row goes.
  Its self-test "the highlight stays on its port as a row above it appears" fails with an index alone.
  Enter copies a URL and Ctrl+X signals a process, both without closing.
- `wt` lists rows under headings the highlight skips, and its cleanup picker marks several worktrees:
  marks kept apart from the highlight, rows that can't be marked, Space to mark (branch names can't hold spaces),
  marks the query hides still counting, and Enter acting on the marks, doing nothing when there are none.
  Escape goes back a step in its two-step flow.
- `zellij-pick-tab`'s digits jump to a tab, where `port-manage`'s and `kube-pick`'s narrow the list.
- `zellij-pick-tab` and `kube-pick` open on the current item, and draw it differently.

## Where the drift lives

Sorting the drift by where it lives answers the question:

| Drift | Kind | Where it lives |
|---|---|---|
| `shown[query.highlighted]` indexes past the end when the options shrink and the text stays (`filter_list`) | Bug | Which option is highlighted |
| `port-manage` needs the highlight held by key as rows refresh | Bug, fixed in one copy | Which option is highlighted |
| An Enter typed with the text before it chooses from the list as last rendered | Bug | Reading the latest state in a handler |
| `matches` copied nearly line for line | Duplication | Matching |
| Tab chooses (cookbook), moves (command-line family), or does nothing (assess) | Preference | Keys |
| `inline_picker.py` stops at the ends rather than wrapping | Preference | Keys |
| Escape closes, goes back a step, or leaves the app | Preference | What a key does |
| Choosing fills in text, sets a setting, jumps, copies, or signals | Preference | What choosing does |
| assess's theme picker keeps its state in the app, to preview the highlighted theme | Preference | Who owns the state |

The bugs are the same mistake made in each copy, in a part that is the same everywhere.
The differences are callers wanting different things, in the wiring.
A hook that wires the parts together fixes the first kind only by taking ownership of the second,
which is why the design this plan replaced grew a parameter for each wiring choice a caller made differently:
a key map, an `on_dismiss` that always-open pickers opted out of, an `is_dismissed` they carried and never drew,
and four focus parameters passed through to the text field it owned.

## How the web does it

The [WAI-ARIA combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/) defines the widget:
"A combobox is an input widget that has an associated popup",
and "the popup is hidden by default".
Focus stays in the text box, the highlighted option is marked with `aria-activedescendant`,
Down opens a closed popup, Escape closes an open one,
Tab moves focus on, and Home and End belong to the text box, not the list.
Options can be `aria-disabled`, which the highlight skips.
`aria-autocomplete` says how the suggestions relate to the text (`list`, `inline`, `both`),
so autocompletion is a property a combobox has, not a widget of its own.
Completion with no popup, as bash's Tab cycling or fish's ghost text, is outside the pattern.

The headless libraries name the pieces differently, and agree on taking them apart:

- [React Aria's `Autocomplete`](https://react-aria.adobe.com/Autocomplete) "filters a collection component
  using a TextField or SearchField", where the collection is a separate component
  (`Menu`, `ListBox`, `GridList`, `Table`), drawn inline or in a popover;
  its `ComboBox` is for selecting "values from a pre-defined set of options".
- [Base UI's `Autocomplete`](https://base-ui.com/react/components/autocomplete) is a text field with suggestions
  whose value is free text, and its `Combobox` is for "when selection state is needed".
- [Headless UI's `Combobox`](https://headlessui.com/v1/react/combobox)
  and [Downshift's `useCombobox`](https://github.com/downshift-js/downshift/tree/master/src/hooks/useCombobox)
  take the options already filtered, and leave the filter to the app.
- React Aria tracks the highlighted option by its key (`focusedKey`), so it stays on the same option
  when the list changes; Downshift tracks an index.
  Downshift takes `isItemDisabled`, and React Aria `disabledKeys`.
- Downshift's `stateReducer` lets an app rewrite what any key does to the state,
  which is what an app writing its own handler from the parts does directly.

On reading the latest state in a handler:

- React renders between discrete events:
  "React ensures that for each user-initiated event like a click or a keypress,
  the DOM is fully updated before the next event"
  ([React 18's automatic batching](https://github.com/reactwg/react-18/discussions/21)),
  so a handler sees the state the last key left.
- ahooks' [`useGetState`](https://github.com/alibaba/hooks/blob/master/packages/hooks/src/useGetState/index.ts)
  returns `[state, setState, getState]`, where `getState` reads a ref each render refreshes,
  which sees only the last render; that's enough in React, since it renders between keys.
- React's [`useEffectEvent`](https://react.dev/reference/react/useEffectEvent) "always accesses the latest
  committed values from render", and may not be called "during rendering".
- Solid's `createSignal` returns a getter instead of a value, since its components run once rather than re-render.

Where counterweight differs:

- Several keys can arrive before the next render, as when typing fast or typing before the first frame,
  and each runs a handler the last render made.
  A handler that decides from the values it rendered with decides from stale state,
  and a getter that reads a copy refreshed each render, as ahooks' does, is just as stale.
  `use_state`'s setter applies an updater immediately, so the state itself is current,
  and the setter returns it.
- There's no `aria-activedescendant`, but the same idea applies.
  The highlighted row gets an `ElementHandle`, and `ScrollIntoView` brings it into view.
- There's no anchor positioning, so a popup can't flip itself above its field when it would overflow;
  the cookbook measures the room with `use_rects` and the screen's height.
- Terminal users expect readline's and fzf's keys (Ctrl+N, Ctrl+P, Tab to move) where a browser has none,
  which is one more reason the keys stay the app's.

## The spike

The parts were tried by porting two dissimilar callers onto them:
the cookbook's `picker.py`, which keeps its state in `use_state` and edits with `use_text_input`,
and `port-manage`, which runs every key through a pure `step` inside its state's updater
and edits its query by hand.

- Both took `Highlight` and the matchers unchanged.
  A wired hook could not have taken `port-manage` without rewriting it to the hook's shape.
- `port-manage`'s self-tests pass unchanged on the parts,
  and breaking `Highlight`'s lookup by key fails "the highlight stays on its port as a row above it appears".
  The port deletes more lines than it adds.
- The picker's stills are byte-identical, and it opens on its current option by key rather than by `names.index`.
- What wiring is left shares almost nothing between the two: the keys, what choosing does,
  who owns the state and how the text is edited all differ.
  The overlap is `edited` (a changed text puts the highlight on the first match), a few lines in each.
- The one subtle piece the picker needed beyond the parts was reading the latest state in its Enter handler.
  The spike read it by passing the setter an identity updater that copied out the value it was given,
  which works because the setter applies updaters immediately;
  the setter returning the state makes that read the identity updater alone.
  On a real pseudo-terminal, writing `pypy` and Enter in one write, the picker before the port kept 3.15,
  choosing from the list as last rendered, and the port chose `pypy3.11`.
  `port-manage` avoids the problem by doing everything inside the updater,
  and pays with a queue of pending actions and the effect that carries them out.

Not yet exercised: options the highlight skips (`wt`'s headings), highlighting a row on hover,
and stopping at the ends (`inline_picker.py`).

## Decisions

| Question | Choice | What it costs |
|---|---|---|
| A hook that wires the parts, or the parts | The parts, with one widget and recipes; a hook waits for callers' wiring to converge | Each picker writes its own handler, a screenful, and its keys keep varying |
| Who filters | The caller, with `fuzzy_matches` and `substring_matches` exported for it | Every caller writes the line that filters |
| Highlight by index or by option | `Highlight` holds both: the option's key, and its index, which is where it lands when its option goes | Options need a key that isn't `None`, and each of `Highlight`'s methods takes the `key` function |
| Rows the highlight skips | An `is_disabled` predicate on `Highlight`'s methods, as Downshift's `isItemDisabled` | One more parameter on each method |
| Reading the latest state in a handler | `use_state`'s setter returns the state it settled at, so an identity updater reads it | Reading is a write that changes nothing; a parameter written out as `Callable[..., None]` rather than `Setter[T]` stops accepting a setter |
| Rendering between events, as React does | No: a handler reads where a decision needs the latest state (see [Why not render between events](#why-not-render-between-events)) | A handler that decides from what it rendered with decides from stale state when keys arrive before a render |
| Which keys do what | The app's handler, for every caller but the widget | No key map to share; the command-line family's scripts each spell out the same keys |
| Popup open and dismissed | The widget's own state, and a recipe for apps that build their own | Each popup picker writes the few lines of Escape and reopening |
| What the widget is called | `combobox`, the APG pattern it implements | none; there's no hook to name, so the always-open list needs no name either |
| Several options | A recipe, composed on top (see [Marking several options](#marking-several-options)) | Each multi-select picker keeps its own marks and its own mark key |

### Why no wired hook

A hook that wires the parts fixes the bugs by owning the wiring, and every caller wires differently,
so each difference becomes a parameter, and a caller that wires the way the hook didn't expect
(`port-manage`'s `step`) can't use it at all.
The parts fix the same bugs and leave the wiring where it varies.
If the ports in [Steps](#steps) find the same subtle lines in several callers' wiring, those lines are the hook,
found from the code rather than designed ahead of it.

### Why handlers read the latest state

An updater computes the next state from the latest one, so a handler that only moves state along needs no read:
the cookbook picker's Down and Up, and every edit, are updaters.
What an updater can't hand back is the rest of what a handler decides from that state:
whether it claims the event or lets it bubble, which controls it returns, and which option it gives the parent.
Routing needs all three when the handler returns, before the next event,
so they can't wait for a render or an effect.
`port-manage` carries its callbacks out in an effect, from a queue of pending actions it keeps in its state,
which costs a frame and the queue, and still can't put off whether a key bubbles.

So the setter returns the state it settled at, and an identity updater reads the latest state,
which `get_state(setter)` names, so a handler doesn't spell the updater out.
Every caller discards the setter's return value today, so returning the state changes nothing at runtime.
A return value also passes through a function that wraps the setter, as `lambda edit: set_value(...)` does,
where a method such as `get` wouldn't, so `use_text_input`'s validating callers keep working.
An updater that returns a result beside the next state, as Haskell's `atomicModifyIORef` does, adds nothing:
a handler is synchronous and nothing runs between its read and its write,
so reading and then setting in plain code is as atomic.

The value stays what a render reads, and a handler that decides from it rather than reading
decides from stale state when keys arrive before a render.
That's a rule of the hooks, like the others, and the docs state it once.

### Why not render between events

React renders between discrete events, so every handler sees the state the last event left, and nothing reads.
A prototype rendered (without painting) before routing each key press or paste whenever state had changed since
the last render, with mouse events still routed through the painted frame, so clicks hit what was drawn.
Mouse moves never triggered it, and a hover followed by a key cost one render.
Typing a burst into a picker over 5000 paths, all of it landing in one batch, the median per burst in ms was:

| Burst | Picker alone, matching cached | Picker alone, matching each render | Beside a 2000-row log, matching cached |
|---|---|---|---|
| 4 keys | 0.58 → 1.56 | 2.48 → 14.3 | 12.1 → 38.0 |
| 16 keys | 0.71 → 5.52 | 2.62 → 50.2 | 12.2 → 150 |
| 64 keys | 1.42 → 12.0 | 3.27 → 194 | 12.9 → 509 |

A burst costs one render today and one per key with renders between them.
The framework's part of each is small in a small app (0.1 to 0.3 ms),
and grows with the whole tree in a large one (6 to 9 ms beside the log, most of it `place` walking every node),
on top of whatever the app's components do in a render: 3 ms of matching per key, which today runs once a burst.
A terminal without bracketed paste sends a paste as a key press per grapheme,
so a long paste would render once per character.
And it buys more than handlers need, since only their decisions need the latest state.

`place` is also about a quarter of that large app's ordinary frames, which is worth a look of its own.
The `picker-burst` benchmark keeps a frame of typed-ahead keys measured: each frame's key press queues a burst
of edits and moves into a picker, which the loop handles in one batch before it renders once.

## Public API

### `Setter`

```python
type Setter[T] = Callable[[Callable[[T], T] | T], T]
```

`use_state`'s setter returns the state as it settled: the value it was given, or what the updater returned.
Given `lambda state: state`, it returns the state as every update since the last render left it,
and since that leaves the state equal, it queues no render.
After the component unmounts, it ignores updates and returns the state as it was when the component unmounted.

```python
def get_state[T](set_state: Setter[T]) -> T: ...
```

`get_state` is the state as every update since the last render left it, read by calling `set_state` with
an updater that returns the state it's given, so it changes nothing and queues no render.
It's for handlers and effects; a render reads the value `use_state` returned.

`use_text_input`, `use_text_area`, `text_input` and `text_area` take
`set_value: Callable[[Callable[[str], str]], str]`, a function that applies an edit and returns the value it settled at,
so a wrapper that validates (`lambda edit: set_value(...)`) passes the result through,
and the hooks read the latest value and the edited one from what it returns.
A parameter annotated `-> None` won't accept a function that returns a value under mypy,
so these change in the same release.
A user's parameter annotated `Setter[T]` follows the alias and needs nothing;
only one that writes the type out as `Callable[..., None]` needs `Setter[T]` instead.

### `Highlight`

```python
@dataclass(frozen=True, slots=True)
class Highlight:
    key: object = None
    index: int = 0

    def index_in[T](
        self, options: Sequence[T], key: Callable[[T], object] = ..., is_disabled: Callable[[T], bool] | None = None
    ) -> int | None: ...
    def landed[T](self, options: Sequence[T], key: ..., is_disabled: ...) -> Highlight: ...
    def moved[T](self, options: Sequence[T], by: int, key: ..., is_disabled: ...) -> Highlight: ...
```

Which of a list of options is highlighted: the one whose key is `key`, or, when none is,
the one at `index`, clamped to the last.
`Highlight()` highlights the first option, and `Highlight(key=current)` the current one, wherever the list puts it.
`key` defaults to the option itself, and a key of `None` is no key.

- `index_in` is the highlighted option's index, passing over the options `is_disabled` marks,
  or `None` if there are none to highlight,
  so a parent that previews the highlighted option agrees with the component drawing the list about which it is.
- `landed` is the highlight on the option it's on now, by that option's key and index,
  so it follows that option rather than the one it held, if that comes back, as `port-manage` does after a refresh.
- `moved` is the highlight `by` enabled options on, back for a negative `by`, wrapping at either end.

### `fuzzy_matches` and `substring_matches`

```python
@overload
def fuzzy_matches(text: str, options: Iterable[str]) -> tuple[str, ...]: ...
@overload
def fuzzy_matches[T](text: str, options: Iterable[T], key: Callable[[T], str]) -> tuple[T, ...]: ...
```

`substring_matches` has the same signatures.
`fuzzy_matches` keeps the options whose `key` holds the typed letters in order, with anything between them;
`substring_matches` keeps the ones that contain the text whole.
Both compare `casefold`ed text, keep the options in their own order except that the one `text` names exactly comes first,
and keep every option for an empty text.
`fuzzy_matches` escapes the letters with `glob.escape` and compares with `fnmatchcase`,
since `fnmatch` folds case only on Windows.
`key` lets `filter_list` match files by path and get files back,
and `port-manage` match a listener by its port, command and directory together.

### The `combobox` widget

```python
@component
def combobox(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
    options: Sequence[str],
    placeholder: str = "",
    opens: Literal["below", "above"] = "below",
    shown_rows: int = 5,
    style: Style = ...,
    styles: ComboboxStyles = ...,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Div: ...
```

A `text_input`-style box whose `fuzzy_matches` open in a list over the content below it, or above it,
clipped only by the screen, at most `shown_rows` tall, scrolling the rest.
It takes the text as `text_input` does, and keeps the highlight and whether the list is dismissed itself.
It shows matches once something is typed, as the cookbook does,
and choosing one sets the text to it and dismisses the list.
Its keys are the combobox pattern's, but for Tab, which chooses, as it does in the cookbook and in editors'
completion lists, since a field that completes as you type has nothing better for Tab to do while its list is open:

| Key | Open, with an option highlighted | Open, nothing to highlight | Dismissed |
|---|---|---|---|
| Down, Up | Highlight the next or previous option, wrapping | Bubbles | Reopen, highlighting the first or the last |
| Enter, Ctrl+J, Tab | Choose it | Bubbles | Bubbles |
| Escape | Dismiss | Dismiss | Bubbles |
| Anything else | The text field's | The text field's | The text field's |

A dismiss key on a dismissed list bubbles, so a dialog around the field can close on it.
Ctrl+J chooses because a tty turns an Enter typed ahead, before the app makes it raw, into a line feed.
Each key decides from the latest state, read through the setters.
Hovering a row highlights it, and clicking it chooses it, keeping focus in the field.
An app that wants other keys builds its own from the parts, as the docs' recipes do.
`ComboboxStyles` holds a `TextFieldStyles` for the box and cursor,
and the styles of the list's box, its rows, and the highlighted row.
It takes `opens` rather than flipping on its own, because flipping needs the screen's height,
which only the app's root knows (see [Open questions](#open-questions)).

## Kinds of picker

Every picker is a set of answers to the same few questions,
and each answer shows up as a specific piece of state or a specific case in the handler.
The docs' recipes are these examples, one idea each.

### The decisions

| Decision | Choices | How it shows in code |
|---|---|---|
| Where the options appear | A popup that opens and closes; a list that's always there; not drawn, cycled into the text; ghost text after the cursor | Popup: an `is_dismissed` beside the highlight, set by Escape and choosing, cleared by Down, Up and edits, with the rows drawn only while open. Always there: no dismissed state, and Escape unhandled, so it reaches whatever closes the dialog. Cycled: no rows; Tab writes the highlighted match into the text, matched against the text as it was when cycling started (`Cycling.stem`). Ghost: no `Highlight` at all; the suggestion is derived from the text, drawn after it, and Right at the end accepts it |
| What the value is | Free text, which the options suggest; one of the options, with the text only a filter | Free text: the parent owns the text (`text` and `set_text` parameters), and choosing writes an option into it. One of the options: the text is the component's own `use_state`, and choosing calls the parent's callback with the option (`run`, `stop`, `remove`) |
| What's highlighted after an edit | The first match (the pattern's automatic selection); nothing until Down or Up (manual selection) | Automatic: the state is a `Highlight`, reset to `Highlight()`. Manual: a `Highlight \| None`, reset to `None`, and Enter with `None` acts on the text itself |
| When matches show | Once something is typed; always, every option for an empty text | `fuzzy_matches(text, PACKAGES) if text else ()`, or the call without the guard |
| What matches | Letters in order; the text whole; a prefix; anything else | `fuzzy_matches`, `substring_matches`, or an expression of the caller's own (cycling's `startswith`), with `key=` to match on part of a richer option |
| How the highlight follows changing options | By position; by the option's key | `key` passed to `Highlight`'s methods (`pid_of`), and `landed` after an edit, so the key is recorded from the first keystroke |
| Rows the highlight skips | None; headings | `is_disabled=` on `Highlight`'s methods, which doesn't exist yet, so no example below runs it |
| What choosing does | Fill in the text and close; act, and let the parent close; act and stay | The body of the Enter case, and what the parent's callback does |
| Which keys do what | The combobox pattern's; the command line's; the app's own | The key sets in the `match`'s cases: `Key.Down \| Key.Tab \| Key.ControlN`, a case for Ctrl+X, a case for `" "` |
| How many | One; several | A `frozenset` of marks beside the highlight, a case that toggles one, and Enter acting on the marks |
| Who owns the state | The component; its parent | Where the `use_state` calls are: a parent that previews the highlighted option owns the `Highlight` and passes it down with its setter |

How the examples answer them:

| Example | Options appear | Value | After an edit | Matching | Follows | Choosing | Keys | How many |
|---|---|---|---|---|---|---|---|---|
| [Combobox](#a-combobox-with-free-text) | Popup | Free text | First match | Fuzzy, once typed | Position | Fills in the text, closes | The pattern's, and Tab | One |
| [Command palette](#a-command-palette) | Always | An option | First match | Substring, always | Position | Acts; the parent closes | The pattern's | One |
| [Search box](#a-search-box-with-manual-selection) | While typed | Free text | Nothing | Substring, once typed | Position | Acts on the text or the option | The pattern's | One |
| [Tab cycling](#tab-cycling) | Not drawn | Free text | Nothing | Prefix | Position | Writes into the text | Tab, Shift+Tab | One |
| [Inline completion](#inline-completion) | Ghost text | Free text | (derived) | Prefix of history | (none) | Fills in the text | Right | One |
| [Refreshing rows](#rows-that-refresh-with-keys-of-their-own) | Always | An option | First match | Substring by `key`, always | Key | Acts and stays | The command line's, and Ctrl+X | One |
| [Marks](#marking-several-options) | Always | Several options | First match | Fuzzy by `key`, always | Key | Acts on the marks | The pattern's, and Space | Several |

The examples were written as a module and type-checked with mypy in strict mode,
against stand-ins for `use_state` and `use_text_input` whose setters return the state,
and each was driven headless through the keys its section describes.
Imports are left out; `Setter` and `get_state` are `counterweight.hooks`'s.
The module becomes `snippets/options.py` (see [Docs](#docs)).

### Shared functions

Every example draws the text and its rows with these two functions,
so the examples below differ only in their behavior:

```python
CURSOR = Style(text_style=(text_color("slate", 900) | text_bg("sky", 300)).text_style)


def field_row(field: TextInput, ghost: str = "") -> Div:
    """The text and its cursor, as `text_input` draws them, and `ghost` dimmed after them, starting in the cursor's cell."""
    at_cursor = field.at_cursor
    if ghost and not field.after_cursor:
        at_cursor, ghost = ghost[0], ghost[1:]
    return Div(
        style=row | overflow_x_scroll | stick_to_end_x,
        on_input=field.on_press,
        children=(
            Text(content=field.before_cursor, style=text_wrap_none),
            Text(content=at_cursor, style=text_wrap_none | CURSOR, handle=field.cursor_cell),
            Text(content=field.after_cursor, style=text_wrap_none),
            Text(content=ghost, style=text_wrap_none | text_color("slate", 500)),
        ),
    )


def option_rows[T](
    shown: Sequence[T],
    highlighted: int | None,
    row_handle: ElementHandle,
    choose: Callable[[T], InputResponse],
    label: Callable[[T], str] = str,
) -> Div:
    """A row per option, the highlighted one marked and given `row_handle`, each choosing its option on a click."""
    return Div(
        style=col | max_height(4) | overflow_y_scroll,
        children=tuple(
            Text(
                content=label(option),
                style=text_wrap_none | (text_bg("sky", 800) if index == highlighted else Style()),
                handle=row_handle if index == highlighted else None,
                on_input=on_click(partial(choose, option)),
            )
            for index, option in enumerate(shown)
        ),
    )
```

### A combobox with free text

The cookbook's autocomplete, and what the `combobox` widget does:
the parent owns the text, the matches open in a list once something is typed,
and Escape or choosing closes it until the next edit, Down or Up.

```python
@dataclass(frozen=True, slots=True)
class Suggesting:
    highlight: Highlight = Highlight()
    is_dismissed: bool = False


@component
def package_field(text: str, set_text: Setter[str]) -> Div:
    suggesting, set_suggesting = use_state(Suggesting())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(text, set_text, auto_focus=True)
    shown = fuzzy_matches(text, PACKAGES) if text else ()
    is_open = field.focus.is_focused and not suggesting.is_dismissed and bool(shown)

    def choose(package: str) -> InputResponse:
        set_text(package)
        set_suggesting(Suggesting(is_dismissed=True))
        return ()

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None
        before, now = get_state(set_text), get_state(set_suggesting)
        now_shown = fuzzy_matches(before, PACKAGES) if before else ()
        index = now.highlight.index_in(now_shown)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key) if now_shown:
                by = 1 if key == Key.Down else -1
                if now.is_dismissed:
                    highlight = Highlight(index=0 if by == 1 else len(now_shown) - 1)
                else:
                    highlight = now.highlight.moved(now_shown, by)
                set_suggesting(Suggesting(highlight=highlight))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Enter | Key.ControlJ | Key.Tab) if index is not None and not now.is_dismissed:
                return choose(now_shown[index])
            case KeyPressed(key=Key.Escape) if not now.is_dismissed:
                set_suggesting(replace(now, is_dismissed=True))
                return ()
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                if get_state(set_text) != before:
                    set_suggesting(Suggesting())
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    return Div(
        style=col | width(24),
        on_input=on_input,
        children=(
            field_row(field),
            *((option_rows(shown, suggesting.highlight.index_in(shown), row_handle, choose),) if is_open else ()),
        ),
    )
```

### A command palette

An always-open list whose value is one of its options:
the text is the palette's own, there's no dismissed state,
and Escape isn't handled, so it bubbles to whatever opened the palette.

```python
@component
def command_palette(run: Callable[[str], InputResponse]) -> Div:
    text, set_text = use_state("")
    highlight, set_highlight = use_state(Highlight())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(text, set_text, auto_focus=True)
    shown = substring_matches(text, COMMANDS)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None
        before, now = get_state(set_text), get_state(set_highlight)
        now_shown = substring_matches(before, COMMANDS)
        index = now.index_in(now_shown)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                set_highlight(now.moved(now_shown, 1 if key == Key.Down else -1))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Enter | Key.ControlJ) if index is not None:
                return run(now_shown[index])
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                if get_state(set_text) != before:
                    set_highlight(Highlight())
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    return Div(
        style=col | width(24) | border | border_lightrounded,
        on_input=on_input,
        children=(
            field_row(field),
            option_rows(shown, highlight.index_in(shown), row_handle, run),
        ),
    )
```

### A search box with manual selection

Nothing is highlighted until Down or Up, so Enter searches what was typed,
or the suggestion the keys moved to.
The highlight's state is `Highlight | None`, and an edit resets it to `None`.

```python
@component
def search_box(search: Callable[[str], InputResponse]) -> Div:
    text, set_text = use_state("")
    nothing: Highlight | None = None
    highlight, set_highlight = use_state(nothing)
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(text, set_text, auto_focus=True)
    shown = substring_matches(text, QUERIES) if text else ()

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None
        before, now = get_state(set_text), get_state(set_highlight)
        now_shown = substring_matches(before, QUERIES) if before else ()
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key) if now_shown:
                by = 1 if key == Key.Down else -1
                if now is None:
                    set_highlight(Highlight(index=0 if by == 1 else len(now_shown) - 1))
                else:
                    set_highlight(now.moved(now_shown, by))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Enter | Key.ControlJ):
                index = None if now is None else now.index_in(now_shown)
                return search(before if index is None else now_shown[index])
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                if get_state(set_text) != before:
                    set_highlight(None)
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    highlighted = None if highlight is None else highlight.index_in(shown)
    return Div(
        style=col | width(24),
        on_input=on_input,
        children=(field_row(field), option_rows(shown, highlighted, row_handle, search)),
    )
```

### Tab cycling

As bash completes: no list is drawn, and Tab writes the next match into the text.
The matches come from the text as it was when cycling started, which `Cycling` keeps,
and any edit ends the cycle.

```python
@dataclass(frozen=True, slots=True)
class Cycling:
    stem: str
    highlight: Highlight


@component
def command_line() -> Div:
    text, set_text = use_state("")
    nothing: Cycling | None = None
    cycling, set_cycling = use_state(nothing)
    field = use_text_input(text, set_text, auto_focus=True)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None
        before, now = get_state(set_text), get_state(set_cycling)
        match event:
            case KeyPressed(key=Key.Tab | Key.BackTab as key):
                by = 1 if key == Key.Tab else -1
                stem = before if now is None else now.stem
                matches = tuple(program for program in PROGRAMS if program.startswith(stem))
                if not matches:
                    return ()
                if now is None:
                    highlight = Highlight(index=0 if by == 1 else len(matches) - 1).landed(matches)
                else:
                    highlight = now.highlight.moved(matches, by)
                set_cycling(Cycling(stem=stem, highlight=highlight))
                set_text(matches[highlight.index])
                return ()
            case _:
                response = field.on_input(event, receiver)
                if get_state(set_text) != before:
                    set_cycling(None)
                return response

    return Div(style=row, on_input=on_input, children=(Text(content="$ "), field_row(field)))
```

### Inline completion

As fish suggests: the rest of the first line from history that starts with the text is drawn dimmed after it,
and Right at the end of the text accepts it. There's no highlight to keep, since the suggestion is derived.

```python
@component
def shell_prompt() -> Div:
    text, set_text = use_state("")
    field = use_text_input(text, set_text, auto_focus=True)

    def suggestion(typed: str) -> str | None:
        return next((line for line in HISTORY if line.startswith(typed) and line != typed), None) if typed else None

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None
        match event:
            case KeyPressed(key=Key.Right) if (
                field.cursor == len(now := get_state(set_text)) and (line := suggestion(now)) is not None
            ):
                set_text(line)
                return ()
            case _:
                return field.on_input(event, receiver)

    ghost = (line or "")[len(text) :] if (line := suggestion(text)) is not None else ""
    return Div(style=row, on_input=on_input, children=(Text(content="$ "), field_row(field, ghost=ghost)))
```

### Rows that refresh, with keys of their own

As `port-manage`: the rows come from the parent and change between renders,
so the highlight follows its row by `pid_of`,
the keys are the command line's, and Ctrl+X acts on the highlighted row without closing.
An edit lands the highlight on the first match, so it follows that row from the first keystroke.

```python
def pid_of(process: Process) -> int:
    return process.pid


@component
def process_list(processes: tuple[Process, ...], stop: Callable[[Process], InputResponse]) -> Div:
    text, set_text = use_state("")
    highlight, set_highlight = use_state(Highlight())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(text, set_text, auto_focus=True)

    def matching(typed: str) -> tuple[Process, ...]:
        return substring_matches(typed, processes, key=lambda process: f"{process.pid} {process.command}")

    shown = matching(text)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None
        before, now = get_state(set_text), get_state(set_highlight)
        now_shown = matching(before)
        index = now.index_in(now_shown, pid_of)
        match event:
            case KeyPressed(key=Key.Down | Key.Tab | Key.ControlN):
                set_highlight(now.moved(now_shown, 1, pid_of))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Up | Key.BackTab | Key.ControlP | Key.ControlK):
                set_highlight(now.moved(now_shown, -1, pid_of))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.ControlX) if index is not None:
                return stop(now_shown[index])
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                if get_state(set_text) != before:
                    set_highlight(Highlight().landed(matching(get_state(set_text)), pid_of))
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    return Div(
        style=col | width(30),
        on_input=on_input,
        children=(
            field_row(field),
            option_rows(
                shown,
                highlight.index_in(shown, pid_of),
                row_handle,
                stop,
                label=lambda process: f"{process.pid:>5} {process.command}",
            ),
        ),
    )
```

### Marking several options

As `wt`'s cleanup picker: the marks are kept beside the highlight, so the text hiding a marked option leaves it marked,
and the header counts every mark.
Space toggles the highlighted option's mark, which works because branch names can't contain a space;
a picker whose options can picks another key.
A worktree with changes can't be marked, and Enter acts on the marks, doing nothing when there are none.

```python
def branch_of(worktree: Worktree) -> str:
    return worktree.branch


@component
def cleanup(remove: Callable[[frozenset[str]], InputResponse]) -> Div:
    text, set_text = use_state("")
    highlight, set_highlight = use_state(Highlight())
    marked, set_marked = use_state(frozenset[str]())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(text, set_text, auto_focus=True)
    shown = fuzzy_matches(text, WORKTREES, key=branch_of)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None
        before, now = get_state(set_text), get_state(set_highlight)
        now_shown = fuzzy_matches(before, WORKTREES, key=branch_of)
        index = now.index_in(now_shown, branch_of)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                set_highlight(now.moved(now_shown, 1 if key == Key.Down else -1, branch_of))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=" ") if index is not None:
                if not (worktree := now_shown[index]).is_dirty:
                    set_marked(lambda marked: marked ^ {worktree.branch})
                return ()
            case KeyPressed(key=Key.Enter | Key.ControlJ):
                return remove(marks) if (marks := get_state(set_marked)) else ()
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                if get_state(set_text) != before:
                    set_highlight(Highlight())
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    def label(worktree: Worktree) -> str:
        return (
            f"{'x' if worktree.branch in marked else ' '} {worktree.branch}{' (changes)' if worktree.is_dirty else ''}"
        )

    return Div(
        style=col | width(30),
        on_input=on_input,
        children=(
            Text(content=f"{len(marked)} marked"),
            field_row(field),
            option_rows(shown, highlight.index_in(shown, branch_of), row_handle, lambda _: (), label=label),
        ),
    )
```

Base UI's `multiple` shows a library could own marks, but the mark key collides with typing in a way
each picker settles differently, and one picker needs it, so it waits for a second.

### What the examples show

- Two blocks recur in most of the handlers.
  The first, at the top: read the text and the highlight with `get_state`, match the latest text, and resolve the index.
  The second, in the last case: pass the event to the text field, reset the highlight if the text changed,
  and scroll the list.
  They are the candidates for a part of their own, if the ports in [Steps](#steps) find them too.
- Every handler here decides something from the latest state (whether to claim a key, which option to choose),
  so each reads once at the top and writes plain values, since nothing changes the state between its read and its write.
  A case that only moves state along, as toggling a mark does, is an updater and reads nothing.
- `TextInput.cursor` is the cursor as last rendered, so inline completion's "Right at the end"
  decides from a stale cursor when keys arrive before a render;
  the setter's return value reaches the state a component holds, not the cursor `use_text_input` holds.
- Nothing here needed a wired hook's parameters: each kind is a different set of cases,
  not a different setting of the same ones.

## Implementation

- `src/counterweight/hooks/_types.py` and `src/counterweight/hooks/_impls.py`: `Setter` returning `T`,
  and the setter `UseState` builds holding the value itself, with the mount status, the node key and the queue,
  rather than holding the `UseState` weakly, so it still has a state to return once the `UseState` is collected,
  and forms no cycle with it.
- `src/counterweight/headless/_text_input.py`, `_text_area.py` and `src/counterweight/widgets.py`:
  `set_value` returns the value it settled at, and the hooks read the latest value and the edited one from it.
- `src/counterweight/hooks/`: `get_state`, joining `counterweight.hooks.__all__`.
- `benchmarks/picker_burst.py`: its `latest`, which copies the value out of an identity updater, replaced by `get_state`.
- `src/counterweight/headless/_options.py`, pure: `Highlight`, `fuzzy_matches` and `substring_matches`.
- `src/counterweight/widgets.py`: `combobox` and `ComboboxStyles`,
  sharing `cursor_chunks` and `placeholder_chunks` with `text_input`.
- `counterweight.headless.__all__` gains `Highlight`, `fuzzy_matches` and `substring_matches`;
  `counterweight.widgets.__all__` gains `combobox` and `ComboboxStyles`.

## Tests

- `tests/hooks/test_use_state.py`: the setter returning the value it's given and what an updater returns;
  an identity updater reading an update made since the render, and queueing no render;
  several updates in one handler; and the state at unmount, after the `UseState` is collected.
  `assert_type` on what a setter returns, so the type can't fall back to `None`.
  `get_state` reading an update made since the render, without queueing a render.
- `tests/headless/test_use_text_input.py` and `test_use_text_area.py`: a validating wrapper (`lambda edit: set_value(...)`)
  that rejects an edit leaves the cursor where it was.
- `tests/headless/test_options.py`, on the parts:
  the highlight staying on its option as an option before it appears and as one before it goes,
  landing on the option that took its place when its own goes, on the new last when the last goes,
  `landed` following the option it landed on, moving and wrapping both ways,
  and passing over disabled options, including when every option is disabled.
  The matchers: the exact name first, glob characters matching themselves, `casefold` (`ß` matching `SS`),
  every option for an empty text, order kept, and `key`.
  Property tests for wrapping (moving once per enabled option returns to the start)
  and for resolution never landing on a disabled option.
- `tests/test_widgets.py`: the widget opening below and above, choosing filling in the text,
  Escape and reopening, Tab choosing without moving focus, a hover highlighting, a click choosing with focus kept,
  and text and Enter arriving before a render choosing from what the text matches.
- `tests/examples/test_snippets.py`: the picker choosing from the latest text,
  driven on a pseudo-terminal with the text and Enter in one write, as the spike's probe was;
  and each kind in `snippets/options.py` driven through its keys, asserting what it shows:
  the combobox filling in the text with Down and Enter, closing on Escape and reopening on Up;
  the palette running the option Down moved to;
  the search box searching the typed text with nothing highlighted, and the suggestion once Down moves to one;
  Tab cycling writing the matches in turn, wrapping, and an edit ending the cycle;
  inline completion showing the rest of a history line and Right accepting it;
  the refreshing rows keeping the highlight on its row as a row appears above it;
  marks counting, refusing a worktree with changes, and Enter acting on them;
  headings never highlighted; and the preview following the highlight.
- The ported snippets' existing stills stay byte-identical, which checks the parts against the code they replace.

## Docs

- `docs/headless/options.md`, a new page in the Headless components section:
  the parts, then the [decision table](#the-decisions) and the table placing each example on it,
  then a section per kind of picker, each with its code, its still, and a cast of someone using it:
  - [A combobox with free text](#a-combobox-with-free-text), and the `combobox` widget that wires it.
  - [A command palette](#a-command-palette).
  - [A search box with manual selection](#a-search-box-with-manual-selection).
  - [Tab cycling](#tab-cycling).
  - [Inline completion](#inline-completion).
  - [Rows that refresh, with keys of their own](#rows-that-refresh-with-keys-of-their-own).
  - [Marking several options](#marking-several-options).
  - Headings the highlight skips, with `is_disabled`, and a preview of the highlighted option,
    with the text and the `Highlight` in a parent (a color swatch),
    so every row of the decision table has an example; these two aren't written yet.

  Matching and "A long list" move to it from the cookbook.
- `snippets/options.py` holds every kind on that page as a root in `ROOTS`, each between section markers of its own,
  which the page shows with `<!-- example: options.py:<kind> -->`,
  and the shared functions in one more section, which the page shows once, before the kinds.
  It's one module rather than one per kind because an example imports only from the library,
  so a module per kind would each carry its own copy of the shared functions;
  the cost is that `counterweight examples copy` hands over every kind at once.
  The kinds checked for this plan are the start of it.
  Its `STILLS` has a still per kind, after the keys its section describes, named `options-<kind>`,
  and its `DEMOS` a `Demo` per kind under the same name, its keys typed at a person's pace with `paced`
  (typing, moving the highlight, choosing, and for each kind the keys that make it that kind:
  Escape and Up reopening the combobox, Enter on typed text in the search box, Tab and Shift+Tab cycling,
  Right accepting a completion, a row appearing above the highlight, Space marking and refusing),
  which each section plays with `<!-- cast: options-<kind> -->` beside its still.
- `docs/hooks/use_state.md`: what the setter returns, and reading the latest state in a handler with `get_state`
  where a decision needs it, since the value a render saw is stale once keys arrive before the next render,
  with a `::: counterweight.hooks.get_state` reference.
- `docs/headless/index.md`: a row for the parts and `combobox`.
- `docs/cookbook/autocomplete.md` keeps what's about layout (escaping the panel, inside a scroll container,
  opening upward, and opening a picker with a key, with its sections and handles), built on the parts,
  and links to the new page for matching, keys and scrolling.
- `docs/inline.md`'s picker, built on the parts with an Enter that returns the `Print` and `Quit`,
  links to the new page.
- Links to `#a-long-list`, inbound from `input-handling/controls.md` and `layout/scrolling.md`
  and the cookbook page's own "[scrolls](#a-long-list)", point at the new page.
- `docs/changelog.md`: Added entries for the parts, `get_state`, and the widget;
  Changed entries for the setter returning the state, and for the text hooks' `set_value` returning the value,
  each saying that a parameter typed `Setter[T]` needs nothing, and one written out as `Callable[..., None]` needs `Setter[T]`.

## Steps

1. The setter returning the state, `get_state`, the text hooks reading through the setter, and their tests.
2. The parts, with `is_disabled`, and their tests.
3. Port `snippets/picker.py`, `snippets/autocomplete.py` and `snippets/inline_picker.py` onto the parts and the setter's return value,
   with their stills unchanged.
4. Port every other picker onto them locally, against an editable install, to prove the parts before they ship:
   whats-new's picker and assess's two, and `wt`, `kube-pick`, `port-manage` and `zellij-pick-tab`,
   whose self-tests must pass unchanged but for the code under test.
   Note the wiring lines that recur across them, which are the evidence a wired hook would need.
5. The widget, its styles and tests.
6. The docs page, with `snippets/options.py` holding every kind, its stills, casts and tests,
   the trimmed cookbook page, and the changelog.
7. After a release: land the ports.

The spike's `_options.py`, its tests and the ported `picker.py` are the start of steps 2 and 3,
with the picker's `latest`, which copies the value out of an identity updater, replaced by `get_state`.

## Open questions

1. **Stopping at the ends.** `inline_picker.py` stops rather than wrapping, because it doesn't scroll.
   A `wrap` parameter on `moved`, or the caller computing the index itself?
2. **Binding `key` once.** Every `Highlight` method takes `key` and `is_disabled`,
   which `port-manage` wraps in methods of its own state to avoid repeating.
3. **Flipping the widget's list.** `opens` puts the choice on the caller.
   The web's answer is CSS anchor positioning's `position-try-fallbacks: flip-block`,
   a layout feature counterweight doesn't have; adding something like it would let the widget flip itself.
4. **Down on an empty widget.** Chrome opens every `<datalist>` option on Down in an empty field.
   The widget could do the same by showing every option once the list is reopened with nothing typed.
5. **The matchers' names.** `fuzzy_matches` is the common word (fzf, VS Code's quick open),
   though "fuzzy" often implies scoring, and this only puts the exact name first.
6. **`filter_list`'s close on blur.** `filter_list` throws its whole state away when its field loses focus,
   and counterweight has no blur event to hang that on, so it keeps its `run_on_mount`.
7. **The recurring handler blocks.** Reading the latest state and matching it, and passing an edit to the field
   and resetting the highlight, recur across the [examples](#what-the-examples-show).
   A part for them would be a function over a `TextInput`, a text `Setter` and a highlight `Setter`;
   whether it's worth one depends on whether the real pickers repeat them as the examples do.
8. **The cursor's latest position.** `use_text_input` keeps its cursor in state of its own,
    and `TextInput.cursor` is the one the last render saw.
    A handler that decides from the cursor, as inline completion's Right does, needs a way to read the latest.
