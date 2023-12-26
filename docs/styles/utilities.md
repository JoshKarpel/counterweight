# Utilities

To avoid the tedium of writing out styles explicitly over and over,
Counterweight provides a variety of [Tailwind-inspired](https://tailwindcss.com/) "utility styles".
These utilities are pre-defined styles that can be combined to form more complex styles.

The utilities can be imported from the `counterweight.styles.utilities` module.
We recommend a `*` import for ease of use:

```python
from counterweight.styles.utilities import *
```

Each utility is a pre-defined `Style` specifying just a small set of properties.
For example, `border_rose_200` is defined as:
```python
from counterweight.styles import Style, Border, Color, CellStyle

border_rose_200 = Style(
    border=Border(style=CellStyle(foreground=Color.from_hex("#fecdd3")))
)
```

Since they are normal `Style`s, they can be combined to form more complex styles using the `|` operator.
Here we make a new `Style` for a `rose_200`-colored heavy border on the top and bottom sides:

```python
from counterweight.styles.utilities import *

border_heavy_top_bottom_rose_200 = border_heavy | border_rose_200 | border_top_bottom
```

Actually giving a name to the new style is optional.
We can also use the expression `border_heavy | border_rose_200 | border_top_bottom` directly in our component:

```python
from counterweight.styles.utilities import *
from counterweight.components import component
from counterweight.elements import Text


@component
def my_component() -> Text:
    return Text(
        content="Hello, world!",
        style=border_heavy | border_rose_200 | border_top_bottom,
    )
```

!!! tip "Performance Considerations"

    If you have an expression like `border_heavy | border_rose_200 | border_top_bottom` in your component,
    it will be evaluated every time the component is rendered.
    Merging styles with `|` does take some time, though it is aggressively cached inside the framework.
    If you find that this is causing performance issues,
    you should create the style just once,
    ideally outside your component (i.e., at module scope),
    so that it runs only once.
