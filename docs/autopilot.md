# Autopilot and Recording

An **autopilot** drives an app without a person at the keyboard:
it feeds the app events and controls, as tests and these docs' screenshots do.
A **recording** saves what an app draws, with its timing,
as an [asciicast](https://docs.asciinema.org/manual/asciicast/v3/) file that
[asciinema-player](https://docs.asciinema.org/manual/player/) and `asciinema play` play back,
whether a person or an autopilot is driving.
This page covers both, and how they combine to record a demo that comes out the same on every run.

## Driving an app

`app`'s `autopilot` is an iterable of events and controls, which the app handles in order, one per render,
starting after its first frame.
It doesn't quit the app when it runs out, so end it with `Quit()`.
With `headless=True` the app neither reads the terminal nor draws on it,
and `dimensions` gives it a screen size:

```python
await app(
    search(),
    headless=True,
    dimensions=(30, 8),
    autopilot=[
        KeyPressed(key="a"),
        KeyPressed(key="n"),
        Screenshot.to_file(Path("typed.svg")),
        Quit(),
    ],
)
```

## Controlling time

An app reads the time from its `clock`, the system's by default.
A [`frozen_clock`][counterweight.clock.frozen_clock] reads the same time until
[`AdvanceClock`][counterweight.controls.AdvanceClock] moves it on,
so an autopilot can show a minute of a clock-driven app in milliseconds,
and show the same thing on every run.
To pace an autopilot, put an `AdvanceClock` between its steps with
[`more_itertools.intersperse`](https://more-itertools.readthedocs.io/en/stable/api.html#more_itertools.intersperse):

```python
typed = [KeyPressed(key=character) for character in "mango"]

await app(
    search(),
    headless=True,
    dimensions=(30, 8),
    clock=frozen_clock(datetime(2026, 3, 14, tzinfo=UTC)),
    autopilot=[*intersperse(AdvanceClock(by=timedelta(milliseconds=300)), typed), Quit()],
)
```

## Waiting for real work

An autopilot runs ahead of anything the app does in the background,
such as an effect waiting on a subprocess or a [command](terminals/commands.md),
since it hands the app its next step as soon as the last one has rendered.
Two steps hold it back while the app keeps handling events and rendering:

- [`WaitFor`][counterweight.autopilot.WaitFor] waits until a condition is true of the frame on screen,
  and fails with `AutopilotTimedOut` if it's still false after its timeout.
  It's the one to reach for, as [Playwright's assertions](https://playwright.dev/docs/test-assertions) are,
  since it waits exactly as long as the work takes.
- [`Wait`][counterweight.autopilot.Wait] waits for a duration of real time.

```python
await app(
    test_runner(),
    headless=True,
    dimensions=(60, 20),
    autopilot=[
        KeyPressed(key="r"),
        WaitFor(lambda frame: "passed" in frame.text(ansi=False), timeout=timedelta(seconds=30)),
        Screenshot.to_file(Path("passed.svg")),
        Quit(),
    ],
)
```

Both wait in real time, measured on the event loop's clock rather than the app's:
with a `frozen_clock` the app's time stands still while the autopilot waits,
and only `AdvanceClock` moves it.

## Recording

Pass `app` a [`Recording`][counterweight.asciicast.Recording] to record it to a file:

```python
await app(search(), recording=Recording(Path("search.cast"), title="Search"))
```

The recording holds what the app draws on its terminal, as it draws it:
the first frame in full, and each later frame as the cells that changed,
which a player applies to the screen it already shows, as a terminal does.
Each frame is timed by the app's clock.
With the system's clock, run the app on a terminal and use it,
and it records itself, with no `asciinema rec` around it.
With a `frozen_clock` and an autopilot, its timing is the autopilot's `AdvanceClock`s,
so it records as fast as the app renders and comes out the same on every run,
as this one, from the [spinner recipe](cookbook/spinners.md), does:

<!-- cast: spinner -->

The recording also holds the screen's size when it changes,
and how the app exited: `0` once it quits, and `1` if it stops with an error.
While the app is [suspended](input-handling/controls.md), the recording can't see what the program it hands the terminal to draws,
so the time it spends suspended is cut out, and a `suspended` marker shows where.

!!! warning "Recording input records everything typed"

    `Recording(input=True)` records every key press, paste and mouse event the app handles,
    which asciinema-player can show as they're typed (its `keystrokeOverlay` option).
    That includes passwords and tokens typed into the app, in a file that's made to be shared,
    so it's off by default, under an autopilot too.
    Turn it on when you know what will be typed, as for an autopilot's demo.

## Marking chapters

The [`Marker`][counterweight.controls.Marker] control marks a point in the recording with a label,
which asciinema-player shows on its progress bar as a chapter to jump to.
An autopilot can mark each step of a demo, and a handler can return one too,
such as to mark each view the user opens.
An app that isn't recording ignores it.

## API

::: counterweight.autopilot.AutopilotStep
::: counterweight.autopilot.Wait
::: counterweight.autopilot.WaitFor
::: counterweight.autopilot.AutopilotTimedOut
::: counterweight.asciicast.Recording
::: counterweight.asciicast.Theme
