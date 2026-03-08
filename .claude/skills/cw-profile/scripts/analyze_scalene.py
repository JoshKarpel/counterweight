#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Analyze a Scalene CPU profile JSON and print the hottest lines in counterweight source files."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        nargs="?",
        default="scalene-profile.json",
        help="Path to Scalene JSON profile (default: scalene-profile.json)",
    )
    parser.add_argument("--top", type=int, default=30, help="Number of hot lines to show")
    parser.add_argument("--min-pct", type=float, default=0.1, help="Minimum CPU%% to include")
    args = parser.parse_args()

    path = Path(args.profile)
    if not path.exists():
        print(f"Profile not found: {path}")
        print("Run: just profile profiling/canvas.py")
        return

    data = json.loads(path.read_text())
    files = data.get("files", {})

    rows = []
    file_totals = []

    for filepath, fdata in files.items():
        if "counterweight" not in filepath or "site-packages" in filepath:
            continue
        short = filepath.split("counterweight/")[-1]
        file_totals.append((fdata.get("percent_cpu_time", 0.0), short))
        for ldata in fdata.get("lines", []):
            cpu = ldata.get("n_cpu_percent_python", 0.0) + ldata.get("n_cpu_percent_c", 0.0)
            if cpu < args.min_pct:
                continue
            rows.append((cpu, short, ldata.get("lineno", 0), ldata.get("line", "").rstrip()))

    rows.sort(reverse=True)

    print(f"\nTop {args.top} hot lines (threshold: {args.min_pct}% CPU)\n")
    print(f"{'CPU%':>6}  {'File':<35} {'Line':>5}  Source")
    print("-" * 100)
    for cpu, filepath, lineno, src in rows[: args.top]:
        print(f"{cpu:>6.2f}  {filepath:<35} {lineno:>5}  {src[:60]}")

    if file_totals:
        print("\nPer-file CPU totals:")
        for pct, name in sorted(file_totals, reverse=True):
            if pct >= 0.5:
                print(f"  {pct:>6.2f}%  {name}")


if __name__ == "__main__":
    main()
