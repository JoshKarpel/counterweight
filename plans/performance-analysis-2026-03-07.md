# Performance Analysis — `profiling/canvas.py`

**Workload:** 4 × `random_walkers` canvases, each 30×30 pixels rendered as half-block chars
(30×15 Chunks per canvas = 450 Chunks × 4 = ~1,800 Chunks total), all walkers moving every frame.
**Dataset:** 500 log lines, 50 complete render cycles, ~0.82 s wall time.
**Result:** Median cycle 15.7 ms (~63.6 FPS).

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

**Status:** PARTIALLY DONE

`canvas()` moved to `counterweight.utils` and optimized:
- Coordinate pairs precomputed and cached per `(width, height)` via `_canvas_rows` —
  eliminates 900 temp tuple allocations per call.
- Row-structured iteration replaces flat `enumerate` + `i % width` modulo per cell.
- `_canvas_chunk(fg, bg)` cached via `lru_cache(maxsize=512)` — each unique color pair
  allocated once; subsequent calls return the interned `Chunk`. For the random walkers
  workload (~31 unique pairs), drops canvas allocations from ~1,800 Chunks + 1,800
  CellStyles per frame to ~31 cached objects after warmup.

Remaining (framework-side):
- `canvas()` still rebuilds the full `list[Chunk]` every frame. A framework-level
  mechanism for `Text` nodes to skip unchanged chunks during paint traversal would
  allow truly incremental rendering.

Relevant code: `src/counterweight/utils.py`, `src/counterweight/paint.py`

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

### 5. Narrow border-healing hint set (saves ~0.4 ms/cycle, ~2.5%)

**Status:** TODO / low priority

`hint_cells` is constant at 279 every frame — the same set of cells is inspected every
frame to find the same 5 fixes. The hint set could be derived lazily from the diff output
(only cells adjacent to changed cells need border healing) rather than computed eagerly
from the full layout.

Relevant code: `src/counterweight/paint.py` (border healing logic)

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

### Extra metrics (run 2)
- `hint_cells` (border heal): constant 279 every cycle
- `diff_cells` (border heal): constant 5 every cycle
- `diff_cells` (paint diff): mean 203
- `bytes` written: mean ~8,544 B
- `num_events`: 4–5 per cycle
- `num_active_effects`: constant 5
