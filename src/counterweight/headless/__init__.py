"""
Hooks that give a component the behavior of a common control, such as editing text or scrolling,
and leave drawing it to the component, as [Headless UI](https://headlessui.com/)
and [React Aria](https://react-spectrum.adobe.com/react-aria/hooks.html) do for the web.
`counterweight.widgets` draws each of them one way.
"""

from counterweight.headless.scroll_area import ScrollArea, ScrollAxis, use_scroll_area
from counterweight.headless.text_area import TextArea, use_text_area
from counterweight.headless.text_input import TextInput, use_text_input

__all__ = [
    "ScrollArea",
    "ScrollAxis",
    "TextArea",
    "TextInput",
    "use_scroll_area",
    "use_text_area",
    "use_text_input",
]
