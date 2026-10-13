# Performance Analysis — `profiling/canvas.py`

**Date:** 2026-03-07

**Workload:** 4 × `random_walkers` canvases, each 30×30 pixels rendered as half-block chars
(30×15 Chunks per canvas = 450 Chunks × 4 = ~1,800 Chunks total), all walkers moving every frame.
**Dataset:** 500 log lines, 50 complete render cycles, ~0.82 s wall time.
**Result:** Median cycle 15.7 ms (~63.6 FPS).

> **Workload bias warning:** The canvas workload is maximally dynamic — content changes on every
> frame, so optimizations that assume temporal locality (caches, memoization) get no hits and only
> pay overhead. Most real apps (dashboards, menus, forms) have mostly-stable content between frames
> and would benefit more from those optimizations. The canvas is a useful stress test for raw
> throughput but flatters different optimizations than a typical app would.

---

## Render Cycle Breakdown

| Sub-step | Mean (ms) | % of cycle |
|---|---|---|
| Generated new paint | 5.31 | 32.7% |
| Calculated layout | 4.08 | 25.1% |
| Updated shadow tree | 2.72 | 16.7% |
| — of which: user component code | ~2.50 | ~15.4% |
| — of which: framework reconciliation | ~0.06 | ~0.4% |
| Diffed new paint from current paint | 1.24 | 7.6% |
| Wrote and flushed to output | 0.46 | 2.8% |
| Healed borders | 0.41 | 2.5% |
| Generated instructions from diff | 0.19 | 1.2% |
| Reconciled effects | 0.02 | 0.1% |
| Unaccounted overhead | 1.83 | 11.2% |

**Key insight from `user_code_ns`:** framework reconciliation overhead in the shadow tree
update is ~63µs at the median — effectively nothing. The dominant 2.5ms cost is user
component functions running. This changes the priority of memoization vs. other work.

---

## Optimization Opportunities

The opportunities this analysis found, numbered as the runs below cite them:

- **#1 Skip layout when the tree is unchanged.** Partly done.
  `LayoutTree` keeps taffy's tree across frames, so taffy reuses its cached layout for unchanged nodes (run 10),
  and only the `layout_changes` are applied to it (run 18).
  `LayoutTree.compute` still calls `compute_layout` and reads every node's layout back on every frame,
  even with no changes: 0.12 ms of `dashboard-local`'s 0.73 ms mean frame, where only one counter changes (run 18).
- **#2 Memoize stable component subtrees.** Done: `update_shadow` re-runs only the components that have to,
  and `@component(memo=True)` skips one whose arguments are unchanged (run 18).
- **#3 Incremental paint for `Text` nodes.** Done in user code, in `counterweight.utils.canvas` (run 3).
- **#4 Lazy initializers in `use_state`.** Done in the canvas workload (run 2).
- **#5a–5c Cache `paint_edge()` and `paint_text()`, and batch adjacent cells in `paint_to_instructions()`.**
  Done (run 4). Run 12 replaced the caches with cached region fills and text rows.
- **#6 Narrow the border-healing hints to corners.** Done (runs 6 and 7).
- **#7 Sparse paint.** Reverted after run 6.
  Run 12's screen-sized `Paint` addresses the same cost: `diff_paint` skips rows that compare equal.

---

## Metrics Reference

### Run 1 (before `user_code_ns`)

**Date:** 2026-03-07

| Event | Count | Mean | Median | P95 | Max |
|---|---|---|---|---|---|
| Handled events | 49 | 0.007 ms | 0.006 ms | 0.010 ms | 0.010 ms |
| Updated shadow tree | 49 | 2.718 ms | 2.654 ms | 3.316 ms | 3.750 ms |
| Calculated layout | 49 | 4.077 ms | 4.003 ms | 4.704 ms | 5.211 ms |
| Generated new paint | 50 | 5.313 ms | 5.246 ms | 6.071 ms | 7.137 ms |
| Healed borders | 50 | 0.406 ms | 0.390 ms | 0.508 ms | 0.685 ms |
| Diffed new paint | 50 | 1.238 ms | 1.199 ms | 1.481 ms | 1.813 ms |
| Generated instructions | 50 | 0.193 ms | 0.178 ms | 0.328 ms | 0.369 ms |
| Wrote and flushed | 50 | 0.458 ms | 0.458 ms | 0.750 ms | 0.853 ms |
| Reconciled effects | 50 | 0.023 ms | 0.021 ms | 0.036 ms | 0.046 ms |
| **Completed render cycle** | **50** | **16.261 ms** | — | **17.696 ms** | **18.311 ms** |

### Run 2 (with `user_code_ns`, lazy `use_state`)

**Date:** 2026-03-07

| Event | Count | Mean | Median | P95 | Max |
|---|---|---|---|---|---|
| Handled events | 49 | 0.006 ms | 0.006 ms | 0.010 ms | 0.012 ms |
| Updated shadow tree | 49 | 2.771 ms | 2.547 ms | 3.421 ms | 7.897 ms |
| — user_code_ns | 49 | 2.596 ms | 2.485 ms | 3.147 ms | 4.462 ms |
| — framework overhead | 49 | 0.175 ms | 0.063 ms | 0.107 ms | 5.178 ms |
| Calculated layout | 49 | 4.538 ms | 4.107 ms | 6.076 ms | 15.646 ms |
| Generated new paint | 50 | 5.363 ms | 5.173 ms | 5.879 ms | 9.927 ms |
| Healed borders | 50 | 0.397 ms | 0.373 ms | 0.455 ms | 0.916 ms |
| Diffed new paint | 50 | 1.278 ms | 1.161 ms | 1.566 ms | 4.068 ms |
| Generated instructions | 50 | 0.191 ms | 0.175 ms | 0.292 ms | 0.391 ms |
| Wrote and flushed | 50 | 0.457 ms | 0.494 ms | 0.677 ms | 0.865 ms |
| Reconciled effects | 50 | 0.021 ms | 0.019 ms | 0.031 ms | 0.072 ms |
| **Completed render cycle** | **50** | **16.782 ms** | **15.713 ms** | **21.621 ms** | **33.306 ms** |

Run 2 high outliers (layout 15.6ms, cycle 33.3ms) are isolated GC/OS scheduling spikes, not regressions.
Steady-state performance is unchanged: median ~15.7ms (~63.6 FPS).

### Run 3 (`@flyweight` on `CellStyle`, `_canvas_chunk` cache, `NEWLINE` constant, `canvas` in utils)

**Date:** 2026-03-07

| Event | Count | Mean | Median | P95 | Max |
|---|---|---|---|---|---|
| Updated shadow tree | 49 | 1.041 ms | 0.881 ms | 1.870 ms | 3.723 ms |
| — user_code_ns | 49 | 0.970 ms | 0.818 ms | 1.793 ms | 3.364 ms |
| — framework overhead | 49 | 0.071 ms | 0.058 ms | 0.125 ms | 0.359 ms |
| Calculated layout | 49 | 3.813 ms | 3.681 ms | 5.127 ms | 6.326 ms |
| Generated new paint | 50 | 5.234 ms | 5.121 ms | 6.277 ms | 7.379 ms |
| Healed borders | 50 | 0.395 ms | 0.380 ms | 0.471 ms | 0.616 ms |
| Diffed new paint | 50 | 1.299 ms | 1.166 ms | 1.689 ms | 3.125 ms |
| Generated instructions | 50 | 0.211 ms | 0.194 ms | 0.358 ms | 0.382 ms |
| Wrote and flushed | 50 | 0.409 ms | 0.420 ms | 0.596 ms | 0.820 ms |
| Reconciled effects | 50 | 0.020 ms | 0.020 ms | 0.029 ms | 0.034 ms |
| **Completed render cycle** | **50** | **14.188 ms** | **13.740 ms** | **17.275 ms** | **19.502 ms** |

Shadow tree: **-67% median** vs run 2 (2.485ms → 0.818ms user_code). Bottleneck fully shifts to paint (37%) and layout (27%).
Overall cycle: **-13% median** (15.7ms → 13.7ms, ~73 FPS median).

### Run 4 (`paint_edge` cache, `paint_text` cache, batched `paint_to_instructions`)

**Date:** 2026-03-07

| Event | Count | Mean | Median | P95 | Max |
|---|---|---|---|---|---|
| Updated shadow tree | 99 | 1.117 ms | 1.003 ms | 1.954 ms | 2.783 ms |
| — user_code_ns | 99 | 1.040 ms | 0.940 ms | 1.713 ms | 2.574 ms |
| — framework overhead | 99 | 0.077 ms | 0.062 ms | 0.167 ms | 0.347 ms |
| Calculated layout | 99 | 4.114 ms | 3.858 ms | 6.094 ms | 6.994 ms |
| Generated new paint | 100 | 6.105 ms | 5.684 ms | 8.820 ms | 12.511 ms |
| Healed borders | 100 | 0.453 ms | 0.391 ms | 0.846 ms | 1.284 ms |
| Diffed new paint | 100 | 1.352 ms | 1.232 ms | 2.327 ms | 2.991 ms |
| Generated instructions | 100 | 1.672 ms | 0.353 ms | 0.589 ms | 128.960 ms |
| Wrote and flushed | 100 | 0.443 ms | 0.490 ms | 0.733 ms | 1.093 ms |
| Reconciled effects | 100 | 0.025 ms | 0.022 ms | 0.041 ms | 0.078 ms |
| **Completed render cycle** | **100** | **17.387 ms** | **15.983 ms** | **19.540 ms** | **145.362 ms** |

Extra metrics (run 4):
- `hint_cells` (border heal): constant 279 every cycle
- `diff_cells` (border heal): constant 5 every cycle
- `diff_cells` (paint diff): mean 207, median 207
- `bytes` written: mean ~8,620 B, median ~8,602 B
- `num_events`: mean 4.1 per cycle
- `num_active_effects`: constant 5

**Result: net regression on the canvas workload (+2.2ms median, 13.7ms → 16.0ms).** The 128ms
instructions spike is a one-time outlier (likely first-call sort). All three changes hurt this workload:

- `paint_text` cache: canvas `Text` content changes every frame → constant cache misses → lru_cache
  lookup overhead with no benefit.
- `paint_edge` cache: probably negligible effect either way (margin/padding rects are static,
  but the work per call is also small).
- Instruction batching (`sorted()` call): adds ~0.175ms/cycle median for the sort overhead on
  ~200 diff cells every frame.

These optimizations benefit static-text workloads (menus, forms, dashboards with stable content)
but are a regression for high-churn workloads like canvas. The right fix for canvas specifically
remains framework-side skip-layout (#1) or component memoization (#2).

Scalene hotspots (run 4, top lines by CPU%):
- `_utils.py:80–91` (flyweight `__new__`) — 3.38% combined, still dominant
- `paint.py:159` — `paint[Position(x, y)] = P(...)` — 0.61%
- `app.py:494` — `new_paint.get(pos, BLANK)` in diff loop — 0.48%
- `output.py:95` — `sorted(paint.items(), ...)` — 0.41% (new cost from batching)
- `layout.py:189` — cell append in wrap_cells — 0.55%

### Run 5 — `profiling/dashboard.py` (mostly-static workload)

**Date:** 2026-03-07

| Event | Count | Mean | Median | %cycle | P95 | Max |
|---|---|---|---|---|---|---|
| Updated shadow tree | 199 | 1.436 ms | 1.207 ms | 14.0% | 1.917 ms | 27.985 ms |
| — user_code | 199 | 1.304 ms | 1.089 ms | 12.6% | 1.723 ms | 27.798 ms |
| — framework overhead | 199 | 0.132 ms | 0.119 ms | 1.4% | 0.193 ms | 0.889 ms |
| Calculated layout | 199 | 1.066 ms | 0.978 ms | 11.3% | 1.746 ms | 2.736 ms |
| Generated new paint | 200 | 2.825 ms | 2.474 ms | 28.6% | 3.658 ms | 39.366 ms |
| Healed borders | 200 | 1.101 ms | 1.016 ms | 11.8% | 1.493 ms | 2.227 ms |
| Diffed new paint | 200 | 1.109 ms | 1.001 ms | 11.6% | 1.749 ms | 3.172 ms |
| Generated instructions | 200 | 0.013 ms | 0.011 ms | 0.1% | 0.023 ms | 0.093 ms |
| Wrote and flushed | 200 | 0.056 ms | 0.048 ms | 0.6% | 0.107 ms | 0.574 ms |
| Reconciled effects | 200 | 0.038 ms | 0.034 ms | 0.4% | 0.066 ms | 0.138 ms |
| **Completed render cycle** | **200** | **9.427 ms** | **8.642 ms** | — | **12.855 ms** | **45.571 ms** |

Extra metrics (run 5):
- `hint_cells` (border heal): constant 784 every cycle (12 bordered metric cards vs canvas's 4)
- `diff_cells` (border heal): constant 17 every cycle
- `diff_cells` (paint diff): mean 1.2, median 1 — only the frame counter changes
- `bytes` written: mean 47 B (vs canvas's 8,620 B)
- `num_events`: mean 1.0 per cycle
- `num_active_effects`: constant 2

**Result: 8.6ms median (~116 FPS).** Paint_text and paint_edge caches are doing real work —
paint generation drops to 2.47ms (vs canvas 5.68ms) for a workload with 24 static Text elements
and 1 changing one. Instructions + write are essentially free (0.01ms / 47B vs 0.35ms / 8.6KB).

Bottleneck breakdown shifts completely vs canvas:

| Bottleneck | Dashboard | Root cause |
|---|---|---|
| Generated new paint (29%) | 2.47 ms | Still dominant but 2× faster with cache hits |
| Shadow tree (14%) | 1.21 ms | 12 `metric_card` components re-run every frame with unchanged props — memoization (#2) would eliminate this |
| Border healing (12%) | 1.02 ms | 784 hints checked every frame to find 17 fixes — **larger than canvas** due to 12 bordered cards; hint-narrowing (#6) would make this near-zero |
| Diffed new paint (12%) | 1.00 ms | Full terminal scan to find 1 changed cell — cost is O(terminal size), not O(changes); dirty-region tracking would eliminate this |
| Layout (11%) | 0.98 ms | Runs every cycle even though nothing structural changed — skip-layout (#1) would eliminate this |

Scalene hotspots (run 5, top lines by CPU%):
- `app.py:494` — `new_paint.get(pos, BLANK)` in diff loop — 0.91% (most expensive single line)
- `border_healing.py:64` — `get_replacement_char()` — 0.84%
- `_utils.py:80–91` (flyweight `__new__`) — 1.87% combined
- `paint.py:65` — `bhh |= b` (border healing hint merge) — 0.67%
- `geometry.py:18–20` — `Position.from_point()` — 1.47% combined

### Run 6 — `profiling/canvas.py` (after #6 corner hints + #7 sparse paint; battery power)

**Date:** 2026-03-08

> **Clock-speed caveat:** recorded on battery — absolute times are ~1.8× slower than runs 1–4.
> Compare proportions only.

| Event | Count | Mean | Median | %cycle | P95 | Max |
|---|---|---|---|---|---|---|
| Updated shadow tree | 49 | 1.767 ms | 1.576 ms | 6.4% | 2.767 ms | 3.750 ms |
| — user_code | 49 | 1.639 ms | 1.472 ms | 6.0% | 2.619 ms | 3.545 ms |
| — framework overhead | 49 | 0.128 ms | 0.111 ms | 0.5% | 0.252 ms | 0.278 ms |
| Calculated layout | 49 | 6.744 ms | 6.479 ms | 26.4% | 8.835 ms | 9.478 ms |
| Generated new paint | 50 | 10.080 ms | 10.137 ms | 41.2% | 12.379 ms | 13.659 ms |
| Healed borders | 50 | 0.089 ms | 0.074 ms | 0.3% | 0.150 ms | 0.386 ms |
| Diffed new paint | 50 | 1.539 ms | 1.431 ms | 5.8% | 2.298 ms | 2.851 ms |
| Generated instructions | 50 | 0.593 ms | 0.530 ms | 2.2% | 1.004 ms | 1.039 ms |
| Wrote and flushed | 50 | 0.687 ms | 0.720 ms | 2.9% | 1.083 ms | 1.876 ms |
| Reconciled effects | 50 | 0.054 ms | 0.038 ms | 0.2% | 0.098 ms | 0.359 ms |
| **Completed render cycle** | **50** | **24.951 ms** | **24.583 ms** | — | **29.745 ms** | **30.216 ms** |

Extra metrics (run 6):
- `hint_cells` (border heal): constant 9 every cycle (was 279 in run 3 — **#6 working**)
- `diff_cells` (border heal): constant 5 every cycle
- `diff_cells` (paint diff): mean 207, median 207
- `bytes` written: mean ~8,628 B
- `num_events`: mean 4.1 per cycle
- `num_active_effects`: constant 5

**Bottleneck proportions vs run 3** (clock-speed-independent comparison):

| Sub-step | Run 3 % | Run 6 % | Δ | Driver |
|---|---|---|---|---|
| Generated new paint | 37.3% | 41.2% | +3.9% | New filter comprehension in `paint_layout` (paint.py:70 at 0.18%) adds overhead with no canvas benefit |
| Calculated layout | 26.8% | 26.4% | ≈ same | — |
| Diffed new paint | 8.5% | 5.8% | **−2.7%** | #7 sparse current_paint — fewer entries to scan |
| Shadow tree | 6.4% | 6.4% | same | — |
| Healed borders | 2.8% | **0.3%** | **−2.5%** | **#6 corner-only hints; hint_cells 279→9** |
| Write | 3.1% | 2.9% | same | — |
| Instructions | 1.4% | 2.2% | +0.8% | within noise |

**Result:** #6 (border healing) is a clean win. #7 (sparse paint) saves on the diff step but adds overhead
in paint generation — mixed on canvas (fully-dynamic), expected to help dashboard significantly.
Dominant bottleneck remains `Generated new paint` (41%) and `Layout` (26%).

Scalene hotspots (run 6, top lines by CPU%):
- `_utils.py:80–91` (flyweight `__new__`) — 1.20% + 1.13% + 0.66% = ~3% combined, still dominant
- `layout.py:189` — cell append in `wrap_cells` — 0.67%
- `paint.py:163` — `paint[Position(x, y)] = P(...)` in `_paint_text` — 0.57%
- `app.py:363` — `output_stream.flush()` — 0.52%
- `paint.py:70` — sparse filter comprehension — 0.18% **(new cost from #7)**
- `layout.py:79` — `_measure_text` — 0.24%

---

### Run 7 — `profiling/dashboard.py` (after #6 corner hints; sparse paint #7 reverted)

**Date:** 2026-03-08

| Event | Count | Mean | Median | %cycle | P95 | Max |
|---|---|---|---|---|---|---|
| Updated shadow tree | 49 | 1.200 ms | 1.105 ms | 16.6% | 1.625 ms | 2.865 ms |
| — user_code | 49 | 1.084 ms | 0.998 ms | 15.0% | 1.479 ms | 2.370 ms |
| — framework overhead | 49 | 0.116 ms | 0.103 ms | 1.5% | 0.171 ms | 0.495 ms |
| Calculated layout | 49 | 0.962 ms | 0.908 ms | 13.7% | 1.110 ms | 2.338 ms |
| Generated new paint | 50 | 2.159 ms | 2.115 ms | 31.8% | 2.537 ms | 2.687 ms |
| Healed borders | 50 | 0.089 ms | 0.075 ms | 1.1% | 0.264 ms | 0.331 ms |
| Diffed new paint | 50 | 0.981 ms | 0.943 ms | 14.2% | 1.292 ms | 1.367 ms |
| Generated instructions | 50 | 0.010 ms | 0.010 ms | 0.1% | 0.015 ms | 0.016 ms |
| Wrote and flushed | 50 | 0.042 ms | 0.042 ms | 0.6% | 0.057 ms | 0.075 ms |
| Reconciled effects | 50 | 0.032 ms | 0.030 ms | 0.5% | 0.041 ms | 0.116 ms |
| **Completed render cycle** | **50** | **6.908 ms** | **6.650 ms** | — | **8.451 ms** | **11.688 ms** |

Extra metrics (run 7):
- `hint_cells` (border heal): constant 21 every cycle (was 784 in run 5 — **#6 working**)
- `diff_cells` (border heal): constant 17 every cycle
- `diff_cells` (paint diff): mean 1.2, median 1 — only the frame counter changes
- `bytes` written: mean 49 B
- `num_events`: mean 1.0 per cycle
- `num_active_effects`: constant 2

**Result: 6.65ms median (~150 FPS), up from 8.64ms (~116 FPS) in run 5 — 23% improvement.**
Entire gain comes from #6 (corner-only border healing hints): 1.016ms → 0.075ms, hint_cells 784 → 21.
Border healing dropped from 11.8% to 1.1% of cycle.

Proportional bottlenecks (shadow/diff/layout absolute times unchanged; percentages rose only because border healing shrank):

| Bottleneck | Run 7 % | Run 7 median | Root cause |
|---|---|---|---|
| Generated new paint | 31.8% | 2.12 ms | Still dominant; paint_text/paint_edge caches hit for static cards |
| Shadow tree | 16.6% | 1.11 ms | 12 `metric_card` components re-run unchanged every frame — memoization (#2) |
| Diffed new paint | 14.2% | 0.94 ms | O(terminal size) scan to find 1 changed cell — sparse diff (#7) |
| Calculated layout | 13.7% | 0.91 ms | Runs every cycle with no structural changes — skip-layout (#1) |

Scalene hotspots (run 7, top lines by CPU%):
- `app.py:494` — `new_paint.get(pos, BLANK)` in diff loop — 1.02% **(most expensive single line; target of #7)**
- `_utils.py:80–91` (flyweight `__new__`) — ~2.5% combined
- `layout.py:79` — `_measure_text` — 0.86%
- `paint.py:58–65` — `paint_element` loop + `bhh |= b` — 1.36% combined
- `geometry.py:18–20` — `Position.from_point()` — 0.95% combined
- `styles/styles.py:22–28` — `merge_style_fragments` — ~0.78% combined

---

### Extra metrics (run 2)

**Date:** 2026-03-07
- `hint_cells` (border heal): constant 279 every cycle
- `diff_cells` (border heal): constant 5 every cycle
- `diff_cells` (paint diff): mean 203
- `bytes` written: mean ~8,544 B
- `num_events`: 4–5 per cycle
- `num_active_effects`: constant 5

---

### Run 8 — canvas.py — after `CellStyle.__hash__` caching

**Date:** 2026-03-08

**Change:** Added `_hash` cached field + `__post_init__` + explicit `__hash__` override to `CellStyle`,
so the hash is computed once at construction and returned in O(1) thereafter.
This also required filtering `init=False` fields in `merge_style_fragments`.

Devlog timings (canvas.py, 50 cycles):

| Event | Mean | Median | %cycle | P95 |
|---|---|---|---|---|
| Updated shadow tree | 0.908ms | 0.872ms | 7.8% | 1.199ms |
| — user_code | 0.853ms | 0.820ms | 7.4% | 1.132ms |
| — framework overhead | 0.055ms | 0.053ms | 0.5% | 0.069ms |
| Calculated layout | 2.363ms | 2.349ms | 21.1% | 2.716ms |
| Generated new paint | 4.535ms | 4.369ms | 39.2% | 5.729ms |
| Healed borders | 0.043ms | 0.043ms | 0.4% | 0.050ms |
| Diffed new paint | 1.122ms | 1.098ms | 9.9% | 1.328ms |
| Generated instructions | 0.316ms | 0.318ms | 2.9% | 0.362ms |
| Wrote and flushed | 0.413ms | 0.450ms | 4.0% | 0.620ms |
| **Completed render cycle** | **11.343ms** | **11.137ms** | 100% | 13.254ms |

Note: this run uses canvas.py (high-churn, ~1,800 cells changing every frame), not dashboard.py.
Prior runs used dashboard.py, so absolute times are not directly comparable — canvas is ~2× heavier.

Scalene hotspots (run 8, canvas.py):
- `styles/styles.py:252` — `CellStyle.__hash__` (cached return) — **2.03%** ← now visible; was hidden before
- `_utils.py:80–91` — flyweight `__new__` — 4.33% combined
- `app.py:350` — `output_stream.flush()` — 0.80%
- `utils.py:52` — `_canvas_chunk` lookup in paint loop — 0.80%
- `paint.py:159` — `paint[Position(x, y)] = P(...)` — 0.73%
- `layout.py:189` — text layout cell append — 0.69%
- `app.py:494` — `new_paint.get(pos, BLANK)` in diff loop — 0.55%

#### Why didn't Scalene show the hash cost before?

The old `CellStyle.__hash__` was auto-generated by `@dataclass(frozen=True)` using `exec()` inside
the `dataclasses` module. Scalene profiles at the source-line level — it can only attribute time
to lines in user source files. A dynamically-generated function has no source line in our code,
so its cost was absorbed into the call site (`key = (hash(self), hash(other))` in
`StyleFragment.__or__`) and folded into what looked like `STYLE_MERGE_CACHE` lookup overhead,
not attributed to anything obviously worth optimizing.

Now that `__hash__` is an explicit method in `styles.py`, Scalene surfaces it at 2.03% — even
though the new version is *faster* (just `return self._hash`). The old generated version was
computing `hash((Color, Color, bool, bool, bool, bool, bool))` on every `StyleFragment.__or__`
call, including cache hits, which is the majority of calls in a hot render loop.

### Run 9 — all four benchmark workloads, devlog through without-logging

**Date:** 2026-10-10

**Change:** the devlog moves from structlog (bridged through stdlib `logging`, rendered twice,
once per file, synchronously in every log call) to without-logging: stdlib `logging` records,
parsed in the caller, encoded once as JSON by a sink task, and written by a dedicated thread.
`counterweight devlog` renders the human view at read time.

Measured with `just profile <workload> <workload>-structlog` on a worktree at the parent commit,
then `just profile <workload> <workload>-without`. Frame times are from the unprofiled runs;
logging cost is the profile's share of logging samples times the mean frame time.

| Workload | Mean frame before | Mean frame after | Change | Logging before | Logging after (emit + sink) |
|---|---|---|---|---|---|
| canvas | 10.58 ms | 10.16 ms | −4.0% | 0.99 ms | 0.29 + 0.05 = 0.34 ms |
| top | 33.89 ms | 31.58 ms | −6.8% | 1.07 ms | 0.30 + 0.04 = 0.34 ms |
| agent | 7.36 ms | 7.14 ms | −3.0% | 0.92 ms | 0.26 + 0.06 = 0.32 ms |
| dashboard | 4.47 ms | 3.50 ms | −21.6% | 0.80 ms | 0.18 + 0.10 = 0.27 ms |

Logging falls by about two thirds on every workload. `top`'s frame time fell by more than its
whole logging cost, so part of its change is run-to-run noise on the shared VM; the logging
column is the robust comparison.

What's left is mostly the emit phase in the caller: stdlib's `Logger.makeRecord` (including
`findCaller`) and without-logging's `parse_record`. The sink task's JSON encoding runs between
frames, so in an app with idle time it costs nothing per frame; these saturated runs count it.

### Run 10 — all four benchmark workloads, per-frame layout (PR #385)

**Date:** 2026-10-10

**Changes,** each profiled with `just profile <workload> <workload>-<change>` against the run before it:

1. `memo`: taffy's measure callback reads a `MeasurableText` node context, built once per `Text`
   per frame, which keeps the `Text`'s cells and its wrapped size at each effective width asked about.
   Before, every callback recomputed `Text.cells`, whose `lru_cache` hashes the whole content.
2. `reuse`: `LayoutTree` keeps one `TaffyTree` for the app's lifetime.
   Each `ShadowNode` keeps its `NodeId` (`update_shadow` carries it over with the hooks),
   and each frame reconciles the tree: `set_style` on every node (a no-op for an equal style),
   `set_node_context` only when a `Text`'s content, text style or wrap changed,
   `set_children` only when a node's children changed, and `remove` for every unmounted node.
3. `resolve`: `_resolve_layout`, which turns a node's absolute position and `waxy.Layout`
   into four `Region`s, is an `lru_cache` keyed on `(position, layout, order)`.
   It wasn't planned; the `reuse` profiles showed it as the largest part of layout on `top` and `dashboard`.

Frame times (unprofiled runs):

| Workload | Median base | memo | reuse | resolve | Mean base | Mean resolve |
|---|---|---|---|---|---|---|
| canvas | 9.10 ms | 6.05 ms | 6.22 ms | 6.05 ms | 10.53 ms | 6.60 ms |
| top | 31.01 ms | 27.96 ms | 28.54 ms | 26.05 ms | 34.44 ms | 28.36 ms |
| agent | 5.21 ms | 4.44 ms | 3.84 ms | 3.79 ms | 6.49 ms | 4.84 ms |
| dashboard | 3.27 ms | 2.92 ms | 2.65 ms | 2.56 ms | 3.75 ms | 2.86 ms |

Layout stage (`compute_layout`, then `LayoutTree.compute`), ms per mean frame:

| Workload | base | memo | reuse | resolve |
|---|---|---|---|---|
| canvas | 3.92 | 0.86 | 0.80 | 0.73 |
| top | 10.10 | 7.59 | 7.55 | 4.88 |
| agent | 1.88 | 0.90 | 0.57 | 0.42 |
| dashboard | 0.79 | 0.52 | 0.38 | 0.17 |

Where layout's samples went, by what the layout stage called:

| Workload | Run | Build or update tree | Taffy (native) | Measure callbacks | Read back |
|---|---|---|---|---|---|
| canvas | base | 0% | 1% | 96% | 3% |
| canvas | resolve | 63% | 6% | 27% | 4% |
| top | base | 6% | 16% | 41% | 36% |
| top | resolve | 51% | 24% | 16% | 9% |
| agent | base | 3% | 8% | 78% | 10% |
| agent | resolve | 59% | 10% | 19% | 12% |
| dashboard | base | 6% | 16% | 53% | 24% |
| dashboard | resolve | 47% | 26% | 15% | 12% |

- The memo does most of the work everywhere: taffy asks a leaf about a dozen distinct questions
  per layout, and on `canvas` each one hashed a 1,600-chunk tuple.
- Reusing the tree pays off where most text is unchanged between frames (`agent` −37%, `dashboard`
  −26% of layout) and does nothing measurable where every `Text` changes every frame (`canvas`, `top`).
- What's left is mostly reconciliation: building each changed `Text`'s cells, hashing styles for
  `layout_style` and `resolve_style`, and, on `top`, samples Tachyon labels `<GC>` (see below).
- The last frame of every workload (`profiles/<name>.txt`) is identical before and after.

**Garbage collection.** Tachyon attributes 1–3.5% of samples to `<GC>` (`top` most), but
`gc.callbacks` and `gc.get_stats()` count about two young and one full collection per 500-frame run,
about 20 ms in all, at the default threshold of 2000 and at 50,000 alike.
The young generation's count is allocations minus deallocations, and nearly every per-frame object
is freed by reference counting, so the threshold is rarely reached.
Raising it changed frame times only within noise, so counterweight leaves the collector's settings
to the app. What Tachyon's `<GC>` frames cover beyond cyclic collection is unexplained.

### Run 11 — all four benchmark workloads, faster interning

**Date:** 2026-10-11

**Change:** `@flyweight` returns a slotless subclass whose metaclass's `__call__` is an `lru_cache`
keyed on the raw call arguments, so constructing an instance equal to a cached one is a single
C-level cache hit that skips `__new__`, `__init__` and `__post_init__`.
A miss builds the instance normally and interns it in a second `lru_cache` keyed on the instance
itself, so every spelling of a call shares one instance; that needs hashable instances, so `P` is frozen.
The hot `P` and `Position` call sites pass arguments positionally, which is about 50 ns cheaper per hit.
Profiled with `just profile <workload> <workload>-paintbase` before and `<workload>-intern` after.

Before, `flyweight.__new__`, its key-building genexpr, the re-run dataclass `__init__` and `__hash__`
were about half of `paint_layout`'s samples on every workload.
Every call site passed keyword arguments, the slowest path through `__new__`.
Per construction, on a cache hit:

| Construction | Before | After |
|---|---|---|
| `P`, keyword arguments | 988 ns | 180 ns |
| `P`, positional | 259 ns | 126 ns |
| `Position`, keyword arguments | 1084 ns | 214 ns |
| `Position`, positional | 342 ns | 130 ns |

Frame times (unprofiled runs):

| Workload | Median before | Median after | Change | Mean before | Mean after |
|---|---|---|---|---|---|
| canvas | 6.02 ms | 3.56 ms | −41% | 6.60 ms | 4.41 ms |
| top | 26.48 ms | 20.27 ms | −23% | 28.96 ms | 25.72 ms |
| agent | 3.63 ms | 2.49 ms | −31% | 4.87 ms | 3.74 ms |
| dashboard | 2.42 ms | 1.61 ms | −33% | 2.77 ms | 2.05 ms |

Paint stage (`paint_layout`), ms per mean frame:

| Workload | Before | After | Change |
|---|---|---|---|
| canvas | 4.21 | 1.77 | −58% |
| top | 12.76 | 7.99 | −37% |
| agent | 2.77 | 1.41 | −49% |
| dashboard | 1.49 | 0.70 | −53% |

- `compare` shows `diff_paint` and `paint_to_instructions` growing by up to 39% on `top` and `agent`,
  but their sample counts are unchanged (`agent` 456 → 469, `top` 931 → 975) and so are their `__eq__` fallbacks,
  so cells still compare by identity. A stage's ms/frame is its share of the profile times the unprofiled mean
  frame, and shrinking paint raises every other stage's share faster than the mean frame falls.
- The last frame of every workload (`profiles/<name>.txt`) is identical before and after.
- What's left in paint is the representation: a `dict[Position, P]` per element, merged with `|=`,
  and per-cell construction where whole rows could be filled with one slice assignment.

### Run 12 — all four benchmark workloads, `Paint` as a screen-sized buffer

**Date:** 2026-10-11

**Change:** `Paint` is a class holding a row-major `list[Cell]` for the whole screen, rather than a
`dict[Position, Cell]` built per element and merged with `|=`.

- Elements are sorted by `(z, order)` and paint straight into one buffer, clipped to the screen.
  A fill is one slice assignment per row; text is one per line.
- An element's margin edge, border and padding edge are cached as `(Region, Cell)` fills, and its text
  as rows of cells keyed on the content region's size, not position, so text that moves (everything
  below `agent`'s streaming message) keeps its cache entry.
- `Cell` (renamed from `P`) no longer carries `z`: painting in z order makes it redundant,
  and without it equal-looking cells intern to one instance.
- `diff_paint` skips a row when the whole row compares equal (in C, identity first), and returns runs
  of adjacent changed cells. `paint_to_instructions` moves the cursor once per run and writes an SGR
  sequence only when the style changes, rather than a move, SGR and reset for every cell.

Profiled with `just profile <workload> <workload>-buffer`, compared against `<workload>-paintbase`
(before run 11). Frame times (unprofiled runs):

| Workload | Median before run 11 | After run 11 | After run 12 | Change overall |
|---|---|---|---|---|
| canvas | 6.02 ms | 3.56 ms | 2.51 ms | −58% |
| top | 26.48 ms | 20.27 ms | 13.36 ms | −50% |
| agent | 3.63 ms | 2.49 ms | 0.99 ms | −73% |
| dashboard | 2.42 ms | 1.61 ms | 0.78 ms | −68% |

Stages, ms per mean frame, before run 11 → after run 12:

| Workload | Paint | Diff | Output |
|---|---|---|---|
| canvas | 4.21 → 0.94 | 0.50 → 0.38 | 0.20 → 0.14 |
| top | 12.76 → 2.82 | 1.73 → 0.75 | 1.74 → 0.45 |
| agent | 2.77 → 0.27 | 0.72 → 0.07 | 0.22 → 0.02 |
| dashboard | 1.49 → 0.30 | 0.46 → 0.03 | 0.005 → 0.002 |

- Paint is no longer the largest stage on `top`: `update_shadow` (5.3 ms) and layout (4.0 ms) are.
- What's left of paint is per-element overhead on `top` (hundreds of short `Text`s), and on `canvas`,
  building text rows on cache misses (every walker moves every frame) and hashing cache keys.
- The last frame of every workload (`profiles/<name>.txt`) is identical to `<workload>-paintbase`,
  and so is every docs screenshot.

**Decision: off-screen cells are invisible, including to border healing.** A screen-sized buffer has
nowhere to keep cells that fall off the screen, so painting clips them, and `heal_borders` sees an
off-screen neighbor as absent. Before, a border running off the screen could join with an off-screen
border's characters at the edge. No screenshot or test exercises that case. We may reverse this later;
doing so means keeping off-screen cells somewhere healing can look at them, for example a buffer
padded by a margin around the screen.

### Run 13 — does `@flyweight` still pay, after the `Paint` buffer?

**Date:** 2026-10-11

**Method:** unprofiled `benchmarks run` with `@flyweight` replaced by the identity decorator for chosen
classes, patched into `counterweight._utils` before the package imports (its `__init__` applies the
decorators, so patching after `import counterweight` silently changes nothing). Every configuration's
last frames are identical to interning on. A first pass ran each configuration once; two runs of the
same interned code in that pass differed by up to 27% on `top`, so the configurations that moved were
rerun in three interleaved rounds.

Median frame time, median of three rounds, change against interning on:

| Workload | Interning on | All off | `Cell` off | `CellStyle` off |
|---|---|---|---|---|
| canvas | 2.56 ms | +20% | +21% | −3% |
| top | 12.21 ms | +16% | +7% | +9% |
| agent | 0.95 ms | +15% | +10% | +3% |
| dashboard | 0.82 ms | +7% | +3% | +4% |

- `Cell` interning still pays wherever cells change: `diff_paint`'s row comparison and its per-cell
  fallback short-circuit on identity, and an uninterned cell built this frame never is the one
  from last frame, so every comparison falls through to the dataclass `__eq__`.
- `CellStyle` interning pays on `top`. Unverified explanation: hundreds of `Text`s build styles every
  frame that end up as cache keys (`text_cells`, `resolve_cell_style`), whose lookups short-circuit on identity.
- Turning off `Position`, `ResolvedCellStyle` or `StyledChar` interning showed no slowdown in the
  single first pass (every workload within that pass's noise, mostly faster).
  `Position` has left the hot path entirely: the buffer indexes by integers.
  Those three are candidates to drop, pending a repeated run to confirm.

### Run 14 — confirming run 13's candidates: `Position`, `ResolvedCellStyle`, `StyledChar`

**Date:** 2026-10-11

**Method:** as in run 13, three interleaved rounds of unprofiled `benchmarks run` (500 frames),
with each candidate's interning off alone and all three off together.
Every configuration's last frames are identical to interning on.
Output bytes are counted separately (100 frames, wrapping `paint_to_instructions`),
because headless runs build the instructions but never write them, so frame time can't show their size.

Median frame time, median of three rounds, change against interning on:

| Workload | Interning on | `Position` off | `ResolvedCellStyle` off | `StyledChar` off | All three off |
|---|---|---|---|---|---|
| canvas | 2.41 ms | +4% | +9% | +0% | +2% |
| top | 12.99 ms | −4% | −0% | −1% | −1% |
| agent | 0.91 ms | +5% | +5% | +10% | +11% |
| dashboard | 0.79 ms | +3% | +0% | +2% | +3% |

The spread between rounds of the same configuration is up to 8% (`top`, interning on: 12.19–13.18 ms).

Output bytes over 100 frames with `ResolvedCellStyle` interning off:

| Workload | On | Off |
|---|---|---|
| canvas | 737,784 | 737,784 |
| top | 1,380,087 | 2,056,441 (+49%) |
| agent | 42,165 | 95,318 (+126%) |
| dashboard | 9,031 | 9,031 |

- `Position` interning is dropped: every workload is within the round-to-round spread.
- `ResolvedCellStyle` interning stays. `paint_to_instructions` starts a new SGR sequence when a cell's
  style isn't the same object as the previous cell's, so equal styles that aren't one instance
  re-send their SGR sequence. Comparing with `!=` after the identity check would make the output
  independent of interning, at the cost of an `__eq__` call wherever the style really changes.
- `StyledChar` interning stays: `agent` is slower with it off in all three rounds.
  Unverified explanation: `justify_line` builds its padding with `StyledChar(char=" ")`,
  which interning turns into a cache hit.

### Run 15 — what styles cost per frame (PR #385)

**Date:** 2026-10-11

**Question:** what resolving authored styles to concrete ones (`resolve_style`, `resolve_cell_style`)
and deriving border widths from `border_kind` (`layout_style`) cost per frame,
and whether `Style` should cache its hash, now that `resolve_style`, `layout_style` and the merge cache
all hash styles on every frame.

**Where styles went, before any change** (`<workload>-s12base`, share of running samples):

- `resolve_style`, `resolve_cell_style` and `layout_style` are `lru_cache` hits on every workload;
  their bodies run on misses only, at most 0.5% of samples.
  What they cost is hashing the `Style` key: on `top`, the dataclass-generated `__hash__` called from
  `_update_node` (`layout_style`, and `resolve_style` for a `Text`'s wrap) is 1.6%, and from `paint_layout` 0.7%.
  So the derived border widths cost one key hash per element per frame, and nothing else.
- Merging was the real cost. `StyleFragment.__or__` was 18.3% of `top`'s samples, 5.4% of `dashboard`'s:
  `top` merges four styles per cell of every process row, every frame.
  The merge cache was a cachetools `LRUCache`, whose `__getitem__` and `__touch` are Python and hash and
  compare the `(left, right)` key again on every hit, and `Style`'s generated `__hash__` recomputes
  a tuple of its eleven fields every call, about 225 ns.
- On `canvas`, the generated `__hash__` is 12% of samples, but it hashes text content
  (`Text.cells`, `MeasurableText.of`, `text_lines`' key), not styles.

**Changes,** each profiled with `just profile <workload> <workload>-<change>` against the run before it:

1. `lru`: the merge cache is a `functools.lru_cache` around `merge_style_fragments`, which hashes the key once
   per lookup, in C. counterweight no longer depends on cachetools.
2. `hash`: `Style` computes its hash once, in `__post_init__`, as `CellStyle` and `ResolvedCellStyle` already do.

Per operation (`timeit`, best of five):

| Operation | Before | `lru` | `hash` |
|---|---|---|---|
| `hash(Style)` | 227 ns | 227 ns | 56 ns |
| `a \| b`, cache hit, `b` the cached instance | 746 ns | 504 ns | 155 ns |
| `a \| b`, cache hit, `b` equal but distinct | 2166 ns | 983 ns | 564 ns |
| `Style(text_style=CellStyle(...))` | 1512 ns | 1512 ns | 2348 ns |

Median frame time, median of three interleaved rounds of unprofiled `benchmarks run`,
each configuration importing counterweight from its own copy of `src` (`PYTHONPATH`):

| Workload | Before | `lru` | `lru` and `hash` |
|---|---|---|---|
| canvas | 2.45 ms | −2% | −1% |
| top | 12.18 ms | −7% | −15% |
| agent | 0.95 ms | +3% | −4% |
| dashboard | 0.80 ms | −6% | −10% |

On `top` the rounds don't overlap: 11.92–12.55 ms before, 10.24–10.66 ms after both changes.
`canvas` and `agent` are within the round-to-round spread; neither merges many styles per frame.

- On `top`, `StyleFragment.__or__` falls from 18.3% to 5.9% of samples, and `Style.__post_init__`
  rises from 1.5% to 4.3%: `top` builds fresh `Style`s every frame (`Style()`, `Style(text_style=...)`),
  and each now pays for its hash when built rather than when first hashed. Every one of them is hashed
  by a merge in the same frame, so the up-front hash is never wasted there.
- What's left of merging on `top` is the generated `__eq__` (3.5% of samples): a freshly built `Style`
  equal to last frame's is a cache hit only after comparing every field, including the `waxy.Style`.
  Interning `Style` with `@flyweight` would make those hits identity checks, at the cost of a lookup on
  every construction; that's untested.
- The last frame of every workload (`profiles/<name>.txt`) is identical before and after.

### Run 16 — output independent of interning (PR #394)

**Date:** 2026-10-12

**Change:** `paint_to_instructions` starts a new SGR sequence only when a cell's style is neither the
same object as the previous cell's nor equal to it (`cell.style is not style and cell.style != style`),
so equal styles that are separate instances no longer re-send their SGR sequence.

**Method:** as in run 14, with `ResolvedCellStyle`'s `@flyweight` replaced by the identity decorator
before the package imports. Each configuration imports counterweight from its own copy of `src`
(`PYTHONPATH`). Output bytes are counted over 100 frames by wrapping `paint_to_instructions`,
with a hash of everything written.

Output bytes over 100 frames:

| Workload | Before, on | Before, off | After, on | After, off |
|---|---|---|---|---|
| canvas | 783,608 | 783,608 | 783,608 | 783,608 |
| top | 1,380,087 | 2,056,441 (+49%) | 1,380,087 | 1,380,087 |
| agent | 48,211 | 101,364 (+110%) | 48,211 | 48,211 |
| dashboard | 10,061 | 10,061 | 10,061 | 10,061 |

After the change, every workload's output hashes the same with interning on and off,
and the same as before the change with interning on.
`canvas`, `agent` and `dashboard` write more than run 14's "on" column; both sides of each
comparison here are measured on the same code.

Median frame time, median of three interleaved rounds of unprofiled `benchmarks run` (500 frames),
with the range across rounds:

| Workload | Before | After, interning on | After, `ResolvedCellStyle` off |
|---|---|---|---|
| canvas | 2.46 ms (2.44–2.51) | 2.46 ms (2.45–2.53) | 2.54 ms (2.52–2.55) |
| top | 10.42 ms (10.41–10.84) | 11.18 ms (10.60–11.25) | 10.93 ms (10.71–11.66) |
| agent | 0.89 ms (0.89–0.95) | 0.89 ms (0.88–0.90) | 0.94 ms (0.92–1.02) |
| dashboard | 0.82 ms (0.78–0.84) | 0.80 ms (0.75–0.84) | 0.76 ms (0.76–0.80) |

- The change costs nothing measurable. Five more interleaved rounds of `top`, before and after,
  overlap: 10.21–10.59 ms (median 10.48) before, 10.33–10.79 ms (median 10.50) after.
  The added `__eq__` runs only where the style really changes: about 200 times per frame on `top`
  and `canvas`, at about 120 ns each, so under 0.03 ms per frame.
- `ResolvedCellStyle` interning stays. `agent` is slower with it off in every round, with no overlap,
  as in run 14. With output no longer depending on it, what it buys is speed alone.
- The last frame of every workload (`profiles/<name>.txt`) and every docs screenshot is identical
  before and after.

### Run 17 — frames timed from the key handler, and `dashboard-local` (PR #394)

**Date:** 2026-10-12

**Change:** the harness times a frame as the interval between two autopilot key presses, seen by a key handler
on the root element, rather than between two renders of the root component, which stops working once the root
can be skipped. `frames` key presses time `frames - 1` frames, so a default run times 479 frames, not 480.
`dashboard-local` draws what `dashboard` does, but its frame counter holds its tick in its own state and
steps it from its own key handler, so nothing above the counter holds state.

**Method:** three interleaved rounds of unprofiled `benchmarks run` (500 frames), the old harness
(from `HEAD`) against the new, on the same counterweight. Every round's last frame is identical between the
two harnesses, and `dashboard-local`'s is identical to `dashboard`'s.

Median frame time, median of three rounds, with the range across rounds:

| Workload | Timed from root renders | Timed from key presses |
|---|---|---|
| canvas | 2.54 ms (2.54–2.99) | 2.54 ms (2.52–2.73) |
| top | 11.30 ms (10.64–12.42) | 12.29 ms (11.45–14.40) |
| agent | 1.06 ms (0.88–1.11) | 0.93 ms (0.88–1.26) |
| dashboard | 0.78 ms (0.74–0.95) | 0.89 ms (0.76–0.91) |
| dashboard-local | | 0.84 ms (0.79–1.01) |

- The two ways of timing agree within the round-to-round spread. Three more rounds of `top` ran while the
  machine was noisier (single rounds from 10.6 to 23.2 ms); paired round by round, the six rounds' change
  is +1%, +35%, −1%, +59%, −10% and +3%, so no systematic shift.
- `dashboard-local` does the same work as `dashboard` while every component re-runs every frame,
  and measures the same. Its column is the baseline for skipping unchanged components.

### Run 18 — incremental rendering, and interning revisited (PR #394)

**Date:** 2026-10-12

**Change:** the rest of PR #394's incremental rendering: per-node state in the shadow tree,
layout reconciled by the pure `layout_changes`, re-running only components whose state, arguments or
rectangles changed, `@component(memo=True)`, `use_memo`, and no layout reconciliation for reused subtrees.

**Method:** the baseline is run 17's `src` and `benchmarks` (`f0d40df`), run from their own directory
against the same environment (`PYTHONPATH`), so both sides time frames from key presses.
Runs 16 and 17 change no frame, so the baseline is the code from before the restructuring.
Five interleaved rounds of unprofiled `benchmarks run` (500 frames), baseline and `HEAD` alternating per workload.
Profiles are `<workload>-s8base` and `<workload>-s8`. The `-memo` workloads exist only on `HEAD`.
Every round's last frame is identical between the baseline and `HEAD`, between each `-memo` workload and its twin,
and between `dashboard-local` and `dashboard`.

Median frame time, median of five rounds, with the range across rounds:

| Workload | Baseline | `HEAD` | Change | `HEAD`, `-memo` twin | Change against `HEAD` |
|---|---|---|---|---|---|
| canvas | 2.46 ms (2.43–2.65) | 2.52 ms (2.51–2.56) | +2% | | |
| top | 10.41 ms (10.33–10.46) | 10.46 ms (10.20–11.12) | +0% | 10.38 ms (10.29–10.68) | −1% |
| agent | 0.89 ms (0.85–0.91) | 0.97 ms (0.91–1.01) | +8% | 0.90 ms (0.86–0.97) | −8% |
| dashboard | 0.73 ms (0.70–0.80) | 0.82 ms (0.78–0.84) | +12% | 0.66 ms (0.65–0.71) | −20% |
| dashboard-local | 0.74 ms (0.71–0.76) | 0.60 ms (0.58–0.63) | −19% | | |

Stages, ms per mean frame (one profiled run each, so read them as shares of a frame rather than as frame times).
In the baseline, layout reconciliation ran inside `LayoutTree.compute`; on `HEAD`, it's `layout_changes`:

| Run | Mean frame | `update_shadow` | `layout_changes` | `LayoutTree.compute` | `paint_layout` | `diff_paint` | `Logger.debug` |
|---|---|---|---|---|---|---|---|
| canvas, baseline | 2.97 | 0.44 | | 0.76 | 0.94 | 0.24 | 0.22 |
| canvas | 3.09 | 0.43 | 0.03 | 0.78 | 1.03 | 0.21 | 0.19 |
| top, baseline | 11.05 | 3.16 | | 3.29 | 2.45 | 0.69 | 0.20 |
| top | 12.38 | 3.58 | 0.85 | 3.09 | 2.65 | 0.78 | 0.26 |
| top-memo | 12.79 | 3.80 | 1.00 | 3.12 | 2.72 | 0.72 | 0.27 |
| agent, baseline | 1.28 | 0.16 | | 0.28 | 0.37 | 0.12 | 0.15 |
| agent | 1.24 | 0.15 | 0.04 | 0.20 | 0.31 | 0.13 | 0.16 |
| agent-memo | 1.07 | 0.13 | 0.03 | 0.23 | 0.28 | 0.09 | 0.15 |
| dashboard, baseline | 0.84 | 0.14 | | 0.12 | 0.28 | 0.03 | 0.09 |
| dashboard | 0.96 | 0.19 | 0.05 | 0.11 | 0.30 | 0.02 | 0.15 |
| dashboard-memo | 0.77 | 0.08 | 0.02 | 0.09 | 0.30 | 0.03 | 0.13 |
| dashboard-local, baseline | 0.84 | 0.17 | | 0.09 | 0.28 | 0.02 | 0.15 |
| dashboard-local | 0.73 | 0.04 | 0.02 | 0.12 | 0.29 | 0.02 | 0.12 |

- **`dashboard-local`** does what the change was for: `update_shadow` falls by three quarters and `layout_changes`
  is 0.02 ms, since only the frame counter re-runs. What's left of the frame is the whole-tree passes that call
  no user code: taffy's traversal and reading layouts back (`LayoutTree.compute`), paint, diff, and logging.
- **The `-memo` workloads** differ as their designs predict. `dashboard-memo` reuses every card and cuts
  `update_shadow` by more than half. `agent-memo` re-runs only the streaming message. `top-memo` saves nothing,
  since its unkeyed rows reorder every frame and memo misses.
- **`canvas` and `top`** are within the round-to-round spread of the baseline: their per-frame work dwarfs
  the bookkeeping the change added.
- **`agent` and `dashboard`** are not: 0.08–0.09 ms per frame slower, with ranges that barely overlap.
  Profiles of 3,000 frames on each side (`<workload>-s8base-long`, `<workload>-s8-long`) put the extra samples
  in `update_shadow` and layout at +17% on `agent` and +18% on `dashboard`, spread across per-node bookkeeping
  with no single hotspot. Each item is 1–5% of those stages' samples:
  - `dirty_paths` walks the whole previous tree every frame, building a parent map, to find the dirty paths.
  - `LayoutTree.compute` walks the whole next tree every frame to build its `NodeId → ShadowNode` map.
  - `_reconcile` calls `text_source` for both the next and the previous `Text`, rebuilding the previous one's
    source rather than reading it from anywhere.
  - `call_component` sets and resets four context variables, where it set two.
  - `ShadowNode.key` is a property that reads through to `Hooks`.

  That's a fixed cost per node, a fraction of a percent of a 60 fps frame budget, and candidates to remove
  if it ever matters: compute the dirty paths from the dirty keys upward through a parent map kept in the tree,
  keep each `Text`'s source on its shadow node, and keep a `NodeId → NodeKey` map in `LayoutTree` beside its
  `NodeKey → NodeId` one.
- Paint is now the largest stage on every workload except `top`, where `update_shadow`, layout and paint
  are about equal. Paint being the largest stage was the condition for revisiting a native cell buffer
  (fill, diff and output in Rust, comparing cells by value without `Cell` interning):
  pick it up in the next round of performance work.

**Interning, revisited.** As in run 13: unprofiled `benchmarks run` with one class's `@flyweight` replaced by
the identity decorator before the package imports, three interleaved rounds, every workload.
Every configuration's last frames are identical to interning on.

Median frame time, median of three rounds, change against interning on, with the range across rounds:

| Workload | Interning on | `Cell` off | `CellStyle` off | `StyledChar` off |
|---|---|---|---|---|
| canvas | 2.48 ms (2.43–2.51) | +23% (2.98–3.11) | −2% (2.41–2.52) | −2% (2.35–2.56) |
| top | 10.30 ms (10.25–10.55) | +9% (11.05–11.27) | +9% (11.19–11.71) | +4% (10.56–10.78) |
| top-memo | 10.48 ms (10.42–10.58) | +7% (11.06–11.21) | +8% (11.18–11.51) | −0% (10.31–10.79) |
| agent | 0.95 ms (0.94–0.97) | +9% (1.04–1.12) | +8% (0.97–1.06) | +8% (0.97–1.11) |
| agent-memo | 0.89 ms (0.82–0.93) | +14% (0.97–1.03) | +0% (0.89–0.91) | +4% (0.88–0.99) |
| dashboard | 0.81 ms (0.77–0.87) | +3% (0.81–0.86) | +8% (0.86–0.92) | +6% (0.84–0.87) |
| dashboard-memo | 0.67 ms (0.64–0.70) | +1% (0.68–0.71) | +7% (0.65–0.72) | −0% (0.63–0.69) |
| dashboard-local | 0.64 ms (0.59–0.68) | −6% (0.60–0.62) | −3% (0.60–0.65) | −4% (0.60–0.62) |

Every `@flyweight` stays: each one's ranges don't overlap interning on for at least one workload.
`Cell` on `canvas`, `top` and `agent`; `CellStyle` on `top`, `top-memo` and `agent`; `StyledChar` on `top`.
Reused subtrees construct fewer values per frame, but the workloads that change most per frame build enough
cells and styles that interning still pays where they're compared.

### Run 19 — mouse routing and the per-render routing table (PR #402)

**Date:** 2026-10-13

**Change:** mouse events route to one target and bubble. Each render builds a `RoutingTable`
(`routing.py:RoutingTable.of`): a map from each visible node's key to its handler, beside references to the
layouts and the shadow tree's parent map. Mouse events hit-test the paint order and bubble through
`ShadowTree.parents`; keys still go to every handler, now through `route_key`, which looks each visible
node up in the handler map instead of reading its element.

**Method:** the baseline is `HEAD` (`9ea3c2b`) in a separate worktree. One profiled `just profile` run of
`dashboard-memo` on each side (`routing-before`, `routing-after`), chosen because it does the least other work
per frame, so a fixed per-render cost shows most there. Then three interleaved unprofiled `benchmarks run`
rounds of `top` (`top-routing-before`, `top-routing-after`), which has the most nodes,
and one profiled run of `top` after the change (`top-routing-profiled`).
Both workloads' last frames are identical before and after.

`dashboard-memo`, one profiled run each:

| Run | Median | Mean | P95 | `RoutingTable.of` | `route_key` |
|---|---|---|---|---|---|
| before | 0.757 ms | 0.865 ms | 1.217 ms | | |
| after | 0.710 ms | 0.845 ms | 1.049 ms | 0.002 ms/frame | 0.002 ms/frame |

`top`, median frame time of three interleaved rounds, with the range across rounds:

| Run | Median |
|---|---|
| before | 11.77 ms (11.02–12.37) |
| after | 12.30 ms (11.55–12.46) |

- **Building the table** costs 0.002 ms per frame on `dashboard-memo` and 0.021 ms on `top`,
  0.2% of each, so rebuilding it every render needs no caching.
- **`top`'s rounds overlap**, and the machine was noisy (the first round's "after" was the slowest of all six).
  The profile accounts for the difference without a regression: of `route_key`'s 0.53 ms per frame,
  237 of its 275 samples are the workload's own `step`, the root key handler that the loop used to call directly.
  Routing's own share is about 0.07 ms per frame, for a key delivered to every visible node,
  which step 5 replaces with one bubble path.

### Run 20 — key routing through focus, and focus reconciliation (PR #402)

**Date:** 2026-10-13

**Change:** a key press bubbles from the focused node,
or from the root component's node when nothing is focused, instead of reaching every visible handler.
`RoutingTable.of` also records each visible node that called `use_focus`, and checks that no two mounted
components share a `FocusHandle`. After each render, `RoutingTable.reconciled_focus` clears focus that can no
longer be held and applies `auto_focus` to the components that mounted.

**Method:** the baseline is `HEAD` (`c362220`) in a separate worktree. One profiled `just profile` run of
`dashboard-memo` on each side (`focus-before`, `focus-after`), then three interleaved unprofiled
`benchmarks run` rounds of `dashboard-memo` and `top` on each side (`dm-focus-*`, `top-focus-i-*`),
and one profiled run of `top` after the change (`top-focus-profiled`).
`dashboard-memo`'s last frame is identical before and after.
Neither workload has a focusable component, so every key goes to the root's handler.

Median frame time of three interleaved rounds, with the range across rounds:

| Workload | Before | After |
|---|---|---|
| `dashboard-memo` | 0.741 ms (0.721–0.854) | 0.801 ms (0.729–0.803) |
| `top` | 12.57 ms (12.52–12.68) | 12.04 ms (11.43–12.10) |

- **The rounds overlap on `dashboard-memo`**, and the profiled "after" run was slower in every stage,
  paint and layout included, which this change doesn't touch, so the machine was noisy during it.
  Its routing stages stay small: `RoutingTable.of` at 0.002 ms per frame on both sides,
  and `route_key` at 0.007 and 0.012 ms per frame, from a handful of samples each.
- **Routing's own cost on `top` falls** from about 0.07 ms per frame to about 0.014 ms:
  of `route_key`'s 288 samples, 279 are the workload's root handler and 9 are routing,
  against 38 of 275 in run 19, since a key now calls one handler rather than every visible node's.
- **Reconciling focus doesn't show** in either profile, and `RoutingTable.of` costs 0.031 ms per frame on `top`,
  against 0.021 ms in run 19, within the noise of one profiled run.

### Run 21 — Markdown and syntax highlighting in `agent` (issue #330)

**Date:** 2026-10-13

**Change:** two new workloads, `agent-markdown` and `agent-markdown-memo`,
step the same models as `agent` but render assistant messages with `markdown`
(a fixed set of words marked up as code, emphasis, strong, or a link)
and tool calls with `code_block` (`python` for reads, `diff` for edits).
`block_gap=0` keeps each message the height `visible` estimates.
The streaming message's source changes every frame, so it is parsed every frame;
every other message is a hit in `markdown`'s cache.

**Method:** three interleaved rounds of unprofiled `benchmarks run` (500 frames), named `r<round>-<config>`,
and one profiled `just profile` run of each workload.
"Quiet" is `agent-markdown` with `logging.getLogger("markdown_it")` raised to `INFO` before the run,
set in the runner and not in counterweight.

Median frame time, median of three rounds, with the range across rounds:

| Workload | Median | Change against its plain twin |
|---|---|---|
| `agent` | 1.07 ms (1.04–1.11) | |
| `agent-markdown` | 1.52 ms (1.50–1.58) | +42% |
| `agent-markdown`, quiet | 1.33 ms (1.30–1.36) | +24% |
| `agent-memo` | 0.99 ms (0.97–1.05) | |
| `agent-markdown-memo` | 1.46 ms (1.42–1.49) | +47% |

- **The added cost is all in `update_shadow`** (0.21 → 0.58 ms per mean frame in the profiles):
  paint and layout are within noise of `agent`. Of `update_shadow`, `markdown` is 22% of running samples,
  nearly all of it `MarkdownIt.parse` of the streaming message.
- **About half of parsing is markdown-it's own logging.** Its block rules call `LOGGER.debug` on entry,
  and the devlog captures every logger at `DEBUG`, so each parse makes dozens of records, built in the caller
  (`makeRecord`, `findCaller`) and encoded by the sink task (whose stage grows from 0.05 to 0.13 ms per frame).
  Quieting that one logger takes back 0.19 ms of the 0.45 ms median difference.
- **`memo` saves nothing extra here:** the only message that re-renders is the streaming one,
  whose source changes every frame, and the others already hit `markdown`'s cache.
- **Max frames of 27–41 ms** in the Markdown runs, against about 5 ms for `agent`, are first use:
  the first `highlight` of a language takes about 19 ms (Pygments loads the lexer and style),
  and the first `markdown` about 17 ms (markdown-it builds its rules); later calls take about 0.1 ms.
- `agent-markdown-memo` draws the same last frame as `agent-markdown`.

### Run 22 — devlog levels by logger name, and where Markdown's time goes (issue #330)

**Date:** 2026-10-13

**Change:** the devlog captures counterweight and the app's own top-level package at `DEBUG`
and everything else from `INFO`, and `app`'s `log_levels` (logger name to level, `""` the root logger)
is merged over that base.
The devlog sets each named logger's level while the app runs, so a third-party `DEBUG` record
is rejected by `isEnabledFor` before it's built, where run 21's markdown-it records cost most.

**Method:** three interleaved rounds of unprofiled `benchmarks run` (500 frames), named `lv<round>-<workload>`.
The breakdown comes from one profiled run of `agent-markdown` with markdown-it's logger at `INFO`
and the `python` and `diff` lexers and the parser warmed up before the first frame (`md-quiet-warm`),
its collapsed stacks bucketed by the innermost frame that names a phase,
and `timeit` on one 185-word streaming message.

Median frame time, median of three rounds, with the range across rounds:

| Workload | Run 21 | Run 22 | Change against its plain twin, run 22 |
|---|---|---|---|
| `agent` | 1.07 ms (1.04–1.11) | 1.05 ms (1.02–1.09) | |
| `agent-markdown` | 1.52 ms (1.50–1.58) | 1.33 ms (1.22–1.36) | +27% |
| `agent-memo` | 0.99 ms (0.97–1.05) | 1.00 ms (0.97–1.11) | |
| `agent-markdown-memo` | 1.46 ms (1.42–1.49) | 1.25 ms (1.24–1.26) | +25% |

`render_markdown_message`, ms per mean frame (1.53 ms):

| Part | ms/frame | Whose |
|---|---|---|
| markdown-it inline pass | 0.138 | library |
| markdown-it block pass | 0.047 | library |
| `SyntaxTreeNode` | 0.031 | library |
| markdown-it core rules | 0.020 | library |
| Converting the tree to elements | 0.025 | counterweight |
| `code_block`, warm | 0.020 | counterweight |
| `marked_up` | 0.036 | the workload |

- **About 70% is markdown-it**, and most of that is its inline pass, which scans every paragraph
  of the streaming message character by character in Python, every frame.
  Under `timeit`, one 185-word message takes 273 µs to parse, 39 µs to build its `SyntaxTreeNode`,
  and 35 µs for counterweight to turn into elements.
- **Counterweight's own share is small:** converting the tree, and wrapping cached highlights in a `Text`
  (0.5 µs per `code_block` on a cache hit).
- **The levers are on our side of the call, not inside markdown-it:** only the last paragraph of a streaming message
  changes, so caching inline parsing per paragraph would take the inline pass from O(message) to O(last paragraph);
  walking markdown-it's tokens directly would drop the `SyntaxTreeNode` step. Neither is tried yet.

### Run 23 — `agent-markdown` shaped like real agent output (issue #330)

**Date:** 2026-10-13

**Change:** `agent-markdown` has its own model, in `benchmarks/agent_markdown.py`, instead of marking up `agent`'s.
Runs 21 and 22 streamed one long run of prose with sparse markup, which real agent output isn't.
Its shapes come from the assistant text blocks in the Claude Code transcripts on the development machine
(5,075 main-thread blocks across 29 projects; only statistics were kept, never text):

| Measure | p10 | p25 | p50 | p75 | p90 | p99 |
|---|---|---|---|---|---|---|
| Words per block | 9 | 14 | 22 | 36 | 278 | 702 |
| Top-level blocks per block | 1 | 1 | 1 | 1 | 6 | 14 |
| Tool calls before a block | 0 | 1 | 2 | 5 | 9 | 26 |
| Words per paragraph | 6 | 13 | 22 | 34 | 54 | 96 |
| Items per list | 2 | 2 | 3 | 4 | 5 | 7 |
| Lines per code fence | 1 | 1 | 3 | 5 | 9 | 76 |

- Every block has a paragraph; 14% have a bulleted list, 3% a numbered list, 3% a code fence,
  2% a table and 2% a heading (nearly all `##`).
- Per 100 words: 4.7 inline code spans, 1.2 bold, 0.05 links, 0.04 italics.
- Tool calls are 53% shell commands, 28% edits and 18% reads, among those three.

The generator draws narration (85%) or a summary (15%) from those percentiles, and reproduces them closely:
a median of 21 words and a 90th percentile of 288, a mean of 2.1 top-level blocks, and the same share of lists.
It streams three words a frame, so the streaming block's source is often unfinished Markdown,
and a code fence that's still streaming misses `highlight`'s cache every frame.

**Method:** three interleaved rounds of unprofiled `benchmarks run` (500 frames), named `real<round>-<workload>`,
and one profiled run of `agent-markdown`, its collapsed stacks under `render_message`
bucketed by the innermost frame that names a phase.

Median frame time, median of three rounds, with the range across rounds:

| Workload | Median | Change against its plain twin |
|---|---|---|
| `agent` | 1.09 ms (1.00–1.11) | |
| `agent-markdown` | 1.34 ms (1.29–1.34) | +23% |
| `agent-memo` | 0.98 ms (0.94–1.00) | |
| `agent-markdown-memo` | 1.28 ms (1.24–1.32) | +31% |

`render_message` is 23% of running samples. Within it:

| Part | Share | Whose |
|---|---|---|
| markdown-it block pass | 28% | library |
| markdown-it inline pass | 22% | library |
| `SyntaxTreeNode` | 12% | library |
| markdown-it core rules | 7% | library |
| Pygments lexing | 14% | library |
| Pygments loading a lexer for the first time | 1% | library |
| Converting the tree to elements | 17% | counterweight |

- **About 83% is library code.** With lists and tables in the mix, markdown-it's block pass now costs more
  than its inline pass, and Pygments re-lexes a code fence on every frame that it grows.
- **Counterweight's share is 17%,** larger than run 22's because real output has more blocks and inline spans per word.
- Run 22's levers still apply, but the per-paragraph inline cache would save less here:
  most blocks are a single short paragraph, and summaries spend more in the block pass.
