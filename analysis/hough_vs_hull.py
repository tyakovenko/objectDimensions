"""Hough circle vs. visual hull circumference comparison.

Compares diameter estimates from both methods across quality tiers against
ground truth. Demonstrates where per-view (Hough) robustness beats multi-view
intersection (hull) and vice versa.

Usage:
    python analysis/hough_vs_hull.py \\
        --good-hull  output/20260423_105356_good \\
        --good-hough output/20260422_212608_good \\
        --medium-hull  output/20260422_211224_medium \\
        --medium-hough output/20260422_212948_medium \\
        --bad-hull  output/bad/20260423_095526_bad \\
        --bad-hough output/20260423_105808_bad \\
        --object corn_can
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

GROUND_TRUTH_PATH = Path(__file__).parent.parent / "data" / "ground-truth.json"


def load_measurements(run_dir: Path) -> dict[str, float]:
    p = run_dir / "measurements.json"
    raw = json.loads(p.read_text())
    return {item["name"]: item["value"] for item in raw}


def load_iqs(run_dir: Path) -> float:
    p = run_dir / "validation.json"
    return json.loads(p.read_text())["composite_iqs"]


def diameter_from_run(m: dict[str, float]) -> float | None:
    """Extract diameter from either measurer output."""
    if "diameter_mid" in m:
        return m["diameter_mid"]
    if "circumference_mid" in m:
        return m["circumference_mid"] / math.pi
    return None


def rel_err(measured: float | None, truth: float) -> float | None:
    if measured is None:
        return None
    return abs(measured - truth) / truth


def main():
    parser = argparse.ArgumentParser(description="Hough vs. hull comparison table")
    parser.add_argument("--good-hull", type=Path, required=True)
    parser.add_argument("--good-hough", type=Path, required=True)
    parser.add_argument("--medium-hull", type=Path, required=True)
    parser.add_argument("--medium-hough", type=Path, required=True)
    parser.add_argument("--bad-hull", type=Path, required=True)
    parser.add_argument("--bad-hough", type=Path, required=True)
    parser.add_argument("--object", required=True, help="Object name (matches ground-truth.json)")
    args = parser.parse_args()

    truth_all = json.loads(GROUND_TRUTH_PATH.read_text())
    if args.object not in truth_all:
        raise KeyError(f"Object '{args.object}' not in ground-truth.json")
    t = truth_all[args.object]
    truth_diam = t.get("diameter_mid_in")
    truth_circ = t.get("circumference_mid_in")
    if truth_diam is None and truth_circ is not None:
        truth_diam = truth_circ / math.pi

    tiers = [
        ("good",   args.good_hull,   args.good_hough),
        ("medium", args.medium_hull, args.medium_hough),
        ("bad",    args.bad_hull,    args.bad_hough),
    ]

    W = 94
    print(f"\n{'Hough Circle vs. Visual Hull — Diameter Comparison':^{W}}")
    print(f"{'Object: ' + args.object + '  |  Truth diameter: ' + f'{truth_diam:.3f} in':^{W}}")
    print("=" * W)
    print(f"  {'Tier':<8} {'IQS':>5}  {'Hull diam':>10}  {'Hull err':>9}  "
          f"{'Hough diam':>11}  {'Hough err':>10}  {'Winner'}")
    print(f"  {'-'*8} {'-'*5}  {'-'*10}  {'-'*9}  {'-'*11}  {'-'*10}  {'-'*6}")

    for tier, hull_dir, hough_dir in tiers:
        m_hull  = load_measurements(hull_dir)
        m_hough = load_measurements(hough_dir)
        iqs_hull  = load_iqs(hull_dir)
        iqs_hough = load_iqs(hough_dir)
        iqs = max(iqs_hull, iqs_hough)  # report the better-quality run's IQS

        d_hull  = diameter_from_run(m_hull)
        d_hough = diameter_from_run(m_hough)
        e_hull  = rel_err(d_hull,  truth_diam)
        e_hough = rel_err(d_hough, truth_diam)

        hull_str  = f"{d_hull:.3f}"  if d_hull  else " N/A"
        hough_str = f"{d_hough:.3f}" if d_hough else " N/A"
        e_hull_str  = f"{e_hull*100:.1f}%"  if e_hull  is not None else " N/A"
        e_hough_str = f"{e_hough*100:.1f}%" if e_hough is not None else " N/A"

        if e_hull is not None and e_hough is not None:
            winner = "hull " if e_hull < e_hough else "hough"
            margin = abs(e_hull - e_hough) * 100
            winner_str = f"{winner}  ({margin:.1f}pp)"
        else:
            winner_str = "—"

        print(f"  {tier:<8} {iqs:>5.2f}  {hull_str:>10}  {e_hull_str:>9}  "
              f"{hough_str:>11}  {e_hough_str:>10}  {winner_str}")

    print("=" * W)
    print("""
Interpretation:
  Good tier  — consistent capture distances; hull intersection accurate → hull wins.
  Medium tier — shooting distance varied ~25% across views; hull intersection
                collapses under scale mismatch; Hough is per-view → Hough wins.
  Bad tier   — both methods degrade similarly; floor set by calibration error
               from inconsistent capture geometry.
""")


if __name__ == "__main__":
    main()
