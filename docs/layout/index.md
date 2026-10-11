# Layout

These pages show how to get each layout effect,
with every technique that achieves it, shown as code beside its screenshot.
Where a technique has a well-known failure, the failure is shown too.

Each example labels its boxes with the styles that produced them.
The examples are components; they all assume these imports:

```python
import waxy

from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
```

`waxy` provides the values that styles are built from,
for the cases no utility covers.

To run one, pass the component to `counterweight.app.app`.

Start with [How layout sizes things](how-layout-sizes-things.md):
the defaults it describes explain most surprises in the other pages.
