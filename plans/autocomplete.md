# Plan: An Autocomplete Headless Component

Artifact: https://claude.ai/code/artifact/ad723da1-a0f8-4971-a221-f0be22e0bbe9

This plan adds `use_autocomplete` to `counterweight.headless`, a hook that gives a component
a text field which narrows a list of options as you type, with a highlighted option
that keys move and Enter chooses, and leaves drawing the field and the list to the component.
It adds `autocomplete`, the widget that draws it one way,
`AutocompleteKeys`, which says which keys do what,
and `fuzzy_matches` and `substring_matches`, the two matchers the callers so far have written.
It rebuilds the cookbook's autocomplete and picker snippets on the hook,
and ends with every picker built on counterweight so far ported onto it.
It doesn't cover choosing several options (though it shows how marks compose on top),
loading options asynchronously, or a list you choose from without typing (a `<select>`),
which is what a future `use_picker` would be.

## The question

Every counterweight app with a picker has written its own, and the copies have started to drift.
What part of them is behavior that belongs in the library,
and what part is drawing, or keys, that each app does its own way?

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

The drift so far:

- assess dropped Tab as a choosing key, and the command-line family uses it to move instead.
- `inline_picker.py` stops the highlight at the ends rather than wrapping,
  and at the last row it shows, since it doesn't scroll.
- `filter_list` needs a `run_on_mount` component to close when its field loses focus.
- `shown[query.highlighted]` indexes past the end if the options shrink while the text stays the same,
  which `filter_list` allows, since the diff's files can change while it's open.
- Every cookbook-family copy chooses from the options as last rendered,
  so an Enter that arrives with the keys typed before it, before the next render, chooses from a stale list.

What differs is drawing (sections under bars, headings, descriptions under options, a popup above or below the field,
"nothing matches"), what counts as a match, which keys do what,
what choosing does (fill in the text, set a setting, jump, copy, signal),
and who owns the state (assess's theme picker keeps it in the app, to preview the highlighted theme behind the dialog).

## How the web does it

The [WAI-ARIA combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/) is the reference for the keys:
focus stays in the text box, the highlighted option is marked with `aria-activedescendant`,
Down opens a closed popup, Escape closes an open one,
Tab moves focus on, and Home and End belong to the text box, not the list.
Options can be `aria-disabled`, which the highlight skips.

The headless libraries split along two lines this plan has to pick a side of:

- **Who filters.** [Headless UI's `Combobox`](https://headlessui.com/v1/react/combobox)
  and [Downshift's `useCombobox`](https://github.com/downshift-js/downshift/tree/master/src/hooks/useCombobox)
  take the options already filtered, and leave the filter to the app.
  React Aria takes a filter function.
- **One component or two.** [React Aria](https://react-aria.adobe.com/Autocomplete) and
  [Base UI](https://base-ui.com/react/components/autocomplete) both have a `ComboBox`,
  which selects a value from a fixed set in a popup that closes,
  and an `Autocomplete`, which filters a collection with a text field, for command palettes and searchable menus.
  The cookbook's autocomplete is the first; every picker is the second.

And beyond the keys:

- **Hover highlights.** Downshift and React Aria move the highlight to the option under the pointer.
- **Highlight by key.** React Aria tracks the highlighted option by its key (`focusedKey`),
  so it stays on the same option when the list changes; Downshift tracks an index.
- **Disabled options.** Downshift takes `isItemDisabled`, and React Aria `disabledKeys`;
  the highlight passes over them and they can't be chosen.
- **Control props.** Downshift lets the app control each piece of state on its own
  (`inputValue`, `highlightedIndex`, `isOpen`), or leave it to the hook.
- **Changing the keys.** None of them takes a key map.
  Downshift's `stateReducer` lets an app rewrite what any key does to the state, which is the general form of one.
- **Several options.** Base UI's `Combobox` takes `multiple`, and React Aria's `ComboBox` doesn't.

HTML's own answer is `<input list>` with a `<datalist>`, which offers no hook into its behavior.
HTML's "picker" is the popup a control opens without typing:
[`showPicker()`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/showPicker)
opens a date, color or file input's, and a customizable `<select>` draws its list in a
[`::picker(select)`](https://developer.mozilla.org/en-US/docs/Web/CSS/::picker) pseudo-element.
That's why the hook is `use_autocomplete` rather than `use_picker`: typing to filter is its defining behavior,
and `use_picker` stays free for a select-like control.

Where counterweight differs:

- There's no `aria-activedescendant`, but the same idea applies.
  The highlighted row gets an `ElementHandle`, and `ScrollIntoView` brings it into view.
- There's no anchor positioning, so a popup can't flip itself above its field when it would overflow;
  the cookbook measures the room with `use_rects` and the screen's height.
- A browser runs each key's handler against the state the last one left.
  A counterweight handler is the one the last render made, and several keys can arrive before the next render,
  so a handler that decides from what it rendered decides from stale state.
  `use_text_input` reads the latest value through its setter, which applies an updater immediately, and so does this hook.
- Terminal users expect readline's and fzf's keys (Ctrl+N, Ctrl+P, Tab to move) where a browser has none,
  so the keys are a value an app can change rather than fixed.

## Decisions

| Question | Choice | What it costs |
|---|---|---|
| Who filters | The caller passes a function from the typed text to the options to show; the library exports `fuzzy_matches` and `substring_matches` for it | Every caller writes one line to filter |
| Which list a key acts on | The one the latest text matches: the hook reads the latest query through `set_query` and calls the caller's function on its text | `set_query` MUST apply an updater before returning, as `use_text_input`'s setter must |
| Who owns the state | The caller, wholesale, as one `Query`, as `use_text_input`'s caller owns its value | A caller that only wants the text carries a `Query` and reads `query.text` |
| Highlight by index or by option | By the option's key, and by its index, which is where the highlight lands when its option is gone | Options need a hashable key; and a highlight that has landed on a neighbor returns to its option if that comes back before the next key moves it |
| Which keys do what | An `AutocompleteKeys` value, defaulting to the combobox pattern's | One more parameter; the command-line family passes its own |
| One hook or two | One: open and dismissed are part of `Query`, and an always-open picker never draws from them | Pickers carry an `is_dismissed` they don't draw; one that stays open passes an `on_dismiss` that closes it, or `dismiss=frozenset()`, since a dismissed list's choose keys bubble |
| What choosing does | The caller's `choose` decides, and its response is the hook's; the hook never closes anything itself | The widget and the cookbook autocomplete each write `q.chosen(text)` |
| Rows the highlight skips | An `is_disabled` predicate, as Downshift's `isItemDisabled` | none beyond the parameter |
| Several options | Left to the caller, composed on top (see [Marking several options](#marking-several-options)) | Each multi-select picker keeps its own marks and its own mark key |
| Hover | Highlights the option under the pointer, as Downshift and React Aria do | assess's theme picker previews whatever the pointer passes over |

Owning the state wholesale is Downshift's control props with every prop controlled.
It's what assess's theme picker needs, and it costs an uncontrolled caller one `use_state` line,
where per-field control would mean two code paths for every field.
The matching stays the caller's because the callers disagree on what matches:
sections match a bar by its title, the cookbook autocomplete shows nothing for an empty text,
`filter_list` matches paths but draws `FileDiff`s, `port-manage` matches a port, command and directory as one string,
and the command-line family matches substrings.

Holding the highlight by key is `port-manage`'s design, and its self-tests are the acceptance cases.
`port-manage` also moves the key to the neighbor the highlight lands on as soon as a refresh removes its row;
the hook can't, since it doesn't see the refresh, only the next render,
and writing state while rendering is the thing hooks don't do.

Reading the latest query is what lets every key, Enter included, decide from the state the keys before it left,
without `port-manage`'s queue of pending actions and the effect that carries them out:
`choose` runs in the handler, with the option the latest text highlights,
and returns what to do as a response, such as `CopyToClipboard`.

## Public API

All of it is in `counterweight.headless`, except the widget, which is in `counterweight.widgets`.

### `Query`

```python
@dataclass(frozen=True, slots=True)
class Query:
    text: str = ""
    highlighted_key: Hashable | None = None
    highlighted_index: int = 0
    is_dismissed: bool = False

    def edited(self, text: str) -> Query: ...
    def chosen(self, text: str) -> Query: ...
    def highlighted_in[T](
        self,
        shown: Sequence[T],
        key: Callable[[T], Hashable] = ...,
        is_disabled: Callable[[T], bool] | None = None,
    ) -> T | None: ...
```

What's typed, which option is highlighted, and whether the list was dismissed.
The caller constructs it, so its fields have defaults: `Query(highlighted_key=current)`
opens a picker on its current option, wherever the list puts it.
A query with no `highlighted_key` highlights by index alone until a key, an edit or the pointer moves the highlight,
so a picker whose rows refresh before the first key, as `port-manage`'s do, passes the key it opens on.
`edited` returns the query unchanged when the text is the same, and otherwise the new text
with the first option highlighted and the list no longer dismissed, so moving the cursor leaves the highlight alone.
`chosen` is the query after choosing an option that fills in `text`: that text, dismissed.
`highlighted_in` is the highlighted option among `shown`: the one whose key is `highlighted_key`,
or the one at `highlighted_index`, clamped to the last, or `None` if there are none,
passing over the options `is_disabled` marks,
so a parent that previews the highlighted option, passing the hook's `key` and `is_disabled`,
agrees with the hook about which it is.
`key` defaults to the option itself.

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

### `AutocompleteKeys`

```python
@dataclass(frozen=True, slots=True)
class AutocompleteKeys:
    highlight_next: frozenset[str] = frozenset({Key.Down})
    highlight_previous: frozenset[str] = frozenset({Key.Up})
    choose: frozenset[str] = frozenset({Key.Enter, Key.ControlJ})
    dismiss: frozenset[str] = frozenset({Key.Escape})
```

Which keys move the highlight, choose, and dismiss, checked before the text field sees a key,
so a set can claim a key the field would edit with, as the command-line family's Ctrl+K does.
The defaults are the combobox pattern's, which leaves Tab to move focus.
Ctrl+J chooses because a tty turns an Enter typed ahead, before the app makes it raw, into a line feed.
The cookbook passes `choose=frozenset({Key.Enter, Key.ControlJ, Key.Tab})`, and the command-line family
`highlight_next=frozenset({Key.Down, Key.Tab, Key.ControlN})` and
`highlight_previous=frozenset({Key.Up, Key.BackTab, Key.ControlP, Key.ControlK})`.

### `use_autocomplete`

```python
def use_autocomplete[T](
    query: Query,
    set_query: Callable[[Callable[[Query], Query]], None],
    matching: Callable[[str], Sequence[T]],
    choose: Callable[[T], InputResponse],
    key: Callable[[T], Hashable] = ...,
    is_disabled: Callable[[T], bool] | None = None,
    on_dismiss: Callable[[], InputResponse] | None = None,
    keys: AutocompleteKeys = AutocompleteKeys(),
    highlighted_row: ElementHandle | None = None,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Autocomplete[T]: ...
```

- `query` and `set_query` are the caller's state; `set_query` takes an updater, which it MUST apply before returning,
  as a `use_state` setter does.
- `matching` is the options to show for a text, in order: the hook calls it on the query it renders with,
  again on the latest query for each key in `keys`,
  and on the edited text for each edit that changes it, to record the first enabled option's key with its index,
  so the highlight follows that option from the first keystroke.
  Other events, such as cursor moves, don't call it.
- `choose` is called, in the handler, with the option the latest query highlights, and the hook returns its response,
  or `()` for `None`, as `on_click` returns for its action, so a `choose` that only sets state still claims the key.
  It closes nothing; a picker that closes on choosing does that in `choose`.
- `key` identifies an option across renders, for the highlight to follow; it defaults to the option itself.
  It MUST NOT return `None`, which `highlighted_key` holds for no option.
- `is_disabled` marks options the highlight passes over and that can't be chosen, such as headings.
- `on_dismiss` is called when a dismiss key dismisses the list, after the query is dismissed,
  and the hook returns its response, or `()` for `None` or no `on_dismiss`,
  so a dialog around the field doesn't also close on the key that closed the list;
  a picker passes one that closes it and gives focus back,
  and `wt` one that goes back a step.
- `keys` says which keys do what.
- `highlighted_row` is the handle the highlighted row gets, passed in when whatever opens the list
  scrolls it into view in the frame it opens in, as `Picking.opened()` does; otherwise the hook makes one.
- The last four are `use_text_input`'s, passed on to it.

### `Autocomplete`

| Field | What it is |
|---|---|
| `field` | The `TextInput` from `use_text_input`, to draw the text and its cursor |
| `shown` | The options `matching` gives for the rendered text |
| `is_open` | Whether the field is focused and the list isn't dismissed |
| `highlighted_index` | The highlighted option's index in `shown`, or `None` if nothing can be highlighted |
| `highlighted` | That option, or `None` |
| `highlighted_row` | The `ElementHandle` for the row at `highlighted_index` |
| `on_input` | The handler for the element the component returns, in place of `field.on_input` |
| `option_on_input` | A function from an option's index in `shown` to the handler for its row |

### Keys

`on_input` handles nothing while its element isn't focused,
and decides each key in `keys` from the latest query and the options `matching` gives for its text.

| Key | Open, with an option highlighted | Open, nothing to highlight | Dismissed |
|---|---|---|---|
| `highlight_next` | Highlight the next enabled option, wrapping | Bubbles | Reopen, with the first enabled option highlighted if there is one |
| `highlight_previous` | Highlight the previous enabled option, wrapping | Bubbles | Reopen, with the last enabled option highlighted if there is one |
| `choose` | Return `choose(option)` | Bubbles | Bubbles |
| `dismiss` | Dismiss, and return `on_dismiss()` | Dismiss, and return `on_dismiss()` | Bubbles |
| Anything else | `field.on_input` | `field.on_input` | `field.on_input` |

The keys that move the highlight, and every event `field.on_input` handles,
return `ScrollIntoView(highlighted_row, block="nearest")` beside whatever else they return,
so the list scrolls in the frame the highlight moves.
Reopening a dismissed list follows the combobox pattern.
A dismiss key on a dismissed list bubbles rather than clearing the text, which the pattern allows,
so a dialog around the field can close on it.
A `choose` or `on_dismiss` that returns `None` claims the key, as `on_click`'s action does,
so `wt`'s Enter with nothing marked does nothing,
and the widget's Tab chooses without also moving focus.
PageUp and PageDown aren't handled: the pattern doesn't bind them,
and how far a page is depends on drawing the hook doesn't do.

### Rows

`option_on_input(index)` highlights the option at `index` when the pointer moves over its row with no button held,
leaving the query as it is if it's already highlighted,
and chooses it on a click, as `on_click` does: claiming the left button's press,
and choosing on its release over the row, so a press dragged off the row chooses nothing.
Claiming the press keeps focus in the field unless `choose`'s response moves it.
It does neither for a disabled option.

### Keys of the caller's own

A caller handles keys of its own by putting its handler in front:
`first(on_digit, autocomplete.on_input)` jumps to a tab on a digit, as `zellij-pick-tab` does,
and `first(on_ctrl_x, autocomplete.on_input)` signals the highlighted process, as `port-manage` does,
reading `autocomplete.highlighted`.
A key the caller's handler takes from the hook decides from the rendered state, not the latest;
one that needs the latest reads it through `set_query`, as the hook does.

### Marking several options

The hook chooses one option. `wt`'s cleanup picker composes marks on top of it:

- Its state holds the marks beside the `Query`, so the query hiding a marked option leaves it marked,
  and its header counts every mark.
- Its handler in front takes Space and toggles the highlighted option's mark,
  which works because its options can't contain a space; a picker whose options can picks another key.
- Its `is_disabled`, or a check in that handler, keeps a worktree with changes from being marked.
- Its `choose` ignores the option and acts on the marks, returning `None` when there are none, so Enter does nothing.

Base UI's `multiple` shows a hook could own marks, but the mark key collides with typing in a way
each picker settles differently, and one picker needs it, so it waits for a second.

### The `autocomplete` widget

```python
@component
def autocomplete(
    query: Query,
    set_query: Callable[[Callable[[Query], Query]], None],
    options: Sequence[str],
    placeholder: str = "",
    opens: Literal["below", "above"] = "below",
    shown_rows: int = 5,
    keys: AutocompleteKeys = AutocompleteKeys(choose=frozenset({Key.Enter, Key.ControlJ, Key.Tab})),
    style: Style = ...,
    styles: AutocompleteStyles = ...,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Div: ...
```

A `text_input`-style box whose `fuzzy_matches` open in a list over the content below it, or above it,
clipped only by the screen, at most `shown_rows` tall, scrolling the rest.
It shows matches once something is typed, as the cookbook does,
and choosing one sets the query to `query.chosen(option)`.
Tab chooses by default, as it does in the cookbook and in editors' completion lists,
since a field that completes as you type has nothing better for Tab to do while its list is open.
`AutocompleteStyles` holds a `TextFieldStyles` for the box and cursor,
and the styles of the list's box, its rows, and the highlighted row.
It takes `opens` rather than flipping on its own, because flipping needs the screen's height,
which only the app's root knows (see [Open questions](#open-questions)).

## Implementation

As the text hooks are, beside their pure cores:

- `src/counterweight/headless/_autocomplete_keys.py`, pure: `Query`, `AutocompleteKeys`,
  `fuzzy_matches`, `substring_matches`, the highlighted option's resolution by key, then index, past disabled options,
  and the function from a key, a query, the options shown, which are disabled, whether the list is open, and the keys
  to what the key does: a new query, choosing an option, dismissing, or nothing.
- `src/counterweight/headless/_autocomplete.py`: `use_autocomplete` and `Autocomplete`,
  which call `use_text_input`, read the latest query through `set_query`, carry out what the pure function decides,
  and add the `ScrollIntoView`s.
- `src/counterweight/widgets.py`: `autocomplete` and `AutocompleteStyles`,
  sharing `cursor_chunks` and `placeholder_chunks` with `text_input`.
- `counterweight.headless.__all__` gains `Autocomplete`, `AutocompleteKeys`, `Query`, `fuzzy_matches`,
  `substring_matches` and `use_autocomplete`; `counterweight.widgets.__all__` gains `autocomplete` and `AutocompleteStyles`.

## Tests

- `tests/headless/test_autocomplete_keys.py`, on the pure core:
  wrapping both ways, reopening at the first and the last, each key with nothing to highlight,
  dismissing open and dismissed, a key set that claims Ctrl+K, and `edited` keeping the query for the same text.
  The highlight: staying on its option as an option above it appears and as one above it goes,
  landing on the option that took its place when its own goes, on the new last when the last goes,
  and passing over disabled options, including when every option is disabled.
  The matchers: the exact name first, glob characters matching themselves, `casefold` (`ß` matching `SS`),
  every option for an empty text, order kept, and `key`.
  Property tests for wrapping (moving next `n` times over `n` enabled options returns to the start)
  and for resolution never landing on a disabled option.
- `tests/headless/test_use_autocomplete.py`, driving an app: keys typed ahead before the first render,
  and a run of text and Enter between renders, choosing the option the latest text highlights;
  the list scrolling in the frame the highlight moves; `choose`'s and `on_dismiss`'s responses coming back;
  a `choose` returning `None` claiming the key, so Tab chooses without moving focus;
  an Escape that closes the list not reaching a handler above it; nothing handled while unfocused;
  Tab moving focus with the default keys; hovering highlighting a row; a click choosing and focus staying;
  and a `highlighted_row` passed in being the one the highlighted row gets.
- `tests/test_widgets.py`: the widget opening below and above, choosing filling in the text, Escape and reopening.
- The ported snippets' existing stills stay byte-identical, which checks the hook against the code it replaces.

## Docs

- `docs/headless/use_autocomplete.md`, a new page in the Headless components section,
  from a new snippet, `snippets/use_autocomplete.py`:
  the hook in a command palette, the keys and changing them, matching (moved from the cookbook),
  the highlight following its option as the options change, disabled options under headings,
  the highlight and scrolling (moved from the cookbook's "A long list"), the rows' hover and press,
  keys of the caller's own, marking several options,
  a controlled query that previews the highlighted option (a color swatch),
  and the widget, with stills and a cast.
- `docs/headless/index.md`: a row for `use_autocomplete` and `autocomplete`.
- `docs/cookbook/autocomplete.md` keeps what's about layout (escaping the panel, inside a scroll container,
  opening upward, and opening a picker with a key, with its sections and handles), built on the hook,
  and links to the new page for matching, keys and scrolling.
- `docs/inline.md`'s picker, built on the hook with a `choose` that returns the `Print` and `Quit`,
  links to the new page for the keys and matching.
- Links to `#a-long-list`, inbound from `input-handling/controls.md` and `layout/scrolling.md`
  and the cookbook page's own "[scrolls](#a-long-list)", point at the new page.
- `docs/changelog.md`: an Added entry.

## Steps

1. The pure core and its tests.
2. The hook and its tests.
3. Port `snippets/picker.py`, `snippets/autocomplete.py` and `snippets/inline_picker.py` onto the hook,
   with their stills unchanged.
4. Port every other picker onto it locally, against an editable install, to prove the API before it ships,
   and fold what they find back into it:
   whats-new's picker and assess's two, and `wt`, `kube-pick`, `port-manage` and `zellij-pick-tab`,
   whose self-tests must pass unchanged but for the code under test.
5. The widget, its styles and tests.
6. The docs page, its snippet, the index row, the trimmed cookbook page, and the changelog.
7. After a release: land the ports.

## Open questions

1. **Flipping the widget's list.** `opens` puts the choice on the caller.
   The web's answer is CSS anchor positioning's `position-try-fallbacks: flip-block`,
   a layout feature counterweight doesn't have; adding something like it would let the widget flip itself.
   Is `opens` enough until then?
2. **Down on an empty widget.** Chrome opens every `<datalist>` option on Down in an empty field.
   The widget could do the same by showing every option once the list is reopened with nothing typed.
   Worth matching?
3. **The matchers' names.** `fuzzy_matches` is the common word (fzf, VS Code's quick open),
   though "fuzzy" often implies scoring, and this only puts the exact name first.
4. **A named key set for the command-line family.** All four scripts would pass the same `AutocompleteKeys`.
   It isn't fzf's (fzf moves on Ctrl+J and Ctrl+K) or readline's, so it has no name to export it under yet;
   until it does, each script spells it out.
5. **`filter_list`'s close on blur.** `is_open` covers hiding a list when the field loses focus,
   but `filter_list` throws its whole state away then, and counterweight has no blur event to hang that on.
   It keeps its `run_on_mount` for now; an `on_open_change`, as React Aria's `ComboBox` has, would need one.
