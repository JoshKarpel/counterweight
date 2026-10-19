# `Text`

## Styling Parts of the Text

A `Text`'s `content` is a string, drawn in the `Text`'s `text_style`,
or a tuple of `Chunk`s, each drawn in its own style merged over the `Text`'s `text_style`,
as a `<span>` inside a `<p>` is.
A chunk's style can be a `Style`, of which it takes the `text_style`,
so the [utilities](../styles/utilities.md) that style a whole `Text` style a chunk the same way:

<!-- example: text_chunks.py:example -->

![Styled chunks](../assets/text-chunks.svg)

The second `Text` is bold, so the chunk that shouldn't be merges `text_not_bold` over it.

A chunk ignores the rest of a `Style`, such as padding or a border, as a browser ignores a `<span>`'s width,
so put those on the `Text` or a `Div` around it.
A chunk's style can also be a `CellStyle`, which is what `Chunk.style` holds either way.

## Wide Characters

A `Text` measures, wraps and paints its content by grapheme cluster,
the unit a reader sees as one character,
so an accented letter written with a combining mark
or an emoji joined from several (`👩‍💻`) stays whole.

Counterweight measures each cluster with [wcwidth](https://github.com/jquast/wcwidth)'s `wcswidth`.
Most clusters take one terminal cell.
CJK characters, most emoji and flags take two,
and zero-width characters (zero-width spaces and joiners, bidirectional marks) take none and aren't drawn.
No cluster takes more than two,
which matches terminals that draw a cluster as one unit, such as Ghostty, foot and Windows Terminal.
Terminals that add up the widths of a cluster's code points instead
draw some clusters wider, such as a joined emoji as its separate parts,
and text after one is drawn to the right of where layout put it.

A two-cell cluster is never split across lines or cut in half.
When one would cross the right edge of its `Text`,
it moves to the next line if the text wraps,
or overflows the box with the rest of its line if it doesn't.
Where a [clip](../layout/clipping.md) cuts across one, it is left out, with a space in its place.

## Control Characters

Newlines (`\n` and `\r\n`) start a new line.
Every other control character, such as tab or escape,
is drawn as a symbol (`␉`, `␛`) rather than written to the terminal,
where it would run as a command instead of drawing anything.

## API

::: counterweight.elements.Text

::: counterweight.elements.Chunk
