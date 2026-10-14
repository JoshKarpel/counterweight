# `Text`

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
