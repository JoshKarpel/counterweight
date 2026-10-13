---
name: cw-mutate
description: Mutation testing workflow for the counterweight project with mutmut. Use when running `just mutate`, triaging or killing surviving mutants, judging whether a counterweight mutant is equivalent, or checking how well the tests pin the shadow tree, hooks, and equivalence logic. Holds the project's known equivalent mutants and its mutmut traps; load it alongside the general `mutation-testing-python` skill.
---

# Counterweight Mutation Testing

mutmut mutates all of `src/counterweight` (configured under `[tool.mutmut]` in `pyproject.toml`).
Every module has no survivors beyond the equivalents listed below,
so a new survivor is a test hole (or a new equivalent to argue for and add here).

## Run it

```bash
just mutate                                   # every mutant without a cached verdict
just mutate 'counterweight.shadow.*'          # re-run only these mutants, cached or not
uv run mutmut results                         # what survived
uv run mutmut show <mutant>                   # one mutant's diff
```

A full cold run takes about 35 minutes on 2 CPUs, most of it in `app.render_loop`,
whose mutants each re-run every app-level test.
When working on the state modules, pass their globs to skip the rest.

Start from `rm -rf mutants` after editing a source file or a test that already existed,
and after any run that died partway: the cache keeps verdicts and the test map from before,
and a run that crashed can leave mutants marked "no tests" that never ran.

## Traps specific to this project

- **Runaway memory.** A mutant can turn a loop that must advance into one that appends forever
  (`layout._wrap_pretty`'s line reconstruction, when its DP table stays empty), at hundreds of megabytes a second.
  `tests/conftest.py` caps each mutmut worker's address space on Linux so such a mutant raises
  `MemoryError` and counts as killed. Without that cap, two of them exhaust a small VM's memory before
  mutmut's timeout fires, and a VM without swap hangs.
- **Warm caches hide mutants.** Each mutmut worker forks from a parent that has already run every test,
  so every `lru_cache` is full, and a function that only runs on a cache miss never runs under its mutant:
  `paint.justify_line` and the wrap helpers sit behind `text_lines`, `CellStyle.__post_init__` behind its flyweight.
  `tests/conftest.py` empties every counterweight `lru_cache` (flyweights included) at the start of each worker.
  A new cache needs nothing extra, but a test that relies on a cached object's identity across tests will fail
  under mutmut only.
- **The baseline runs each test twice in one process** (the stats pass, then the clean run),
  so state a test leaves in a module or class, like a `ClassVar` list it appends to, has to be reset by the test.
- **Decorators run before any mutant does.** mutmut imports the test modules in its parent process,
  so a module-level `@component` runs the unmutated `component`.
  A test that pins what a decorator builds has to apply it inside the test body.
- **Autopilot never yields to effects.** `app`'s autopilot loop doesn't await anything that suspends,
  so an effect started by a render hasn't run when the next autopilot event is handled:
  `use_mouse` hasn't subscribed when the first `MouseMoved` arrives, and that event is lost.
  Test hooks that need a running effect with `tests.rendering.render`, which yields once after starting effects.
- **The devlog's writer thread can run the garbage collector.** A collection it triggers drops waxy objects
  from cyclic garbage on that thread, which raises because waxy's types can't be dropped off the main thread,
  and `-Werror` fails whichever test was running. mutmut's stats pass allocates enough to make this likely.
  `tests/conftest.py` keeps the collector off and collects the youngest generation after each test instead.
- **Hypothesis finds some mutants only rarely.** The wrap property tests in `tests/test_wrap_algorithms.py`
  check against slow reference implementations, but 100 random paragraphs seldom separate the squared-slack cost
  or its tie-breaking from a near miss. Each counterexample a longer search found is pinned with `@example`,
  so those kills don't depend on luck; do the same for a new survivor a longer search can kill.
- **The devlog is pinned, not prose.** `docs/performance.md` documents the devlog, so tests assert its exact lines:
  `tests/test_devlog.py` and `test_performance_guide.py` for the render loop's,
  `tests/inputs/test_terminal_input.py` for `read_keys`'.
  Their message, field, and value mutants are killed rather than documented.
- **Keep `--cov` out of `addopts`.** Coverage is gated at 100% through a bare `just test` and CI, which pass `--cov`.
  mutmut runs pytest itself, against a copy of the source the coverage config doesn't name and with only the tests
  that reach each mutant, so a gate there fails the baseline and counts every mutant as killed.
- `tests/test_mkdocs_utility_tables.py` is skipped under mutmut: it lists the utilities module's public names,
  and mutmut adds its own.

## Known equivalent mutants

Each is equivalent for the reason given; recheck the reason, not just the shape, when a new survivor resembles one.

### Across modules

- **Diagnostic prose.** `XX` wraps and case changes of the fixed sentences in `InconsistentHookExecution`
  (`update_node`), `ImpureComponent` (`check_is_pure`), `StaleMemo` (`Hooks.use_memo`),
  the exception groups of `cancel_tasks`, and `teardown_failure`'s `RuntimeError`.
  Tests pin what each message names (the component, the hook types, the key, the size), not its wording.

### State

- **`check_is_pure`'s `zip(..., strict=True)`** dropped or `False`/`None`.
  Two nodes' children are zipped only after their elements matched, and a node's children come from its element,
  so the lengths are always equal.
- **`ShadowNode.detached`'s `element=None`, and `Hooks.detached`'s `clocks` (`None` or dropped) and
  `mount_status` (`is_mounted=None`).** A detached tree is only re-rendered by `check_is_pure`,
  where every node is in `paths` and `dirty_nodes`: an element node is rebuilt from `next` without reading its
  previous element, a node's `clocks` are read only by `ShadowTree` and `is_dirty`, which never see the copy,
  and its `mount_status` is read only by a `use_state` hook created on the copy,
  which a re-run can only create on its way to raising `InconsistentHookExecution`.
- **Truthiness swaps.** `unmount`'s `is_mounted = None`, `update_shadow`'s `check_purity=None`,
  and `equivalent_within`'s `case _: return False` dropped (returning `None`):
  each value is only ever read for truthiness.
- **`Hooks.use_effect`'s initial `deps=None`** instead of `(object(),)`.
  `handle_effects` reruns an effect whose `new_deps` is `None` or differs from `deps`,
  and `None` differs from every tuple, so a mounting effect runs either way.

### App

- **`render_loop`'s truthiness swaps.** `should_quit`, `should_bell` and `should_render` set to `None`,
  `should_suspend` set to `""`, and `events = None` after a timeout: each is only read for truthiness.
- **`handle_control`'s `case None: pass` dropped.** A `match` with no matching case does nothing.
- **`Dummy()` replaced by `None` in the event queue.** It only wakes the loop, and `None` matches no case either.
- **The available size, `None` or dropped**, in `render_loop` (warmup and frames) and `LayoutTree.compute`.
  The screen element has an explicit size and grid tracks, so the space offered to it changes nothing.
- **`screen_element_style`'s `size_width` and `size_height`, `None` or dropped.**
  The explicit grid tracks already size the screen element.
- **The warmup's `instant=read_clock()` dropped** (reading `BEGINNING`). `use_clock` uses its mount reading
  only through its monotonic time, which is zero at the start either way,
  and the first painted frame's wall time is in a later tick, so it takes a fresh reading.
- **`layout_changes(None, shadow)` in place of the previous shadow.** Every node is created again,
  which lays out the same; it only throws away taffy's cached layout.

### Input

- **`read_keys`'s read size grown** (`3**10`, `2**11`): a burst longer than 1024 bytes is all a test could
  use to tell, and how a burst splits across reads isn't a contract. Shrinking it (`2 * 10`) is killed.

### Layout

- **`_append_style_change`'s `and` as `or`.** `layout_style` is cached, so equal styles are the same object
  and the identity test already decides; they differ only after an eviction, which costs a redundant `SetStyle`.
- **`MeasurableText.of`'s `text_cells(content, None)`.** Measuring reads only the cells' widths.
- **`_measure_text`'s known height `None`, or either known dimension ignored.** Taffy uses a known dimension
  in place of the measured one (probed by running the suite with each variant patched in).
- **Initial values the code never reads.** `_extract_words_and_spaces`'s `current_word = None`,
  `_greedy_line_count`'s `length = None` and `pending_space_len` (`None`, `1`, or `1` after the last word),
  and `_wrap_at_target`'s `current_width` (`None`, `1`) and `pending_space = None`:
  each is replaced, or read only for truthiness, before anything else reads it.
- **`_wrap_at_target`'s `zip(..., strict=True)`** dropped, `False` or `None`: the widths are built from the words.
- **`_flatten_long_words`' spacing between chunks** (`j > 0 and False`, `j > 1`) and its first-word guard
  (`i > 0 or True`, `i >= 0`), and `cells_width(word) >= width`. A word exactly `width` wide breaks into itself,
  the first word's first chunk is never preceded by a space, and a chunk that isn't a word's last leaves less room
  than the next chunk's first cluster needs, so no line ever holds two chunks of one word.
- **`_break_long_word`'s `room` at width 1** (`width > 1 or True`, `width >= 1`): a room of 0 takes one
  cluster per chunk without a hyphen, as a room of 1 does.
- **`_wrap_balance`'s `k < 1`** sends a one-line paragraph through the search, which finds the full width again,
  and its `/` midpoint leaves the target strictly between the answer and the answer plus one,
  which wraps the same since cell widths are whole.
- **`_wrap_pretty`'s constant shifts and slack.** `prefix` or `space_prefix` starting at 1 shifts every entry,
  so every difference is unchanged; `dp[n] = 1.0` and a last-line cost of `1.0` add one to every candidate;
  `n + 2`-long tables, `bp` starting at 1, and the outer loop starting at `n + 1` or running to `-2`,
  or the inner loop starting at 0, only add entries or iterations that are never read or never win;
  and the single-word guard on the space length (`or True`, `>=`, `j > i - 1`) only changes `j == i + 1`,
  where the space length is 0 either way.

### Paint and output

- **`Paint.write_row`'s `x <= 0` and `x < 1`.** At `x == 0`, `skip` is 0 either way.
- **`justify_line`'s `space < 0`.** Padding by zero spaces returns the same line.
- **`svg`'s `"0.2F"` format, its dropped empty `style` attributes, and `0 / x_mul`**: they render identically.
- **`paint_to_instructions`'s initial `style = ""`.** It differs from every cell's style, as `None` does.
- **`CellStyle` and `ResolvedCellStyle`'s `hash(None)`.** Every instance hashing alike only slows caches;
  equality still decides.
- **`JoinedBorderParts.select`'s `case _: return None` dropped.** The function returns `None` without it.

### Utilities

- **`unordered_range`'s `b <= a`.** At `a == b`, both steps give the one-element range.
- **`render_exception`'s `isinstance(frames, list) or True`.** `without_logging` always writes `frames`
  as a list; the check narrows the parsed JSON for the type checker.
