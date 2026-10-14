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

A full cold run takes about 70 minutes on 2 CPUs, most of it in `app.render_loop`,
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
  `paint.justify_line` sits behind `line_cells`, `CellStyle.__post_init__` behind its flyweight.
  `tests/conftest.py` empties every counterweight `lru_cache` (flyweights included) at the start of each worker.
  It also empties them before every test in mutmut's stats pass, which maps each function to the tests that run it,
  so a function behind a cache is mapped to every test that reaches it, not just the first to miss.
  A new cache needs nothing extra, but a test that compares a cached object by identity with one built before
  the caches were emptied (`cell is BLANK`, where `Cell` is a flyweight) fails in every mutmut worker,
  counting every mutant it reaches as killed. Compare such values by equality.
- **The baseline runs each test twice in one process** (the stats pass, then the clean run),
  so state a test leaves in a module or class, like a `ClassVar` list it appends to, has to be reset by the test.
- **Code that runs at import never runs under a mutant.** mutmut imports the source in its parent process,
  so a module-level table built by calling a function (`input_parsing`'s `ALT_KEYS` and `SEQUENCE_KEYS`,
  `text_editing`'s `KEY_EDITS`, `markdown`'s `PARSER` patched by `wrap_gfm_autolink_rules`) is built by the unmutated
  function, and tests that only read the table can't see that function's mutants.
  Test such a function by calling it directly (`sequence_keys()`, `move_to(word_start)`), as its own contract.
- **Decorators run before any mutant does.** mutmut imports the test modules in its parent process,
  so a module-level `@component` runs the unmutated `component`.
  A test that pins what a decorator builds has to apply it inside the test body.
- **Autopilot never yields to effects.** `app`'s autopilot loop doesn't await anything that suspends,
  so an effect started by a render hasn't run when the next autopilot event is handled:
  `use_mouse` hasn't subscribed when the first `MouseMoved` arrives, and that event is lost.
  Test hooks that need a running effect with `tests.rendering.render`, which yields once after starting effects.
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
  `place`'s `ValueError` for a `Text` or `Canvas` whose overflow is `Scroll`, the `ValueError`s of `scroll_on_keys`,
  `scroll_on_wheel` and `focus_receiver_on_press`, `use_focus`'s `DuplicateUseFocus` and `ChangedFocusHandle`,
  `ShadowTree`'s `DuplicateElementHandle` and `DuplicateFocusHandle`, `render_loop`'s `UnsettledFocus`,
  the exception groups of `cancel_tasks`, and `teardown_failure`'s `RuntimeError`.
  Tests pin what each message names (the component, the hook types, the key, the size, the handles), not its wording.
- **`case _: return None` dropped** from a function that returns `None` without it:
  `on_click`, `tab_focus`, `focus_on_press`, `focus_receiver_on_press`, `clear_focus`,
  `use_text_input`'s and `use_text_area`'s `on_press`, `key_scroll`, and `JoinedBorderParts.select`.
- **`ScrollIntoView` without `inline="nearest"`**, in `focus_into_view` and `use_text_input`'s `on_input` and `on_press`:
  `inline` defaults to `"nearest"`. Dropping `block="nearest"` is killed, since `block` defaults to `"start"`.
- **`key is None` guards disabled where the lookup misses `None` anyway**: `scroll_in`'s
  (`layouts.scrolls.get(None, NO_SCROLL)`) and `captured`'s `press.captor is None`
  (`deliver` finds no handler for `None`). Both are keyed by `NodeKey`; the guards narrow the type for the checker.

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
- **`Hooks.use_focus`'s `hook.auto_focus = None` on a later run.** `reconciled_focus` reads `auto_focus` only for
  the nodes an update mounted, which created their hook in that update, and a purity re-run writes to a detached copy,
  so the value a later run stores is never read.
- **`Hooks.use_effect`'s initial `deps=None`** instead of `(object(),)`.
  `handle_effects` reruns an effect whose `new_deps` is `None` or differs from `deps`,
  and `None` differs from every tuple, so a mounting effect runs either way.

### App

- **`render_loop`'s truthiness swaps.** `should_quit`, `should_bell` and `should_render` set to `None`,
  `should_suspend` set to `""`, `events = None` after a timeout, `is_suspended = None`, `should_clear = None`
  after a frame, and `FocusPrevious`'s `is_forward=None`: each is only read for truthiness.
- **`render_loop`'s initial `should_clear`, `None` or `False`.** `handle_screen_size_change` sets it to `True`
  before the first frame reads it, and the `finally` block never reads it.
- **The warmup's pending scroll when nothing is focused** (`(focused is None) and False`, queueing
  `focus_into_view(None)`): `scroll_requests` drops a control whose `Subtree` key is `None`,
  and the first frame clears `pending_scrolls`.
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

- **`sequence_keys`' `\x1B` for `\x1b`**: a hex escape's case doesn't change the byte.
- **`parse_input`'s initial `Step(end=None)` or `Step(end=1)`**: the loop replaces `step` before reading its `end`,
  and after the loop only its `paste_searched` is read, which is `None` either way.
- **`parse_input`'s `(paste_searched or 1)` and `else 1`**: `max` clamps any count up to
  `len(PASTE_START) + len(PASTE_END) - 1` to the start of the paste's text, so 0 and 1 search from the same place.
- **`parse_escaped_sequence`'s `end` when it finds no event** (`start ± 1`, `start + 2`, `None`), and its
  `events=(None,)` for an unknown sequence: its only caller, `parse_alt`, reads that `end` only to compare it with
  `following`, which none of them equal, and `(None,)` matches its `case (KeyPressed(...), *rest)` no more than `()`
  does, so either way `parse_alt` returns Escape and `end=following`.
- **The codec name `"UTF-8"`** in `parse_paste` and `parse_text`: codec lookup ignores case.
- **`read_keys`' `is_final=None`**: `parse_input` and its helpers read `is_final` only for truthiness.
- **`put_parsed_keys`' `paste_searched=None` or dropped** in its call to `parse_input`: the count only saves work.
  By `parse_input`'s contract the bytes it skips can't hold the paste's end, so searching them again finds the same.
  Dropping the count `KeyReader` stores is killed, since tests read that state.
- **`read_keys`'s read size grown** (`3**10`, `2**11`): a burst longer than 1024 bytes is all a test could
  use to tell, and how a burst splits across reads isn't a contract. Shrinking it (`2 * 10`) is killed.

### Headless components

- **`line_start_at`'s `rfind("\n", None, offset)`**: `str.rfind` reads a `None` start as 0.
- **`blank_separated_word_start`'s first loop at `position >= 0`.** At 0, `previous_cluster` returns 0,
  so the slice is empty and `"".isspace()` is false, which stops the loop as `> 0` does.
- **`line_rows`' `zip(..., strict=True)`** dropped, `False` or `None`: the second sequence is `starts[1:]`
  plus the line's end, so it's always as long as `starts`.
- **`drawn`'s `row.start <= cursor <= row.end`** only adds the end of a soft row, which the row after it
  also matches (it starts there), and that later match overwrites `cursor_row`.
- **`drawn`'s `after_cursor` guard as `or True` or `<=`.** At the end of the cursor's row, `at_cursor` is the
  one-cell space, and `value[cursor + 1 : cursor]` is empty.
- **`use_text_input`'s and `use_text_area`'s initial `EditableText(value=None, ...)`.** The state is only read
  through `following(value)`, which for a text whose value differs returns `EditableText(value, len(value), None)`,
  exactly the initial text.

### Markdown and highlighting

- **`block`'s and `span`'s `case _` dropped, and their `ValueError(None)`**: `PARSER` enables no rule that makes
  any other block or inline span, so the arm never runs (it's `# pragma: no cover` for the same reason).
- **`block`'s `split(maxsplit=2)` for a fence's info string**: `fenced_code` reads only the first word,
  and whether there is one.
- **Lexer names in another case, and `"XXtextXX"`** (`"YAML"` in `block`, `"TEXT"` and `"XXtextXX"` in `fenced_code`):
  Pygments looks lexers up by lowercased alias, and an unknown name raises `ClassNotFound`,
  which `fenced_code` answers with the same `"text"` block.
- **`fill(2)` on display math beside its label, and `grow(2)` on a list item's column**: each is the only
  growing child of its row, so it takes all the free space whatever its factor.
- **`alert`'s title spans with `styles=None`**: markdown-it writes the title as the alert's kind, one text token,
  and `span` reads no style for text.
- **`zip(..., strict=True)` dropped, `False` or `None`, in `wrap_gfm_autolink_rules`, `list_block` and `footnotes`**:
  markdown-it's default rule chain holds every enabled rule, so it's as long as `get_active_rules()`,
  and list markers and footnote numbers are built one per item and one per footnote.

### Layout

- **`scroll_of`'s `offset=None`** in the unclamped `Scroll`: it's only read through `max_offset`,
  and `replace` sets the clamped offset before the `Scroll` leaves the function.
- **`settled_scroll`'s `_resolve_layout(..., 1, 0)`.** It reads only the padding box's top, width and height,
  which a horizontal shift doesn't change.
- **`aligned`'s `"nearest"` boundaries** (`<=` for `is_cut_at_start`, `>=` for `is_cut_at_end`, `<` for `fits`).
  A box exactly at a view edge, or exactly the view's size, gets the same offset from either branch:
  aligning the edge it already sits on leaves the offset where it is.
- **`_append_style_change`'s `and` as `or`.** `layout_style` is cached, so equal styles are the same object
  and the identity test already decides; they differ only after an eviction, which costs a redundant `SetStyle`.
- **`_measure_leaf`'s known height (for a text) `None`, or either known dimension ignored.** Taffy uses a known dimension
  in place of the measured one (probed by running the suite with each variant patched in).
- **Initial values the code never reads.** `_extract_words_and_spaces`'s `current_word = None`,
  `_greedy_line_count`'s initial `length` and `pending_space_len` (`None`, `1`, or `1` after the last word),
  and `_wrap_at_target`'s `current_width` (`None`, `1`) and `pending_space = None`:
  each is replaced, or read only for truthiness, before anything else reads it.
- **`_wrap_at_target`'s `zip(..., strict=True)`** dropped, `False` or `None`: the widths are built from the words.
- **`_flatten_long_words`' spacing between chunks** (`j > 0 and False`, `j > 1`) and its first-word guard
  (`i > 0 or True`, `i >= 0`), and `cells_width(word) >= width`. A word exactly `width` wide breaks into itself,
  the first word's first chunk is never preceded by a space, and a chunk that isn't a word's last leaves less room
  than the next chunk's first cluster needs, so no line ever holds two chunks of one word.
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

- **`Paint.write_row`'s `x <= low`.** At `x == low`, `skip` is 0 either way.
- **`justify_line`'s `space < 0`.** Padding by zero spaces returns the same line.
- **`svg`'s `"0.2F"` format, its dropped empty `style` attributes, and `0 / x_mul` and `0 / y_mul`**: they render identically.
- **`paint_element`'s `resolved.visible is resolved.border` disabled (`and False`).** `visible` is
  `border.intersection(clip)`, which is `border` itself only when the clip contains the non-empty border box,
  and every corner `border_fills` returns is a cell of that box, so filtering them by `clip.contains` keeps them all.
- **`paint_element`'s `lines = None` for a `Div`**: a `Div`'s lines are only read through `not lines`.
- **`paint_element`'s `child_clip(clip, None, ...)`**: with `clip_to="padding"`, `child_clip` never reads `screen`.
- **`paint_to_instructions`'s initial `style = ""`.** It differs from every cell's style, as `None` does.
- **`CellStyle` and `ResolvedCellStyle`'s `hash(None)`.** Every instance hashing alike only slows caches;
  equality still decides.

### Styles

- **`Style._resolve`'s fallbacks that equal the defaults.** `or_default(self.z, None)`, since `STYLE_DEFAULTS.z`
  is `None`, and `resolve_cell_style` without its second argument for `border_style` and `text_style`,
  whose default is `CELL_STYLE_DEFAULTS`, which both of `STYLE_DEFAULTS`' cell styles are.

### Utilities

- **`unordered_range`'s `b <= a`.** At `a == b`, both steps give the one-element range.
- **`render_exception`'s `isinstance(frames, list) or True`.** `without_logging` always writes `frames`
  as a list; the check narrows the parsed JSON for the type checker.
