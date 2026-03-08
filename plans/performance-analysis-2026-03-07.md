# Performance Analysis — `profiling/canvas.py`

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

### 1. Skip layout when tree is unchanged (saves ~4 ms/cycle, ~25%)

**Status:** TODO

Layout runs every cycle even though the canvas workload has a completely static component
tree and static styles — no sizing or structural changes ever occur. Adding a dirty flag
(set when styles, structure, or terminal size change) to skip `compute_layout` would
recover the full 4.1 ms on stable frames.

Relevant code: `src/counterweight/app.py`, `src/counterweight/layout.py`

---

### 2. Memoize stable component subtrees (saves ~2 ms/cycle, ~12%)

**Status:** TODO

**Revised priority:** now clearly #2, up from #3. `user_code_ns` shows that ~93% of shadow
tree time is spent inside component functions — so skipping calls for unchanged subtrees
would recover most of the 2.5ms. For the canvas workload, `header()` and `fps_display()`
are static each frame and could be skipped entirely. Analogous to `React.memo`.

The opt-in API would likely be a `@component(memo=True)` decorator flag or a `use_memo`
hook. A component would be re-skipped if its args/kwargs are equal to the previous render.

Relevant code: `src/counterweight/shadow.py` (`update_shadow`), `src/counterweight/components.py`

---

### 3. Incremental paint for Text nodes (saves ~2–4 ms/cycle, ~15–25%)

**Status:** DONE (user-side optimizations); framework-side incremental paint is N/A

`canvas()` moved to `counterweight.utils` and optimized:
- Coordinate pairs precomputed and cached per `(width, height)` via `_canvas_rows` —
  eliminates 900 temp tuple allocations per call.
- Row-structured iteration replaces flat `enumerate` + `i % width` modulo per cell.
- `_canvas_chunk(fg, bg)` cached via `lru_cache(maxsize=512)` — each unique color pair
  allocated once; subsequent calls return the interned `Chunk`. For the random walkers
  workload (~31 unique pairs), drops canvas allocations from ~1,800 Chunks + 1,800
  CellStyles per frame to ~31 cached objects after warmup.

Framework-side incremental paint is not viable: user components are declarative and return
a new element tree on every render, so the framework has no stable chunk references to diff
against without re-running the component.

Relevant code: `src/counterweight/utils.py`

---

### 4. Use lazy initializers in `use_state` (fixed in canvas.py)

**Status:** DONE

`use_state(expensive_expr)` evaluates `expensive_expr` on every render even though the
initial value is only used once. Pass a lambda instead: `use_state(lambda: expensive_expr)`.
`use_state` already supports `Getter[T] | T` — if the argument is callable it is only
invoked on first render.

Fixed in `profiling/canvas.py`: `random.sample(...)` and the walkers list comprehension
are now lambdas.

Also a good pattern to document for framework users.

---

### 5a. Cache `paint_edge()` output (saves est. ~0.5–1 ms/cycle on static layouts)

**Status:** DONE

`paint_edge()` fills margin/padding strips from `(outer, inner, color, z)` arguments — all hashable
(`waxy.Rect` supports value equality, `Color` and `int` are trivially hashable). It does the same
kind of point-by-point iteration as `fill_rect()`, which already has `@lru_cache`. Adding
`@lru_cache(maxsize=2**10)` to `paint_edge()` would make static layouts hit the cache every frame.

Relevant code: `src/counterweight/paint.py:145`

---

### 5b. Cache `paint_text()` output (saves est. ~1–2 ms/cycle on static text)

**Status:** DONE

`paint_text()` rebuilds its full `Paint` dict every frame — running `wrap_cells`, `justify_line`,
and dict construction — even when the `Text` element and rect are unchanged. `Text` is a frozen
dataclass (hashable) and `waxy.Rect` supports value equality, so `@lru_cache` keyed on
`(text, rect)` would return the cached dict by reference on subsequent calls.

Note: the cached dict must not be mutated by callers. Currently `paint_element()` merges via
`box | paint_text(...)` which creates a new dict — safe.

Relevant code: `src/counterweight/paint.py:111`

---

### 5c. Batch adjacent cells in `paint_to_instructions()` (reduces bytes written)

**Status:** DONE

`paint_to_instructions()` emits one `move_to + SGR + char + reset` per cell (~40 bytes each).
For adjacent cells on the same row with the same style, only one `move_to` and one SGR are needed;
subsequent chars on the same run can be concatenated. Sorting diff cells by `(y, x)` then grouping
same-style runs would reduce output bytes substantially (e.g. a 60-char line of same-style text
goes from ~2400 bytes to ~50 bytes). Impact on write time is modest at current scale but grows
with terminal size or high-churn frames.

Relevant code: `src/counterweight/output.py:89`

---

### 6. Narrow border-healing hint set (saves ~0.4 ms/cycle, ~2.5%)

**Status:** Done (2026-03-08)

`hint_cells` was constant at 279 (canvas) / 784 (dashboard) every frame. Healing only
ever produces fixes at corner positions — straight-edge overlaps always yield the same
character. `paint_border()` now emits hints only for the (up to 4) corner positions of
each bordered element, reducing hint_cells to ~16 (canvas) / ~48 (dashboard).

Implemented in `src/counterweight/paint.py` `paint_border()` — replaced full `chars`
dict broadcast with conditional corner-only population inside the `try/except/else` block.

---

### 7. Sparse paint / dirty-region tracking (saves ~1 ms/cycle on static workloads)

**Status:** TODO

`current_paint` is initialized as a full `w×h` dict of BLANK cells (`app.py:110`), so
`diff_paint` iterates all `w×h` entries every frame — 1,920 iterations for an 80×24 terminal
even when only 1 cell changed (dashboard frame counter).

**Required changes:**

1. **Initialize `current_paint` as `{}`** instead of pre-filling with BLANK. BLANK is the
   implicit default (see `.get(pos, BLANK)` usage). Replace the explicit `CLEAR_SCREEN` write
   (currently driven by the BLANK-filled paint dict) with a raw escape sequence instead.

2. **Keep `new_paint` sparse** — `paint_layout` should not write BLANK cells into the dict;
   callers already treat missing positions as BLANK.

3. **`diff_paint` scans `new_paint.keys() | current_paint.keys()`** instead of only
   `current_paint.keys()`. With both dicts sparse, this set is O(content cells), not
   O(terminal size).

**Expected gain:** Dashboard drops from ~1,920 iterations/frame to ~25 (one card's content),
recovering most of the 1.0ms diff cost. Canvas (all cells change) gets no benefit.

Relevant code: `src/counterweight/app.py:110` (init), `app.py:490` (`diff_paint`),
`src/counterweight/paint.py` (`paint_layout`).

---

## Metrics Reference

### Run 1 (before `user_code_ns`)

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

### Extra metrics (run 2)
- `hint_cells` (border heal): constant 279 every cycle
- `diff_cells` (border heal): constant 5 every cycle
- `diff_cells` (paint diff): mean 203
- `bytes` written: mean ~8,544 B
- `num_events`: 4–5 per cycle
- `num_active_effects`: constant 5
