---
name: cw-profile
description: Performance profiling workflow for the counterweight project. Use when profiling the render loop or input parsing, benchmarking a change, finding hotspots, investigating a performance regression, or comparing before and after runs. Covers the benchmark workloads in `benchmarks/`, profiling them with Tachyon (Python's sampling profiler), reading the report, and comparing runs.
---

# Counterweight Performance Profiling

The `benchmarks/` package holds deterministic workloads that run headless at a fixed size
for a fixed number of frames, so two runs of a workload do the same work frame for frame.
Compare runs against each other, before and after a change, on the same machine.

## Workloads

Run `uv run python -m benchmarks list` for the workloads and what each stresses,
and `uv run python -m benchmarks show <workload>` to watch one run live in the terminal.
Choose by what the change touches: a cache keyed on content does nothing for `canvas`,
reusing last frame's layout matters most for `dashboard`, and text measurement dominates
`agent` and `top`. `dashboard-local` draws what `dashboard` does, but holds its changing state
in a leaf component rather than the root: compare the two to see what skipping components
whose state didn't change saves. Each `-memo` workload (`dashboard-memo`, `top-memo`,
`agent-memo`, `agent-markdown-memo`) draws what its twin does with the per-item component declared `memo`:
compare the pair to see what skipping components whose arguments didn't change saves.
`agent-markdown` streams Markdown shaped like a real coding agent's (short narration between tool calls,
and now and then a summary with lists, tables and code), rendered with `markdown` and `code_block`:
compare it with `agent` to see roughly what parsing and highlighting cost.
`agent-scrolled` is `agent` with its transcript scrolled back partway through the run, so it reads back
while messages stream in below and drop off above: compare it with `agent`, which follows the end,
to see what scroll anchoring costs.
`agent-typing` is `agent` with a `text_area` prompt that holds focus and takes one edit a frame while the transcript streams
(typing, Backspace, Ctrl+J, a paste, and Enter to send, which empties it), wrapping past its maximum height so it scrolls.
Each of its frames is two loop iterations, one that edits the prompt and one that streams,
so compare it with `agent` to see what a key press costs on a busy screen.
`document` types onto the end of a ~110 KB document drawn as one `Text` in a scroll container,
as a pager would draw a file, `document-lines` draws it as one `Text` per line, as `markdown` draws one per block,
and `document-text-area` types into it in a `text_area`, which wraps it itself and draws it as a few `Text`s:
use them to see what content scrolled out of view costs.
`devloop` is an `Inline` app that prints three log lines a frame above a small status bar:
use it to see what printing costs (rendering each print once, writing it above the region)
and what feeding the emulator an inline app keeps of its terminal costs.
`chat`, `tasks` and `picker` are `Inline` apps too, shaped like the ones people build:
a coding agent's reply streaming as Markdown into a region that grows, then printed above it;
parallel downloads, a row each, each printing a line as it finishes, so the region grows and shrinks;
and an `fzf --height` finder, a region of fixed size with nothing printed.
An inline app makes its emulator before its first frame, which shows in their stages as `handle_screen_size_change`.

## Profile a run

```bash
just profile top                  # writes profiles/top.{bin,json,txt,html}
just profile top before --frames 300
```

The recipe runs the workload twice: once under Tachyon (`--blocking`), and once unprofiled
for frame times, since blocking sampling slows frames.
It then writes a flamegraph (`profiles/<name>.html`) and prints the report.
`just profiles-serve [PORT]` serves `profiles/` over HTTP, to open flamegraphs from another machine.
`profiles/<name>.txt` is the last frame as plain text: read it to confirm the workload drew
what you expect before trusting its numbers.

For frame times alone, without a profile: `uv run python -m benchmarks run top`.

## Read the report

`uv run python -m benchmarks report <name>` prints:

- **Frame times**: median, mean, P95 and max of the interval between two autopilot key presses,
  as seen by a key handler on the root element,
  which covers the whole loop (events, shadow tree, layout, paint, output, effects)
  and anything else the event loop ran in between, such as the devlog's sink task.
- **Stages**: samples by the function `counterweight._app.render_loop` called, by other asyncio
  task (`task ...`, such as without-logging's `capture.<locals>.run_sink`), and in the event
  loop itself, with each stage's share of the mean frame time.
  Stages come from the call stack, so splitting a stage into named functions inside
  `render_loop` is how to get a finer breakdown.
  `harness.py:...on_input` is the workload's own `step`, not framework time,
  and it sits under `_routing.py:route_key`, so subtract it from that stage to see routing's own cost.
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

## Time input parsing

Parsing terminal input isn't part of any workload's frames, so it has its own command,
which times `parse_input` on whole reads (a key press, a read full of mouse motion, pasted text):

```bash
uv run python -m benchmarks parse --name before   # writes profiles/before.parsing.json
# make the change
uv run python -m benchmarks parse --name after
uv run python -m benchmarks compare before after
```

## Time emulator snapshots

Snapshotting the terminal emulator (`Emulator.snapshot`) isn't part of any workload either,
so `snapshot` times it on a 120x40 terminal after pieces of output (a scrolling line, plain, colored or wide,
a progress bar rewriting its row, and nothing), timing only the snapshots:

```bash
uv run python -m benchmarks snapshot --name before   # writes profiles/before.snapshots.json
# make the change
uv run python -m benchmarks snapshot --name after
uv run python -m benchmarks compare before after
```

## Record results

Add a section to `plans/performance-analysis.md`, numbered after the last run and with a
`**Date:**` line under its heading, with the `compare` tables and the hotspots that moved,
saying what changed between the runs.
