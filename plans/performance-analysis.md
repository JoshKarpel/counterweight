# Performance Analysis — `profiling/canvas.py`

**Workload:** 4 × `random_walkers` canvases, each 30×30 pixels rendered as half-block chars
(30×15 Chunks per canvas = 450 Chunks × 4 = ~1,800 Chunks total), all walkers moving every frame.
**Dataset:** 500 log lines, 50 complete render cycles, ~0.82 s wall time.
**Result:** Mean cycle 16.3 ms (~61.5 FPS), σ = 0.72 ms — very stable.

---

## Render Cycle Breakdown

| Sub-step | Mean (ms) | % of cycle |
|---|---|---|
| Generated new paint | 5.31 | 32.7% |
| Calculated layout | 4.08 | 25.1% |
| Updated shadow tree | 2.72 | 16.7% |
| Diffed new paint from current paint | 1.24 | 7.6% |
| Wrote and flushed to output | 0.46 | 2.8% |
| Healed borders | 0.41 | 2.5% |
| Generated instructions from diff | 0.19 | 1.2% |
| Reconciled effects | 0.02 | 0.1% |
| Unaccounted overhead | 1.83 | 11.2% |

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

### 2. Incremental paint for Text nodes (saves ~2–4 ms/cycle, ~15–25%)

**Status:** TODO

`canvas()` in `profiling/canvas.py` rebuilds all `width * (height/2)` Chunk objects
unconditionally every frame. With `n=30` walkers in `w*h=900` cells, only ~3.3% of cells
change per frame. The paint step traverses all ~1,800 Chunks regardless.

Two angles:
- **Framework side:** allow `Text` nodes to declare their chunks as a diff-friendly
  structure so unchanged chunks can be skipped during paint traversal.
- **User side:** `canvas()` could track the previous cell dict and only rebuild changed
  Chunks. This is a lower-level workaround but immediately available to app authors.

Relevant code: `src/counterweight/paint.py`, `profiling/canvas.py`

---

### 3. Skip shadow tree reconciliation for memoized components (saves ~1–2 ms/cycle, ~10%)

**Status:** TODO

The 4 `random_walkers` components each have independent, fully static subtree structure.
If a component's output is referentially equal to the previous render (or its props are
unchanged), reconciliation of its subtree could be skipped — analogous to `React.memo`.

This is harder to apply to `random_walkers` specifically (state changes every frame) but
would benefit stable sibling subtrees like `header()` and `fps_display()` (mostly static).

Relevant code: `src/counterweight/app.py` (shadow tree update logic)

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

## Metrics Reference (50-cycle sample)

| Event | Count | Mean | Median | P95 | P99 | Max |
|---|---|---|---|---|---|---|
| Handled events | 49 | 0.007 ms | 0.006 ms | 0.010 ms | 0.010 ms | 0.010 ms |
| Updated shadow tree | 49 | 2.718 ms | 2.654 ms | 3.316 ms | 3.750 ms | 3.750 ms |
| Calculated layout | 49 | 4.077 ms | 4.003 ms | 4.704 ms | 5.211 ms | 5.211 ms |
| Generated new paint | 50 | 5.313 ms | 5.246 ms | 6.071 ms | 7.137 ms | 7.137 ms |
| Healed borders in new paint | 50 | 0.406 ms | 0.390 ms | 0.508 ms | 0.685 ms | 0.685 ms |
| Diffed new paint from current paint | 50 | 1.238 ms | 1.199 ms | 1.481 ms | 1.813 ms | 1.813 ms |
| Generated instructions from paint diff | 50 | 0.193 ms | 0.178 ms | 0.328 ms | 0.369 ms | 0.369 ms |
| Wrote and flushed to output | 50 | 0.458 ms | 0.458 ms | 0.750 ms | 0.853 ms | 0.853 ms |
| Reconciled effects | 50 | 0.023 ms | 0.021 ms | 0.036 ms | 0.046 ms | 0.046 ms |
| **Completed render cycle** | **50** | **16.261 ms** | **16.241 ms** | **17.696 ms** | **18.311 ms** | **18.311 ms** |

Extra metrics (new):
- `user_code_ns` (shadow tree update): time spent inside component functions; remainder is framework reconciliation overhead

Extra metrics (original run, before `user_code_ns` was added):
- `hint_cells` (border heal): constant 279 every cycle
- `diff_cells` (border heal): constant 5 every cycle
- `diff_cells` (paint diff): mean 203, range 192–212
- `bytes` written: mean 8,544 B, range 8,083–8,901 B
- `num_events`: 4–5 per cycle
- `num_active_effects`: constant 5
