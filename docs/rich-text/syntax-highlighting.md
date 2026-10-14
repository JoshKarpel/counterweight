# Syntax Highlighting

`code_block` highlights source code with [Pygments](https://pygments.org/),
in any of the [languages it knows](https://pygments.org/languages/),
and draws it on its theme's background.

```python
--8<-- "syntax_highlighting.py:example"
```

![Syntax highlighting in three themes](../assets/syntax-highlighting.svg)

A theme is the name of any [Pygments style](https://pygments.org/styles/),
or a `pygments.style.Style` subclass, which is how to define your own.

`code_block` is as wide as its longest line, as an HTML `pre` is.
To scroll lines wider than the space it's given, put it in a [scroll container](../layout/scrolling.md)
with `overflow_x_scroll` and [`scroll_on_wheel`](../input-handling/handlers.md#scrolling),
as [`markdown`](markdown.md#wide-code-and-tables) does,
so a sideways wheel, or the wheel with Shift held, scrolls it:

```python
Div(style=overflow_x_scroll, on_input=scroll_on_wheel(), children=(code_block(source, "python"),))
```

To lay the code out yourself, `highlight` returns its chunks,
to put in a `Text` with whatever else you like,
and `code_style` the background and text color to draw them on.

Highlighting is cached by its arguments,
so a component can highlight the same code on every render without lexing it again.
Tabs are expanded, to four columns unless `tab_size` says otherwise.

## API

::: counterweight.highlighting
    options:
      members:
        - highlight
        - code_block
        - code_style
        - CodeTheme
        - DEFAULT_CODE_THEME
