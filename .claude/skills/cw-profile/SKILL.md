---
name: cw-profile
description: Performance profiling workflow for the counterweight project. Use when profiling the app, analyzing render cycle timings, reading the devlog, interpreting Scalene CPU profiles, investigating performance regressions, or comparing results across runs. Covers running the profiler, parsing results, and writing findings to the performance plan.
---

# Counterweight Performance Profiling

Two complementary tools: **Scalene** (line-level CPU profiler) and the **structured devlog** (per-event render cycle timings). Use both together for a complete picture.

## Workflow

### 1. Run a profiling session

```bash
just profile profiling/canvas.py     # high-churn: all content changes every frame
just profile profiling/dashboard.py  # mostly-static: one frame counter changes, rest cached
```

Both run for up to 60 seconds under Scalene, then print a reduced CLI summary. The full profile is saved to `scalene-profile.json` in the project root.

- **canvas.py** — adversarial for caches: 4 random-walker canvases, ~1,800 cells changing every frame. Stresses raw paint throughput. Optimizations that rely on temporal locality (lru_cache, memoization) show no benefit here.
- **dashboard.py** — representative of typical apps: 12 static metric cards + 1 live frame counter. Most Text elements are stable between frames, so paint_text and paint_edge caches hit heavily. Use this to validate cache-based optimizations.

### 2. Analyze the devlog

The devlog is cleared each time the app starts. After a session:

```bash
uv run python3 .claude/skills/cw-profile/scripts/analyze_devlog.py --last 500
```

This fetches recent entries via `just devlog --json --last N`, computes mean/median/P95/max for each render sub-step, and shows `%cycle` so you can see where time is going at a glance.

Key events and what they mean:
- **Updated shadow tree** — running user component functions + framework reconciliation
- **— user_code** — time inside user `@component` functions only
- **— framework overhead** — reconciliation, hook bookkeeping (should be <0.1ms)
- **Calculated layout** — waxy/taffy flex layout computation
- **Generated new paint** — `paint_layout()` traversal, cell allocation
- **Healed borders** — border-joining fixup pass; `hint_cells` is how many cells were checked
- **Diffed new paint** — cell-by-cell comparison; `diff_cells` is how many changed
- **Generated instructions** — ANSI escape string construction
- **Wrote and flushed** — actual bytes sent to the terminal; `bytes` field shows size
- **Completed render cycle** — wall time for the full cycle; median → FPS (1000/median)

### 3. Analyze the Scalene profile

```bash
uv run python3 .claude/skills/cw-profile/scripts/analyze_scalene.py
```

Shows the hottest lines in counterweight source files with their CPU%. Use `--top N` and `--min-pct X` to adjust. The profile must exist at `scalene-profile.json` (produced by step 1).

### 4. Record results

Add a new run section to `plans/performance-analysis-2026-03-07.md` with the raw table from `analyze_devlog.py` and any notable Scalene hotspots. Note what changed since the previous run and whether it was an improvement or regression.

## Fixes

_(none yet)_
