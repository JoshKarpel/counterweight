"""
Render the style utilities reference from the utilities module itself.

`docs/styles/utilities.md` groups utilities into hand-written sections,
each with a `<!-- utilities: <glob> ... -->` marker naming its utilities,
and a `<!-- utilities-palette -->` marker for the color constants.
This hook replaces the markers with tables built from the live values,
and fails the build unless every public utility is claimed by exactly one marker,
so a newly generated utility can't be silently missing from the page.
"""

import dataclasses
import inspect
import re
from annotationlib import Format
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from fnmatch import fnmatchcase
from types import ModuleType
from typing import get_args

import waxy
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

from counterweight.styles import UNSET, CellStyle, Color, Style
from counterweight.styles import utilities as utilities_module

UTILITIES_MARKER = re.compile(r"^<!-- utilities: (?P<patterns>[^>]+?) -->$", re.MULTILINE)
PALETTE_MARKER = re.compile(r"^<!-- utilities-palette -->$", re.MULTILINE)


def public_utilities(module: ModuleType) -> dict[str, object]:
    """
    The `Style` and `Color` constants and the functions defined in `module`, in source order.

    Names the module only imports (`waxy`, `Style`) and its type aliases are not utilities.
    """
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and (isinstance(value, Style | Color) or (callable(value) and value.__module__ == module.__name__))
    }


def format_value(value: object) -> str:
    """A value as it appears in the Sets column: colors as hex, everything else as its `repr`."""
    return value.hex if isinstance(value, Color) else repr(value)


def describe_style(style: Style) -> list[str]:
    """One `field = value` line per field `style` sets, with nested fields as `parent.field`."""
    settings: list[str] = []
    for f in dataclasses.fields(style):
        if not f.init:
            continue
        value = getattr(style, f.name)
        match value:
            case waxy.Style():
                settings.extend(f"layout.{name} = {getattr(value, name)!r}" for name in sorted(value.fields_set))
            case CellStyle():
                settings.extend(
                    f"{f.name}.{inner.name} = {format_value(getattr(value, inner.name))}"
                    for inner in dataclasses.fields(value)
                    if inner.init and getattr(value, inner.name) is not UNSET
                )
            case _ if value is UNSET:
                continue
            case _:
                settings.append(f"{f.name} = {format_value(value)}")
    return settings


def summarize(function: Callable[..., object]) -> str:
    """The first paragraph of `function`'s docstring, on one line."""
    docstring = inspect.getdoc(function)
    if docstring is None:
        raise ValueError(f"Utility function {function.__name__} has no docstring to describe it with")
    return " ".join(docstring.split("\n\n")[0].splitlines())


def signature(function: Callable[..., object]) -> str:
    """`function`'s signature with its annotations as written in the source, so aliases like `Shade` survive."""
    return function.__name__ + inspect.signature(function, annotation_format=Format.STRING).format(
        quote_annotation_strings=False
    )


def constants_table(constants: Mapping[str, Style]) -> str:
    rows = [
        f"| `{name}` | {'<br>'.join(f'`{line}`' for line in describe_style(style)) or 'Nothing'} |"
        for name, style in constants.items()
    ]
    return "\n".join(["| Utility | Sets |", "| --- | --- |", *rows])


def functions_table(functions: Mapping[str, Callable[..., object]]) -> str:
    rows = [f"| `{signature(function)}` | {summarize(function)} |" for function in functions.values()]
    return "\n".join(["| Function | Description |", "| --- | --- |", *rows])


def utilities_tables(utilities: Mapping[str, object]) -> str:
    """A table of the constants among `utilities`, then a table of the functions, leaving out an empty one."""
    constants: dict[str, Style] = {}
    functions: dict[str, Callable[..., object]] = {}
    for name, value in utilities.items():
        match value:
            case Style():
                constants[name] = value
            case Color():
                raise ValueError(f"Color constant {name} belongs in the palette, not a utilities table")
            case _ if callable(value):
                functions[name] = value
            case _:
                raise TypeError(f"Utility {name} is neither a style, a color, nor a function: {value!r}")
    tables = [constants_table(constants)] if constants else []
    if functions:
        tables.append(functions_table(functions))
    return "\n\n".join(tables)


def palette_names(colors: Sequence[str], shades: Sequence[int]) -> list[list[str]]:
    """The color constant names, one row per color, one column per shade."""
    return [[f"{color}_{shade}" for shade in shades] for color in colors]


def palette_table(utilities: Mapping[str, object], colors: Sequence[str], shades: Sequence[int]) -> str:
    def swatch(name: str) -> str:
        color = utilities[name]
        if not isinstance(color, Color):
            raise TypeError(f"Palette entry {name} is not a Color: {color!r}")
        return f'<td><span class="swatch" style="background-color: {color.hex}" title="{name} {color.hex}"></span></td>'

    header = "<tr><th></th>" + "".join(f"<th>{shade}</th>" for shade in shades) + "</tr>"
    rows = [
        f"<tr><th>{color}</th>" + "".join(swatch(name) for name in names) + "</tr>"
        for color, names in zip(colors, palette_names(colors, shades), strict=True)
    ]
    return "\n".join(
        [
            '<div class="utility-palette">',
            '<table class="palette">',
            f"<thead>{header}</thead>",
            "<tbody>",
            *rows,
            "</tbody>",
            "</table>",
            "</div>",
        ]
    )


def render_utility_tables(
    markdown: str,
    utilities: Mapping[str, object],
    colors: Sequence[str],
    shades: Sequence[int],
) -> str:
    """
    Replace each utilities marker with tables of the utilities its globs match, and the palette marker with the palette.

    Markdown with neither marker is returned unchanged.
    Otherwise every utility must be claimed by exactly one marker, and every glob must match something.
    """
    if not (UTILITIES_MARKER.search(markdown) or PALETTE_MARKER.search(markdown)):
        return markdown

    claims: Counter[str] = Counter()

    def tables(match: re.Match[str]) -> str:
        patterns = match["patterns"].split()
        for pattern in patterns:
            if not any(fnmatchcase(name, pattern) for name in utilities):
                raise ValueError(f"Utilities pattern {pattern!r} matches nothing")
        matched = {
            name: value for name, value in utilities.items() if any(fnmatchcase(name, pattern) for pattern in patterns)
        }
        claims.update(matched.keys())
        return utilities_tables(matched)

    def palette(match: re.Match[str]) -> str:
        claims.update(name for row in palette_names(colors, shades) for name in row)
        return palette_table(utilities, colors, shades)

    rendered = PALETTE_MARKER.sub(palette, UTILITIES_MARKER.sub(tables, markdown))

    unclaimed = [name for name in utilities if name not in claims]
    repeated = [name for name, count in claims.items() if count > 1]
    if unclaimed or repeated:
        raise ValueError(
            "Every utility must appear in exactly one section. "
            f"Missing: {unclaimed or 'none'}. Repeated: {repeated or 'none'}."
        )

    return rendered


def on_page_markdown(markdown: str, /, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    return render_utility_tables(
        markdown,
        utilities=public_utilities(utilities_module),
        colors=get_args(utilities_module.ColorName),
        shades=get_args(utilities_module.Shade),
    )
