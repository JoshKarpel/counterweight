#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Analyze the counterweight JSON devlog and print timing statistics."""

import argparse
import json
import statistics
import subprocess
from collections import defaultdict


def fetch(last: int) -> list[dict]:
    result = subprocess.run(
        ["uv", "run", "counterweight", "devlog", "--json", "--last", str(last)],
        capture_output=True,
        text=True,
        check=True,
    )
    records = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if line.startswith("{"):
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    return records


def ms(ns_str: str) -> float:
    return int(str(ns_str).replace("_", "")) / 1e6


def pct(val: float, total: float) -> str:
    if total <= 0:
        return "  —  "
    return f"{val / total * 100:5.1f}%"


def summarize(vals: list[float]) -> tuple[float, float, float, float]:
    s = sorted(vals)
    return statistics.mean(vals), statistics.median(vals), s[int(len(s) * 0.95)], max(vals)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--last", type=int, default=500, help="Number of log lines to fetch")
    args = parser.parse_args()

    records = fetch(args.last)
    if not records:
        print("No records found. Is the devlog populated? Run the app first.")
        return

    events: dict[str, list[float]] = defaultdict(list)
    user_code: list[float] = []
    extra: dict[str, list[float]] = defaultdict(list)

    for rec in records:
        event = rec.get("event", "")
        if "elapsed_ns" in rec:
            events[event].append(ms(rec["elapsed_ns"]))
        if "user_code_ns" in rec:
            user_code.append(ms(rec["user_code_ns"]))
        for k in ("hint_cells", "diff_cells", "bytes", "num_events", "num_active_effects"):
            if k in rec:
                extra[f"{event}:{k}"].append(float(str(rec[k]).replace("_", "")))

    # Compute framework overhead = shadow tree - user_code
    shadow = events.get("Updated shadow tree", [])
    framework_overhead = (
        [s - u for s, u in zip(shadow, user_code)] if shadow and user_code and len(shadow) == len(user_code) else []
    )

    cycle_median = statistics.median(events.get("Completed render cycle", [1])) or 1

    order = [
        ("Updated shadow tree", events.get("Updated shadow tree", [])),
        ("  — user_code", user_code),
        ("  — framework overhead", framework_overhead),
        ("Calculated layout", events.get("Calculated layout", [])),
        ("Generated new paint", events.get("Generated new paint", [])),
        ("Healed borders", events.get("Healed borders in new paint", [])),
        ("Diffed new paint", events.get("Diffed new paint from current paint", [])),
        ("Generated instructions", events.get("Generated instructions from paint diff", [])),
        ("Wrote and flushed", events.get("Wrote and flushed instructions to output stream", [])),
        ("Reconciled effects", events.get("Reconciled effects", [])),
        ("Completed render cycle", events.get("Completed render cycle", [])),
    ]

    print(f"\n{'Event':<28} {'N':>5} {'Mean':>8} {'Median':>8} {'%cycle':>7} {'P95':>8} {'Max':>8}")
    print("-" * 80)
    for label, vals in order:
        if not vals:
            continue
        mean, med, p95, mx = summarize(vals)
        n = len(vals)
        print(f"{label:<28} {n:>5} {mean:>7.3f}ms {med:>7.3f}ms {pct(med, cycle_median)} {p95:>7.3f}ms {mx:>7.3f}ms")

    if extra:
        print("\nExtra metrics:")
        for k, vals in sorted(extra.items()):
            print(
                f"  {k}: mean={statistics.mean(vals):.1f}  median={statistics.median(vals):.1f}  min={int(min(vals))}  max={int(max(vals))}"
            )


if __name__ == "__main__":
    main()
