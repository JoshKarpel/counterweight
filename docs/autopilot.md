# Autopilot and Recording

An **autopilot** drives an app without a person at the keyboard:
it feeds the app events and controls, as tests and these docs' screenshots do.
A **recording** saves what an app draws, with its timing,
as an [asciicast](https://docs.asciinema.org/manual/asciicast/v3/) file that
[asciinema-player](https://docs.asciinema.org/manual/player/) and `asciinema play` play back,
whether a person or an autopilot is driving.
This page covers both, and how they combine to record a demo that comes out the same on every run.

## Driving an app

`app`'s `autopilot` is an iterable of events and controls, which the app handles in order, starting after its first frame.
Each step waits for what the last one set off, as a person's next key press would:
the renders it caused, and the effects those renders started, up to where each first waits on something.
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

`search` is the fruit search from [`use_text_input`](headless/use_text_input.md#using-the-hook).
The screenshot it writes is the frame after both keys, with the list narrowed to the fruits that contain "an":

![The search box holding "an", above banana, mango and orange](assets/autopilot-typed.svg)

## Controlling time

An app reads the time from its `clock`, the system's by default.
A [`FrozenClock`][counterweight.clock.FrozenClock] reads the same time until the autopilot moves it on,
with [`AdvanceClock`][counterweight.controls.AdvanceClock] or by [waiting](#waiting-for-real-work),
so an autopilot can show a minute of a clock-driven app in milliseconds,
and show the same thing on every run.
To pace an autopilot, put an `AdvanceClock` between its steps,
as [`paced`][counterweight.autopilot.paced] does,
which also holds on the last step, so a recording that loops lingers where it ends:

```python
typed = [KeyPressed(key=character) for character in "mango"]

await app(
    search(),
    headless=True,
    dimensions=(30, 8),
    clock=FrozenClock(datetime(2026, 3, 14, tzinfo=UTC)),
    autopilot=[*paced(typed, every=timedelta(milliseconds=300)), Quit()],
)
```

Its [recording](#recording) plays a key every 300 milliseconds,
though the autopilot ran in only as long as the app took to render:

<!-- cast: autopilot-mango -->

## Waiting for real work

An autopilot runs ahead of anything the app does in the background,
such as an effect waiting on a subprocess or a [command](terminals/commands.md),
since it hands the app its next step once the renders the last one caused are painted,
not once the work they started is done.
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

Both wait in real time, and a `FrozenClock` runs in real time while they do,
so a component that reads the clock, such as a spinner, keeps moving while the work goes on.
Each step of an autopilot can pick its own kind of time:
an `AdvanceClock` skips ahead at once, and a wait lets the time the work really takes pass.
A `Wait` moves the clock on by exactly its duration,
and a `WaitFor` by however long its condition took to hold.

!!! warning "Waiting brings real time into a frozen clock"

    An app under an autopilot that waits doesn't come out the same on every run, even with a `FrozenClock`.
    The frames it renders during a wait are timed by when the event loop wakes,
    and a `WaitFor` moves the clock on by however long the work took,
    which shifts everything the app shows of the time from then on.
    For screenshots and recordings that must not change between runs,
    such as ones checked into a repository, pace the autopilot with `AdvanceClock` alone.

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
With a `FrozenClock` and an autopilot, its timing is the autopilot's `AdvanceClock`s and waits,
so with no waits it records as fast as the app renders and comes out the same on every run,
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
This demo of the fruit search starts each chapter with a marker, and pauses between its keys:

<!-- example: autopilot_search.py:chapters -->

<!-- cast: autopilot-chapters -->

Notice the chapters on the player's progress bar, one for each marker, which jump to the start of their step.

## API

::: counterweight.autopilot.AutopilotStep
::: counterweight.autopilot.Wait
::: counterweight.autopilot.WaitFor
::: counterweight.autopilot.AutopilotTimedOut
::: counterweight.autopilot.paced
::: counterweight.asciicast.Recording
::: counterweight.asciicast.Theme
