"""
Hooks that give a component the behavior of a common control, such as editing text or scrolling,
and leave drawing it to the component, as [Headless UI](https://headlessui.com/)
and [React Aria](https://react-spectrum.adobe.com/react-aria/hooks.html) do for the web.
`counterweight.widgets` draws each of them one way.
"""

from counterweight.headless._scroll_area import ScrollArea
from counterweight.headless._scroll_area import ScrollAxis
from counterweight.headless._scroll_area import use_scroll_area
from counterweight.headless._terminal import EmbeddedTerminal
from counterweight.headless._terminal import use_terminal
from counterweight.headless._text_area import TextArea
from counterweight.headless._text_area import use_text_area
from counterweight.headless._text_input import TextInput
from counterweight.headless._text_input import use_text_input

__all__ = [
    "EmbeddedTerminal",
    "ScrollArea",
    "ScrollAxis",
    "TextArea",
    "TextInput",
    "use_scroll_area",
    "use_terminal",
    "use_text_area",
    "use_text_input",
]
