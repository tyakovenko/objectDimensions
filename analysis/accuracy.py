"""Accuracy analysis: compare pipeline measurements to ground truth.

Produces per-measurement error tables and the school gate pass/fail.
IQS scores are pulled from validation.json alongside measurements.

Usage:
    # Single run:
    python analysis/accuracy.py output/20260422_171017_good --object corn_can

    # Multi-run tier comparison (Table 1):
    python analysis/accuracy.py output/run_good output/run_medium \\
        --object corn_can --labels good medium
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


GROUND_TRUTH_PATH = Path(__file__).parent.parent / "data" / "ground-truth.json"

# School gate: both of these must be under GATE_THRESHOLD.
GATE_MEASUREMENTS = {"height", "circumference_mid"}
GATE_THRESHOLD = 0.10


def load_measurements(run_dir: Path) -> dict[str, float]:
    p = run_dir / "measurements.json"
    if not p.exists():
        raise FileNotFoundError(f"No measurements.json in {run_dir}")
    raw = json.loads(p.read_text())
    return {item["name"]: item["value"] for item in raw}


def load_iqs(run_dir: Path) -> float | None:
    p = run_dir / "validation.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    return raw.get("composite_iqs")


def load_truth(object_name: str) -> dict[str, float]:
    all_truth = json.loads(GROUND_TRUTH_PATH.read_text())
    if object_name not in all_truth:
        available = list(all_truth.keys())
        raise KeyError(f"Object '{object_name}' not in ground-truth.json. Available: {available}")
    entry = all_truth[object_name]
    return {k.removesuffix("_in"): v for k, v in entry.items() if k.endswith("_in")}


def compute_errors(measured: dict[str, float], truth: dict[str, float]) -> list[dict]:
    rows = []
    for name, truth_val in sorted(truth.items()):
        if name not in measured:
            rows.append({"name": name, "truth": truth_val, "measured": None,
                         "abs_err": None, "rel_err": None, "gate": name in GATE_MEASUREMENTS})
            continue
        m = measured[name]
        abs_err = abs(m - truth_val)
        rel_err = abs_err / truth_val if truth_val else None
        rows.append({
            "name": name,
            "truth": truth_val,
            "measured": m,
            "abs_err": abs_err,
            "rel_err": rel_err,
            "gate": name in GATE_MEASUREMENTS,
        })
    return rows


def print_run_table(run_dir: Path, rows: list[dict], iqs: float | None, label: str | None) -> bool:
    header = f"\n{'=' * 65}"
    header += f"\n  {run_dir.name}"
    if label:
        header += f"  [{label}]"
    if iqs is not None:
        header += f"  IQS={iqs:.2f}"
    print(header)
    print(f"{'=' * 65}")
    print(f"  {'Measurement':<25} {'Truth':>6} {'Measured':>9} {'AbsErr':>7} {'RelErr':>7}  Gate")
    print(f"  {'-'*25} {'-'*6} {'-'*9} {'-'*7} {'-'*7}  {'-'*4}")

    gate_results = []
    for r in rows:
        if r["measured"] is None:
            gate_col = "(gate)" if r["gate"] else ""
            print(f"  {r['name']:<25} {r['truth']:>6.3f} {'N/A':>9}  {gate_col}")
            if r["gate"]:
                gate_results.append(False)
            continue
        rel_pct = f"{r['rel_err']*100:.1f}%" if r["rel_err"] is not None else "—"
        gate_col = ""
        if r["gate"]:
            passed = r["rel_err"] is not None and r["rel_err"] <= GATE_THRESHOLD
            gate_col = "PASS" if passed else "FAIL"
            gate_results.append(passed)
        print(f"  {r['name']:<25} {r['truth']:>6.3f} {r['measured']:>9.3f} "
              f"{r['abs_err']:>7.3f} {rel_pct:>7}  {gate_col}")

    valid_rels = [r["rel_err"] for r in rows if r["rel_err"] is not None]
    if valid_rels:
        median_rel = statistics.median(valid_rels)
        overall_pass = all(gate_results) if gate_results else False
        verdict = "PASS" if overall_pass else "FAIL"
        print(f"\n  Median rel error (all measurements): {median_rel*100:.1f}%")
        print(f"  Gate ({', '.join(sorted(GATE_MEASUREMENTS))} < {GATE_THRESHOLD*100:.0f}%): {verdict}")

    return all(gate_results) if gate_results else False


def main():
    parser = argparse.ArgumentParser(description="Accuracy analysis for object dimension pipeline")
    parser.add_argument("runs", nargs="+", type=Path, help="Output run directories to analyse")
    parser.add_argument("--object", required=True, help="Object name (matches ground-truth.json key)")
    parser.add_argument("--labels", nargs="*",
                        help="Tier labels for each run, e.g. --labels good medium bad")
    args = parser.parse_args()

    try:
        truth = load_truth(args.object)
    except (FileNotFoundError, KeyError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    labels = args.labels or []
    labels += [None] * max(0, len(args.runs) - len(labels))

    all_pass = True
    for run_dir, label in zip(args.runs, labels):
        try:
            measured = load_measurements(run_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            all_pass = False
            continue
        iqs = load_iqs(run_dir)
        rows = compute_errors(measured, truth)
        passed = print_run_table(run_dir, rows, iqs, label)
        all_pass = all_pass and passed

    print()
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
