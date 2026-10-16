# `use_clock`

`use_clock` gives a component the time, so it can show a clock, an uptime, or a timer
while staying [pure](../components/index.md#keeping-components-pure).
A component that reads the time any other way, such as with `datetime.now()`,
keeps showing the time from whenever it last ran.

<!-- example: use_clock_status_bar.py:example -->

![Status bar](../assets/use-clock-status-bar.svg)

## Ticks

Each call reads the clock every `interval`.
A component takes a reading when it mounts,
and again on its first render after each new tick starts,
re-running then if nothing else made it.
Every render in between gets the same reading,
so re-running the component for any other reason doesn't change what it shows.

Ticks start at whole multiples of `interval` on the wall clock,
so `wall_clock` re-runs as the minute turns, along with `uptime`,
rather than a minute after the app started.
Components that take a reading in the same frame get the same one,
so two clocks on screen never disagree.

Each tick re-runs the components that read the clock and nothing else,
so call `use_clock` in the component that shows the time,
not in one that also renders things that don't change with it.
See [Performance](../performance.md#which-components-run-in-a-frame).

## Time zones

The app's clock reads the wall-clock time in UTC,
so an app shows the same time wherever it runs unless it asks for another zone.
Give `app` a [`SystemClock`][counterweight.clock.SystemClock] with a `timezone`
to read the time in that zone instead:

```python
await app(status_bar(), clock=SystemClock(timezone=ZoneInfo("America/New_York")))
```

Ticks follow the clock's zone too, so an `interval` of a day ticks at that zone's midnight.
Converting a UTC reading with `tick.now.astimezone(zone)` shows the right time,
but its ticks still start on UTC's boundaries:
a day-long tick at UTC's midnight rather than the zone's,
and an hour-long tick off the zone's hour where it's offset by a fraction of one, such as India's.

## Timing from an event

`since_mount` is how long the component has been mounted.
To time something from an event, such as a key press,
render a component that reads the clock and give it a new key when the event happens,
which remounts it and starts its `since_mount` again from zero:

<!-- example: use_clock_lap_timer.py:example -->

![Lap timer](../assets/use-clock-lap-timer.svg)

Each press of Space starts the next lap from zero:

<!-- cast: use-clock-lap-timer -->

A handler sees the reading from the latest tick,
so a time it records, such as the lap time when a lap ends, is up to one `interval` early.
Choose an `interval` as fine as the precision the time needs.
A timer that can be paused and resumed loses up to that much on each pause,
since it carries the time recorded at the pause into the next run.

## Why compute from elapsed time?

Compute whatever changes over time, such as an animation frame or a countdown,
from `since_mount` or `since_start`.
Don't keep a running total in state and add to it each tick:

```python
@component
def spinner() -> Text:
    frame, set_frame = use_state(0)

    async def step() -> None:
        while True:
            await sleep(0.1)
            set_frame(lambda frame: frame + 1)  # wrong: falls further behind each step

    use_effect(step, deps=())

    return Text(content="|/-\\"[frame % 4])
```

Each step counts a full interval, but takes longer:
`sleep` wakes up late, and a render and any other work run before the next step starts.
The total falls behind the real elapsed time by a little more each step, and the gap only grows.
Measured on an otherwise idle event loop, steps of 10 ms counted 2 seconds when 2.05 had passed.
Adding up the real time between steps instead fixes the drift,
but anything that misses a step or repeats one, such as an effect that restarts, still breaks the total.

Elapsed time from `use_clock` is the difference between two readings of a monotonic clock,
so a value computed from it can't drift, however long the component runs:

```python
@component
def spinner() -> Text:
    frame = use_clock(timedelta(milliseconds=100)).since_mount // timedelta(milliseconds=100)
    return Text(content="|/-\\"[frame % 4])
```

It also needs no state or effect, so a tick re-renders once instead of twice.

## Testing

Pass a [`FrozenClock`][counterweight.clock.FrozenClock] to `app` to fix the time,
and move it on with [`AdvanceClock`][counterweight.controls.AdvanceClock] in the autopilot,
so a test or a screenshot doesn't depend on when it runs or how long it takes:

```python
async def test_the_lap_timer_counts_from_the_last_lap() -> None:
    await app(
        lap_timer(),
        headless=True,
        clock=FrozenClock(datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC)),
        autopilot=[
            AdvanceClock(by=timedelta(seconds=75)),
            KeyPressed(key=Key.Space),
            AdvanceClock(by=timedelta(seconds=42)),
            Screenshot.to_file(Path("lap-timer.txt")),
            Quit(),
        ],
        check_purity=True,
    )
```

## API

::: counterweight.hooks.use_clock
::: counterweight.hooks.Tick
::: counterweight.clock.FrozenClock
::: counterweight.clock.SystemClock
::: counterweight.clock.Instant
