---
name: cw-profile
description: Performance profiling workflow for the counterweight project. Use when profiling the render loop, benchmarking a change, finding hotspots, investigating a performance regression, or comparing before and after runs. Covers the benchmark workloads in `benchmarks/`, profiling them with Tachyon (Python's sampling profiler), reading the report, and comparing runs.
---

# Counterweight Performance Profiling

The `benchmarks/` package holds deterministic workloads that run headless at a fixed size
for a fixed number of frames, so two runs of a workload do the same work frame for frame.
Compare runs against each other, before and after a change, on the same machine.

## Workloads

Run `uv run python -m benchmarks list` for the workloads and what each stresses.
Choose by what the change touches: a cache keyed on content does nothing for `canvas`,
reusing last frame's layout matters most for `dashboard`, and text measurement dominates
`agent` and `top`.

## Profile a run

```bash
just profile top                  # writes profiles/top.{bin,json,txt,html}
just profile top before --frames 300
```

The recipe runs the workload twice: once under Tachyon (`--blocking`), and once unprofiled
for frame times, since blocking sampling slows frames.
It then writes a flamegraph (`profiles/<name>.html`) and prints the report.
`profiles/<name>.txt` is the last frame as plain text: read it to confirm the workload drew
what you expect before trusting its numbers.

For frame times alone, without a profile: `uv run python -m benchmarks run top`.

## Read the report

`uv run python -m benchmarks report <name>` prints:

- **Frame times**: median, mean, P95 and max of the interval between root renders,
  which covers the whole loop (events, shadow tree, layout, paint, output, effects)
  and anything else the event loop ran in between, such as the devlog's sink task.
- **Stages**: samples by the function `counterweight.app.render_loop` called, by other asyncio
  task (`task ...`, such as without-logging's `capture.<locals>.run_sink`), and in the event
  loop itself, with each stage's share of the mean frame time.
  Stages come from the call stack, so splitting a stage into named functions inside
  `render_loop` is how to get a finer breakdown.
  `harness.py:...on_key` is the workload's own `step`, not framework time.
  Work moved off the render loop onto another task still costs frame time in these
  saturated runs; it only comes for free in an app with idle time between frames.
- **Self and inclusive samples** per function below each stage's root.
  Collapsed stacks name files by basename, so `styles.py:...` could be any `styles.py`.
  `<string>:__create_fn__...` frames are dataclass-generated methods (`__init__`, `__hash__`,
  `__eq__`); `<GC>` is garbage collection.

## Compare runs

```bash
just profile top before
# make the change
just profile top after
uv run python -m benchmarks compare before after
```

`compare` shows both runs' frame times and, when both were profiled, each stage's
ms/frame with the change between them. Repeat a run when a change is within a few percent:
frame times on a shared machine vary run to run.

For a visual diff, `uv run python -m profiling.sampling replay --diff-flamegraph
profiles/before.bin -o profiles/diff.html profiles/after.bin`.

## Record results

Add a section to `plans/performance-analysis-2026-03-07.md` with the `compare` tables
and the hotspots that moved, saying what changed between the runs.
