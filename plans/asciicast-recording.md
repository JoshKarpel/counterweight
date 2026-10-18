# Plan: Recording Apps as Asciicasts

Artifact: https://claude.ai/code/artifact/e42539fa-5909-4c7c-8207-dce393b9476c

This plan lets an app record itself as an
[asciicast v3](https://docs.asciinema.org/manual/asciicast/v3/) file,
the format [asciinema-player](https://docs.asciinema.org/manual/player/) plays back,
whether it runs on a terminal or headless under an autopilot.
It adds two autopilot steps that wait, `Wait` and `WaitFor`, so an autopilot can let real work finish,
and a `Marker` control that marks chapters in a recording.
It makes the app's clock one of exactly two, the system's or a frozen one that only the autopilot moves.
It ends with the docs showing recordings of examples beside their screenshots.
It doesn't cover recording a program the app hands the terminal to while suspended,
or a CLI command that records an app.

## The question

How do we record what an app shows, with timing, without a separate recorder,
and with timing an autopilot controls instead of the wall clock?

The render loop already has both halves.
Each frame is one string of terminal instructions,
`synchronized(CLEAR_SCREEN? + paint_to_instructions(diff))` (`app.py`),
which is exactly the data of an asciicast `o` (output) event,
and headless mode builds it already and throws it away.
The time comes from `read_clock()`: the app's clock, moved on by every `AdvanceClock`.
Timestamping events with that one reading covers both uses:

| Clock | Where it comes from | What the recording's timing is |
| --- | --- | --- |
| `SystemClock()` (the default) | headful use, or an autopilot that waits on real work | real time: the app records itself, with no `asciinema rec` |
| `FrozenClock(start)` | a scripted autopilot | the `AdvanceClock`s, and the real time its waits take: a 10-minute timer records in milliseconds, the same on every run unless it waits |

## How the web does it

Browsers don't record themselves as a replayable stream;
the closest analogs are [rrweb](https://github.com/rrweb-io/rrweb), which records DOM mutations with timestamps,
and Playwright's [video](https://playwright.dev/docs/videos) and [trace](https://playwright.dev/docs/trace-viewer) recording.
Two of their answers carry over:

- **rrweb records changes, not frames.**
  An asciicast's `o` events are the same idea in a terminal,
  and counterweight's frames are already diffs of the previous paint.
- **Playwright runs on real time and waits on conditions.**
  [`page.waitForTimeout`](https://playwright.dev/docs/api/class-page#page-wait-for-timeout) exists,
  but its docs steer tests toward waiting for a condition
  ([`expect(locator).toBeVisible()`](https://playwright.dev/docs/test-assertions), `waitForSelector`).
  That's the split between `Wait` and `WaitFor` below.

Where counterweight differs: Playwright can't fake time in a recording,
and its clock mocking ([`page.clock`](https://playwright.dev/docs/clock)) is separate from its video.
Counterweight's recording reads the app's clock, so a frozen clock makes the recording's time fake too.

`page.clock` is also the model for the clocks themselves.
A test gets real time, or a fake clock it controls:
`pauseAt` stops time, `fastForward` jumps it, and `resume` lets it flow in real time again.
Sinon's and Jest's fake timers offer the same two modes, and none of them take an arbitrary time source.
`AdvanceClock` is counterweight's `fastForward`,
and a frozen clock runs in real time while the autopilot waits, as if each wait were a `resume` and a pause.

## Public API

### `Recording`

```python
@dataclass(frozen=True, slots=True)
class Recording:
    path: Path
    title: str | None = None
    idle_time_limit: timedelta | None = None
    theme: Theme | None = None
    input: bool = False


await app(root(), recording=Recording(Path("demo.cast")))
```

- `app` gains `recording: Recording | None = None`, and records whether or not it's `headless`.
- `idle_time_limit` and `title` go in the header as the spec defines them.
- `theme` is the header's `term.theme` (`fg`, `bg`, and an 8- or 16-color palette).
  Colors the terminal decides (`TERMINAL_DEFAULT`, `IndexedColor`) follow the player's theme without it.
- `input` records `i` events (below), and defaults to `False`, as the spec asks of recorders,
  whether or not the app runs under an autopilot.
  Its docstring and the docs page warn, in a `!!! warning` admonition, why:
  in a headful session the recording captures everything typed, passwords and tokens included,
  in a file that's made to be shared.

### `Marker`

```python
Marker(label: str = "")
```

A control that records an `m` (marker) event, which asciinema-player shows as a chapter you can jump to.
It's a control, not only an autopilot step, so a handler can return it too,
such as an app marking each view the user opens.
Without a `Recording` it does nothing.

### `Wait` and `WaitFor`

```python
Wait(duration: timedelta)
WaitFor(condition: Callable[[Frame], bool], timeout: timedelta)
```

Autopilot steps, not controls: a handler has nothing to wait for, so the autopilot's type grows
to `AnyEvent | AnyControl | Wait | WaitFor`, named `AutopilotStep`, in a new `counterweight.autopilot` module.

- `Wait` holds the autopilot back for `duration` of real time, measured on the event loop's clock.
  The app keeps rendering and handling events meanwhile, so a subprocess's output arrives and paints.
  The app's time passes as it waits, with either clock (see below).
- `WaitFor` holds the autopilot back until `condition` is true of a rendered frame,
  checked after each render, and raises `AutopilotTimedOut` if `timeout` passes first.
  It's the one to reach for when waiting on work like a subprocess, as Playwright's docs recommend,
  since it doesn't race the work it waits for.
  The frame is the whole screen, not the diff: the render loop keeps the full paint it diffs against
  (`current_paint`), and `WaitFor` hands the condition a copy of it, as `Screenshot` does,
  so conditions can read it with `frame.text(ansi=False)`.
  A condition sees what's drawn and not app state, as Playwright's locators see the page and not the app's state.

### `SystemClock` and `FrozenClock`

```python
SystemClock(timezone: tzinfo = UTC)
FrozenClock(start: datetime)

type Clock = SystemClock | FrozenClock
```

`app`'s `clock` is one of two frozen dataclasses, not an arbitrary callable,
so the render loop knows what each means and computes a frozen clock's time itself.

- `SystemClock` reads the system's time in `timezone`, UTC unless it's given another,
  and ticks follow that zone, so an app that wants local midnight asks for its zone.
  Time passes on it as it really does, waits included.
- `FrozenClock` reads `start` (which must have a timezone) moved on by the `AdvanceClock`s
  and by the real time the autopilot has spent waiting:
  each `Wait` exactly its duration, however late the event loop wakes from it,
  and each `WaitFor` until its condition held.
  While a wait is in progress the clock runs in real time,
  so a component that reads it, such as a spinner, keeps moving while the work goes on.
  Each step of an autopilot picks its own kind of time:
  an `AdvanceClock` skips ahead, and a wait lets the time the work really takes pass.

Waiting brings real time into a frozen clock, so an autopilot that waits doesn't record the same thing on every run:
frames during a wait are timed by when the event loop wakes, and a `WaitFor` moves the clock by however long the work took.
The docstrings and the docs page warn about it, in a `!!! warning` admonition.

Pacing a scripted autopilot needs no new API:
[`more_itertools.intersperse`](https://more-itertools.readthedocs.io/en/stable/api.html#more_itertools.intersperse)
puts an `AdvanceClock` (or a `Wait`) between every step.

```python
typed = [*(KeyPressed(key=character) for character in "hello"), KeyPressed(key=Key.Enter)]
autopilot = intersperse(AdvanceClock(by=timedelta(milliseconds=300)), typed)
```

## What gets recorded

| Event | When | Data |
| --- | --- | --- |
| header | when the app starts | `term.cols`/`rows` from the starting size, `term.type` `xterm-256color`, `timestamp` from the clock's first wall reading, and `Recording`'s fields |
| `o` | each frame, the title, the bell, and the start of output control | the same instructions the terminal gets |
| `r` | `TerminalResized`, and resuming at a different size | `COLSxROWS` |
| `i` | each key press, paste and mouse event the app handles, if `Recording.input` | the event re-encoded by `input_encoding` |
| `m` | each `Marker`, and resuming from a suspension | the marker's label, or `suspended` |
| `x` | when the app stops | `0` after a quit, `1` after an error |

Decisions in that table:

- **Output is what the terminal gets.**
  The render loop's writes (frames, title, bell) go through one function
  that writes to the terminal unless headless and records if recording,
  so headless and headful record the same thing.
  The start of output control (alternate screen, cursor off, clear) becomes a constant
  that both `start_output_control` and the recording's first `o` event use.
- **Frames are diffs.**
  An `o` event is bytes for the player's terminal emulator to apply to the screen it already has,
  so the recording holds what the terminal gets: each frame's `diff_paint` runs,
  and every cell only where the render loop clears the screen (the first frame, a resize, a resume).
  A frame that changes one character records a cursor move, a style, and that character.
- **Input is re-encoded from events, not taken from raw bytes.**
  An autopilot has events and no bytes, and `input_encoding` turns events back into the bytes a terminal sends,
  so one path covers headful and autopilot input, and records what the app understood.
  The app's own modes (any-event SGR mouse tracking, bracketed paste) are the `Modes` it's encoded with.
  It's recorded where the render loop handles the event, at the time it does.
- **Suspensions are cut out.**
  While a suspended app hands the terminal to a shell or an editor, the recording can't see what that program draws.
  The recording pauses, and the time spent suspended is subtracted from every later timestamp,
  so playback goes straight from the frame before to the frame after,
  and a `suspended` marker at the cut shows where it is.

## Timing

Each event's time is the `monotonic` part of the render's `Instant`, as `read_clock()` gives it.
Intervals are rounded to milliseconds, as the official recorder does,
by rounding each event's absolute time and writing the difference from the previous rounded time,
so rounding can't drift over a long recording (the spec's error-diffusion note)
and the intervals of a frozen-clock recording are exactly its `AdvanceClock`s.

## Implementation

1. **Encoding** (`counterweight/asciicast.py`), pure:
   `Recording` and `Theme`, the header line, an event line, and the interval rounding.
2. **Writer**: opens `Recording.path` at start, writes lines as the render loop produces them,
   and closes it in the render loop's `finally`, after the `x` event.
   Writes are buffered and made on the loop to start;
   measure with the `cw-profile` workloads and move them to a background task, as the devlog's are,
   only if they show.
3. **Render loop**: the output function above, `r`/`i`/`m`/`x` events at their points,
   and the suspension cut.
4. **Autopilot steps** (`counterweight/autopilot.py`): `Wait`, `WaitFor`, `AutopilotStep`, `AutopilotTimedOut`.
   The loop's `for ap in chain(autopilot, repeat(None))` becomes a step that yields nothing while a wait is pending,
   and the queue's timeout wakes for the earliest of the next clock tick, the end of a `Wait`,
   and the timeout of a `WaitFor`.
   The autopilot keeps how long its waits have taken, which `read_clock()` hands the clock.
5. **Clocks** (`counterweight/clock.py`): `SystemClock`, `FrozenClock`, and a pure `reading(clock, waited)`
   that gives each one's time, with the system's clock ignoring `waited`, which real time has already passed.
6. **`Marker`** in `controls.py`, handled by recording an `m` event.

## Tests

- The header and event lines for each field and code, against the spec's examples.
- Interval rounding: a property test that the rounded intervals sum to the rounded total for any sequence of times.
- A frozen-clock autopilot with `AdvanceClock`s: the recording's intervals are exactly the advances.
- Output round trip: feeding a recording's `o` events into `Emulator` gives a screen whose text is the last frame's.
- Input round trip: a property test that a key press's recorded `i` data parses back to the same key press,
  and that a paste's and a mouse event's do.
- A resize records an `r`, a `Marker` an `m`, and quitting an `x` of `0`; an error records `x` of `1`.
- A `Marker` without a recording does nothing.
- A suspension's time is cut out of later timestamps, and a `suspended` marker is recorded at the cut,
  tested on the `Recorder` with an injected time source, since neither clock moves during a suspension handler.
- An autopilot recording with `input` left alone records no `i` events.
- `WaitFor` releases the autopilot on the first frame its condition holds for, and raises `AutopilotTimedOut` after its timeout.
- `WaitFor`'s condition sees the whole screen, including cells the last frame's diff didn't touch.
- `Wait` holds the autopilot while events keep being handled, using a short duration
  and asserting order (an event put during the wait is handled before the next step), not elapsed time.
- The time the autopilot has waited: a `Wait` counts no more than its duration however late it ends,
  a `WaitFor` counts until its condition held, and waits add up.
- A frozen clock runs while the autopilot waits: a component ticking every 10 ms reaches a count a `WaitFor` waits for,
  and a `Wait` moves a frozen-clock recording on by exactly its duration.
- `SystemClock` reads UTC unless given a timezone, and ignores the time waited;
  `FrozenClock` reads its start plus the time waited, and rejects a naive start.
- Coverage stays at 100%.

## Docs

- **A page, "Autopilot and Recording"**, since autopilot has no page of its own:
  driving an app with an autopilot, `FrozenClock` and `AdvanceClock`, `Wait` and `WaitFor`
  with the warning that waiting brings real time into a frozen clock,
  pacing with `intersperse`, `Recording` with the warning about `input`, and `Marker`.
- **Recordings of examples.**
  Example modules declare a `CASTS` list of `CastSpec(root, asset, dimensions, steps)` beside `SCREENSHOTS`,
  and `docs.examples.generate_screenshots` renders them to `docs/assets/<asset>.cast`
  with the frozen clock, writing only what changed, so the pre-commit hook regenerates them without churn.
  Docs recordings pace their steps with `AdvanceClock` only: a wait would change the file on every run.
- **`use_clock`'s page** says the clock reads UTC, and shows `SystemClock(timezone=...)` for another zone.
  First candidates: the spinner, typing into the text input, the lap timer, and the tailing scroll area.
- **asciinema-player 3.17.0**, vendored into `docs/assets/vendor/` (its JS and CSS, version in the path)
  and loaded through `extra_javascript` and `extra_css`, so the docs build offline
  and depend on no CDN at view time.
  It needs 3.10.0 or later for v3 files.
- **A hook, `mkdocs_hooks/casts.py`**: a `<!-- cast: <asset> -->` line outside any code block
  becomes the player's element for `docs/assets/<asset>.cast`, and the build fails if the file doesn't exist,
  as the example hook does for a missing section.
- A changelog entry under `Added`.
