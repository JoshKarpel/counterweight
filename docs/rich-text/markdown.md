# Markdown

`markdown` renders a Markdown document as a `Div` of elements,
which goes anywhere an element does.
It handles [CommonMark](https://commonmark.org/), with GitHub's tables and strikethrough.

```python
--8<-- "markdown_document.py:example"
```

![A rendered Markdown document](../assets/markdown-document.svg)

- Links and images are [hyperlinks](hyperlinks.md) to their destinations.
  An image is shown as its alt text, since a terminal can't show the image.
- Fenced code blocks are [highlighted](syntax-highlighting.md) as the language their info string names,
  or shown as written if it names none, or one Pygments doesn't know.
- Raw HTML is shown as written.

Rendering is cached by the source and the styles,
so a component can render the same document on every render without parsing it again.

`markdown` doesn't scroll: a document longer than the space it's given runs past the bottom of it.
The [Markdown viewer](https://github.com/JoshKarpel/counterweight/blob/main/examples/markdown_viewer.py) example
puts a tree of a directory's Markdown files beside the one it's showing.

## Styles

`MarkdownStyles` holds a `Style` for each kind of block and a `CellStyle` for each kind of inline span.
Pass the fields you want to change, and the rest keep their defaults:

```python
markdown(source, MarkdownStyles(heading_1=text_color("amber", 300), code_theme="monokai", block_gap=0))
```

## API

::: counterweight.markdown.markdown

::: counterweight.markdown.MarkdownStyles
