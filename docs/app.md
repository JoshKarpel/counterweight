# Running an App

`app` runs an application.
Give it the root component, already called with its arguments,
and run it on an event loop with `asyncio.run`:

```python
import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.elements import Text


@component
def root(name: str) -> Text:
    return Text(content=f"Hello, {name}!")


if __name__ == "__main__":
    asyncio.run(app(root("world")))
```

It switches the terminal to its alternate screen, reads input raw and turns on mouse reporting,
then renders the root and handles input until something returns [`Quit`][counterweight.controls.Quit],
which by default Ctrl+C does.
It restores the terminal before it returns,
and before an error raised in a component, a handler or an effect propagates out of it.

## Where it draws

`app`'s `viewport` says where on the terminal the app draws.
[`FullScreen()`][counterweight.FullScreen], the default, fills the alternate screen,
as `vim` or `htop` do, and leaves the main screen as it found it.
[`Inline()`][counterweight.Inline] draws in a region below the prompt, as tall as the root's content,
which leaves its last frame in the terminal when the app stops (see [Inline Apps](inline.md)).

## What else it takes

The rest of `app`'s parameters each belong to a part of the framework, with its own page:

| To | Pass | See |
| --- | --- | --- |
| Title the terminal window | `title` | [`SetTitle`][counterweight.controls.SetTitle] |
| Change what Ctrl+C and Ctrl+Z do, or give other keys defaults | `unclaimed_keys` | [Keys the terminal would act on](input-handling/events.md#keys-the-terminal-would-act-on) |
| Read the time in another time zone, or freeze it | `clock` | [`use_clock`](hooks/use_clock.md) |
| Drive it without a person, or without a terminal | `autopilot`, `headless`, `dimensions` | [Autopilot](autopilot.md#driving-an-app) |
| Record it as an asciicast | `recording` | [Recording](autopilot.md#recording) |
| Catch components that go stale | `check_purity` | [Performance](performance.md#how-do-i-catch-stale-output) |
| Let garbage collection run in the middle of a frame | `collect_garbage_between_frames` | [Performance](performance.md#when-not-to-pause-it) |
| See other libraries' debug logs in the devlog | `log_levels` | [The devlog](performance.md#the-devlog) |
| Match a font that isn't twice as tall as it is wide | `cell_aspect_ratio` | [Gradients](styles/gradients.md#what-cells-change) |
| Draw on a terminal other than standard input and output | `input_stream`, `output_stream` | [Running programs](terminals/programs.md) |
| Print to streams other than standard output and standard error | `stdout`, `stderr` | [Printing](inline.md#printing) |
| Leave `sys.stdout` and `sys.stderr` alone | `capture_output` | [Stray prints](inline.md#stray-prints) |

## Which version is running

`counterweight.__version__` is the version installed,
which `counterweight version` prints too.

## API

::: counterweight.app
::: counterweight.FullScreen
::: counterweight.Inline
::: counterweight.__version__
