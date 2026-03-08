# Plan: Implement Real Text Wrapping (Issue #304)

## Summary

Add four CSS-inspired `text_wrap` modes to counterweight: `none` (existing), `wrap`,
`balance`, and `pretty`. Currently, `TextWrap = Literal["none"]` and `wrap_cells()`
only splits on explicit `\n` characters — text that exceeds the available width simply
overflows. This plan introduces word-aware line breaking and two paragraph-level
layout algorithms.

### Semantics of each mode

| Mode      | Behavior |
|-----------|----------|
| `none`    | No wrapping — lines only break on explicit `\n` (current behavior) |
| `wrap`    | Greedy word wrap: break lines at word boundaries to fit within the available width, falling back to character-level breaks for words longer than the width |
| `balance` | Like `wrap`, but redistributes words across lines so line lengths are as equal as possible (good for headings) |
| `pretty`  | Like `wrap`, but uses a paragraph-level algorithm (Knuth-Plass or similar minimum-raggedness) to avoid orphans and produce even line lengths |

---

## Files to Change

### 1. `src/counterweight/styles/styles.py` — Extend `TextWrap` type

**Current (line 16):**
```python
TextWrap = Literal["none"]
```

**New:**
```python
TextWrap = Literal["none", "wrap", "balance", "pretty"]
```

No other changes needed in this file — the `Style.text_wrap` field already defaults
to `"none"`.

---

### 2. `src/counterweight/layout.py` — Implement wrapping algorithms in `wrap_cells()`

This is the core of the work. The `wrap_cells()` function (lines 173–191) currently
only handles `wrap == "none"`. We need to add three new branches.

#### Shared helper: split cells into words

All wrapping modes need to split cells into logical "words" (sequences of non-space
cells) and "spaces" (space characters). A helper function will do this:

```python
def _split_into_words(cells: Iterable[CellPaint]) -> list[list[CellPaint]]:
    """Split cells into word and whitespace segments.

    Returns a list of segments where each segment is a contiguous run of
    either whitespace or non-whitespace cells. Newline cells produce their
    own single-character segment.
    """
```

#### `wrap` mode — greedy word wrap

Standard greedy algorithm:
1. Split cells into words (honoring explicit `\n`).
2. Place words on the current line if they fit within `width`.
3. If a word doesn't fit and the line is non-empty, start a new line.
4. If a single word exceeds `width`, break it at the character level.
5. Collapse leading whitespace on continuation lines.

#### `balance` mode — balanced line lengths

After performing greedy wrapping to establish the set of words and a baseline
number of lines, re-wrap targeting a narrower effective width so that line lengths
are as uniform as possible:

1. Perform greedy wrap to determine total lines `N`.
2. Compute `target_width = ceil(total_chars / N)` as a starting point.
3. Binary search or iterative narrowing: find the minimum width that still produces
   `N` lines with the greedy algorithm.
4. Re-wrap at that width.

This keeps the algorithm simple (O(n log n) at worst) and avoids the factorial
complexity of a true optimal balancer. For counterweight's use case (terminal text,
not millions of characters), this is perfectly adequate.

#### `pretty` mode — minimum-raggedness (Knuth-Plass style)

Use a dynamic-programming approach for minimum raggedness:

1. Split into words with their lengths.
2. Define a cost function: `cost(i, j) = (width - line_length(words[i..j]))^2`
   when the words fit, `∞` otherwise.
3. DP: `dp[j] = min over i of (dp[i] + cost(i+1, j))` for placing words `i+1..j`
   on one line.
4. Backtrack to find optimal break points.
5. Special case: the last line has zero cost (it's okay for the last line to be
   short), which naturally avoids orphan penalties.

This is O(n * W) where n = number of words, W = width — very fast for terminal text.

#### Updated `wrap_cells()` structure

```python
def wrap_cells(
    cells: Iterable[CellPaint],
    wrap: TextWrap,
    width: int | None,
) -> list[list[CellPaint]]:
    if width is not None and width <= 0:
        return []

    if wrap == "none":
        # ... existing code ...

    # For all wrapping modes, first split on \n to get paragraphs,
    # then wrap each paragraph independently.
    paragraphs = _split_on_newlines(list(cells))

    if wrap == "wrap":
        return _flatten([_greedy_wrap(p, width) for p in paragraphs])
    elif wrap == "balance":
        return _flatten([_balance_wrap(p, width) for p in paragraphs])
    elif wrap == "pretty":
        return _flatten([_pretty_wrap(p, width) for p in paragraphs])
    else:
        assert_never(wrap)
```

When `width is None` (unconstrained), all wrapping modes degrade to the same
behavior as `"none"` — no wrapping is possible without a width constraint.

---

### 3. `codegen/generate_utilities.py` — Generate `text_wrap_*` utility constants

Add a block similar to the `text_justify` block (around line 500):

```python
for w in literal_vals(Style, "text_wrap"):
    generated_lines.append(f'text_wrap_{w} = Style(text_wrap="{w}")')
```

Then run `just codegen` to regenerate `src/counterweight/styles/utilities.py`.

This will produce:
```python
text_wrap_none = Style(text_wrap="none")
text_wrap_wrap = Style(text_wrap="wrap")
text_wrap_balance = Style(text_wrap="balance")
text_wrap_pretty = Style(text_wrap="pretty")
```

---

### 4. `src/counterweight/styles/__init__.py` — Export new utilities

Verify the new `text_wrap_*` constants are exported. If utilities are re-exported
via `__init__.py` or `__all__`, add the new names.

---

### 5. Tests — `tests/test_layout.py` (or new `tests/test_wrap.py`)

Add thorough tests for `wrap_cells()` covering:

- **`wrap` mode:**
  - Basic word wrapping within width
  - Long words broken at character level
  - Explicit `\n` respected
  - Width exactly equal to text length (no wrap needed)
  - Single word that fits exactly
  - Empty input
  - Width of 1 (every character on its own line)

- **`balance` mode:**
  - Two words that fit on one line → stays one line
  - Four equal-length words on a width that forces 2 lines → balanced split
  - Heading-like short text → roughly equal line lengths

- **`pretty` mode:**
  - Avoids orphaned single short word on last line
  - Produces more even line lengths than greedy for multi-line paragraphs
  - Falls back gracefully when width is very tight
  - Matches greedy when text fits in one line

- **Edge cases (all modes):**
  - `width=None` → no wrapping (single line per paragraph)
  - `width=0` → empty result
  - Styled `Chunk` cells maintain correct styles across line breaks
  - Mixed styled and unstyled text

---

### 6. `_measure_text()` in `layout.py` — No changes needed

The measurement function already calls `wrap_cells()` and computes dimensions from
the result. Since `wrap_cells()` will now return properly wrapped lines, measurement
will automatically account for wrapping.

### 7. `paint_text()` in `paint.py` — No changes needed

Similarly, the paint function already calls `wrap_cells()` and renders the resulting
lines. No modifications required.

---

## Implementation Order

1. Extend `TextWrap` type in `styles.py`
2. Implement `_split_on_newlines()` helper in `layout.py`
3. Implement `_greedy_wrap()` in `layout.py`
4. Add `wrap` branch to `wrap_cells()` + write tests
5. Implement `_balance_wrap()` in `layout.py` + tests
6. Implement `_pretty_wrap()` in `layout.py` + tests
7. Update codegen and run `just codegen`
8. Verify exports and run full test suite (`just test`)

## Dependencies

No new dependencies are needed. The algorithms are straightforward enough to
implement in pure Python. The DP for `pretty` mode uses only built-in data
structures.

## Risks and Considerations

- **Performance**: Terminal text is small (typically < 200 columns, < 50 lines).
  Even the DP algorithm is O(n * W) which is trivially fast at this scale.
- **Styled text**: `CellPaint` carries per-character styles. The wrapping
  algorithms operate on `list[CellPaint]` so styles are preserved across breaks
  by construction.
- **Backward compatibility**: The default `text_wrap="none"` is unchanged, so
  existing applications behave identically.
