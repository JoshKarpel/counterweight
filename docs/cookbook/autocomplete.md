# Autocomplete

An autocomplete field suggests completions as you type,
in a list that opens under the field and lays over whatever is there.
The list has to reach past the box the field is in,
which here is a form that [scrolls](../layout/scrolling.md) inside a [`fill(1)`](../layout/splitting-space.md) panel,
and so clips its children.

Counterweight has no text input element, so the recipe builds a minimal one:
a [focusable](../hooks/use_focus.md) component that keeps its text in state,
and appends each typed grapheme to it or, for Backspace, removes the last one.

```python
--8<-- "autocomplete.py:example"
```

Typing `py` into the package field opens the list,
which reaches past the bottom of the panel and over the text below it:

![The list of packages matching "py", reaching past the panel](../assets/autocomplete-open.svg)

## Matching

A candidate matches when the typed letters appear in it in order, with anything between them,
so `py` matches `mypy` as well as `pytest`.
`matches` builds a pattern with a `*` between and around the typed letters,
each escaped with `glob.escape`, so a typed `[` or `?` matches itself rather than starting a pattern.
It lowercases both sides and compares them with `fnmatchcase`,
since `fnmatch` folds case only where `os.path.normcase` does, which is on Windows alone.

The list shows at most `MOST_SHOWN` matches, in the order of the candidates.

## The list

The list is a `Div` the field renders only while it's focused and has matches,
so it closes when focus moves away:
Tab with the list closed bubbles to the root's `tab_focus`,
and a press anywhere that doesn't claim it bubbles to the root's `clear_focus`.

It's [absolutely positioned](../layout/layering.md#absolute-positioning) against the field,
so it doesn't push the fields below it down.
`inset_top=Percent(1.0)` puts its top edge at the bottom of the field,
and `inset_x(0)` makes it as wide as the field.
It's raised with `z(1)`, so it's drawn over the fields and text that follow it.

## Choosing a match

Down and Up move the highlight through the list, wrapping at the ends.
The field keeps which match is highlighted in state, and resets it whenever the text changes:

![The third match highlighted after Down twice](../assets/autocomplete-highlighted.svg)

Enter or Tab replaces the text with the highlighted match, and closes the list:

![The package field holding pydantic-settings](../assets/autocomplete-chosen.svg)

Escape closes the list too, and it stays closed until the text changes.
Each of these keys is handled only while the list is open,
so with it closed, Tab moves focus and Enter bubbles to whatever handles it outside the field.

A press on a match chooses it, through [`on_click`](../input-handling/handlers.md).
`on_click` claims the press, so it never reaches the root's `clear_focus`, and focus stays in the field.

## Escaping the panel

The list sets [`clip_to_screen`](../layout/clipping.md#escaping-every-clip), so no ancestor clips it.
With the default, `clip_to_padding`, the panel would cut the list off at its padding box:

![The same list cut off at the panel's border](../assets/autocomplete-clipped.svg)

`clip_to_screen` changes only what clips the list.
The list is still positioned against the field, and still needs its `z` to cover what follows it.

## Inside a scroll container

The form scrolls, with [`scroll_on_wheel`](../input-handling/handlers.md#scrolling),
and has its border and title on the panel around it, so they stay put while the fields move.
The open list is positioned against its field, so it moves with the field as the form scrolls.
It's part of the form's content, so it also extends how far the form scrolls:
the four fields and the gaps between them reach two rows past the form,
but with the Python field's list open, the form scrolls three rows down, and further still to show all of it.

![The Python field's list, scrolled up with the field](../assets/autocomplete-scrolled.svg)

## Opening upward

A field near the bottom of the screen, below the panel, opens its list above it instead,
with `inset_bottom=Percent(1.0)`, when there's more room above it than below.
The field compares its own border box, from [`use_rects`](../hooks/use_rects.md),
with the screen's height, which the root takes from its own `use_rects` and passes down:

![The list of recipes opening above the field at the bottom of the screen](../assets/autocomplete-upward.svg)

`use_rects` reports the previous frame's rectangles, and empty ones on the first render.
The list only opens once something has been typed, by which time the field and the root have been laid out.
