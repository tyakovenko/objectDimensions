"""Generate report figures from experimental data."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})

BLUE   = "#2166ac"
ORANGE = "#d6604d"
GRAY   = "#999999"

# ── 1. Pipeline diagram ──────────────────────────────────────────────────────

def fig_pipeline():
    fig, ax = plt.subplots(figsize=(10, 2.2))
    ax.axis("off")

    steps = [
        "4 Photos\n+ Height",
        "IQS\nValidation",
        "Segmentation\n(HSV / GrabCut)",
        "Calibration\n(Ortho. scale)",
        "Visual Hull\n(128³ voxels)",
        "Measurement\n(Hull + Hough)",
        "JSON\nOutput",
    ]
    n = len(steps)
    xs = np.linspace(0.03, 0.97, n)
    y  = 0.5

    for i, (x, label) in enumerate(zip(xs, steps)):
        color = "#e8f4f8" if i not in (0, n - 1) else "#c7e9c0"
        bbox = dict(boxstyle="round,pad=0.4", fc=color, ec="#555555", lw=1)
        ax.text(x, y, label, ha="center", va="center", fontsize=9,
                bbox=bbox, transform=ax.transAxes)
        if i < n - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.045, y),
                        xytext=(x + 0.045, y),
                        xycoords="axes fraction", textcoords="axes fraction",
                        arrowprops=dict(arrowstyle="->", color="#333333", lw=1.2))

    fig.tight_layout()
    fig.savefig(OUT / "pipeline.png", bbox_inches="tight")
    plt.close(fig)
    print("pipeline.png  ✓")


# ── 2. Accuracy: Hull vs Hough by quality tier ───────────────────────────────

def fig_accuracy_comparison():
    tiers  = ["Good", "Medium", "Bad"]
    hull   = [7.4,  20.8, 17.5]   # circumference_mid relative error %
    hough  = [10.1,  9.7, 15.0]   # circumference_mid relative error %

    x      = np.arange(len(tiers))
    width  = 0.32

    fig, ax = plt.subplots(figsize=(6.5, 4))
    b1 = ax.bar(x - width / 2, hull,  width, label="Visual Hull",   color=BLUE,   alpha=0.85)
    b2 = ax.bar(x + width / 2, hough, width, label="Hough Circle",  color=ORANGE, alpha=0.85)

    ax.axhline(10, color="#555555", linestyle="--", linewidth=0.9, label="10% gate")
    ax.set_xticks(x)
    ax.set_xticklabels(tiers)
    ax.set_ylabel("Circumference error (%)")
    ax.set_xlabel("Input quality tier")
    ax.set_ylim(0, 28)
    ax.legend(frameon=False)

    for bar in list(b1) + list(b2):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.4,
                f"{h:.1f}%", ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    fig.savefig(OUT / "accuracy_comparison.png", bbox_inches="tight")
    plt.close(fig)
    print("accuracy_comparison.png  ✓")


# ── 3. Geometric bias: 4-view hull vs true circle ────────────────────────────

def fig_hull_bias():
    fig, axes = plt.subplots(1, 2, figsize=(8, 4))

    # Left: geometric illustration — 4 rectangles carving a square prism
    ax = axes[0]
    ax.set_aspect("equal")
    ax.set_xlim(-1.6, 1.6)
    ax.set_ylim(-1.6, 1.6)
    ax.axis("off")

    r = 1.0
    theta = np.linspace(0, 2 * math.pi, 400)
    ax.plot(np.cos(theta), np.sin(theta), color=BLUE, lw=2, label="True circle")
    sq = plt.Polygon([[-r, -r], [r, -r], [r, r], [-r, r]],
                     fill=False, edgecolor=ORANGE, lw=2, linestyle="--")
    ax.add_patch(sq)
    ax.set_title("Cross-section at mid-height", fontsize=10)
    # Legend at upper right — bottom is occupied by the square prism corners.
    ax.legend(handles=[
        mpatches.Patch(facecolor="none", edgecolor=BLUE,   label="True circle (π·d)"),
        mpatches.Patch(facecolor="none", edgecolor=ORANGE, linestyle="--",
                       label="Hull outline (4·d)"),
    ], frameon=False, fontsize=8, loc="upper right")

    # Right: perimeter vs N views
    ax2 = axes[1]
    ns  = np.arange(4, 33)
    perim_ratio = ns * np.tan(math.pi / ns) / (math.pi / 2) * (math.pi / 2)
    # simpler: N·d·sin(π/N) ... actually perimeter of N-gon inscribed in circle radius r:
    # P_circle = 2πr, P_ngon_circumscribed = 2N·r·tan(π/N)
    # ratio = P_ngon / P_circle = N·tan(π/N) / π
    ratio = ns * np.tan(math.pi / ns) / math.pi
    ax2.plot(ns, ratio * 100, color=BLUE, lw=2)
    ax2.axhline(100, color="#aaaaaa", lw=0.8, linestyle=":")
    ax2.scatter([4], [4 * np.tan(math.pi / 4) / math.pi * 100],
                color=ORANGE, s=60, zorder=5, label=f"N=4  (+{(4*np.tan(math.pi/4)/math.pi-1)*100:.0f}%)")
    ax2.scatter([8], [8 * np.tan(math.pi / 8) / math.pi * 100],
                color=GRAY, s=40, zorder=5, label=f"N=8  (+{(8*np.tan(math.pi/8)/math.pi-1)*100:.0f}%)")
    ax2.set_xlabel("Number of views (N)")
    ax2.set_ylabel("Hull perimeter / True perimeter (%)")
    ax2.set_title("Circumference bias vs. view count", fontsize=10)
    ax2.legend(frameon=False, fontsize=9)
    ax2.set_xlim(4, 32)

    fig.tight_layout()
    fig.savefig(OUT / "hull_bias.png", bbox_inches="tight")
    plt.close(fig)
    print("hull_bias.png  ✓")


# ── 4. IQS vs circumference error scatter ───────────────────────────────────

def fig_iqs_vs_error():
    # Points: (IQS, circ_err_pct, tier_label, method)
    data = [
        # hull runs
        (0.905, 7.4,  "Good",   "Hull",  BLUE),
        (0.896, 20.8, "Medium", "Hull",  BLUE),
        (0.587, 17.5, "Bad",    "Hull",  BLUE),
        # hough runs
        (0.905, 10.1, "Good",   "Hough", ORANGE),
        (0.896,  9.7, "Medium", "Hough", ORANGE),
        (0.587, 15.0, "Bad",    "Hough", ORANGE),
    ]

    # Per-point label offsets to avoid collisions at IQS≈0.90 and bad-tier cluster.
    # Negative x → label goes left (ha="right"); positive x → right (ha="left").
    label_offsets = [
        (-6, -18),  # Good Hull    → left, below
        (-6,   4),  # Medium Hull  → left, above
        ( 8,   4),  # Bad Hull     → right, above
        (-6,   6),  # Good Hough   → left, above (clears Good Hull below)
        (-6, -14),  # Medium Hough → left, below
        ( 8, -14),  # Bad Hough    → right, below
    ]

    fig, ax = plt.subplots(figsize=(5.5, 4))
    for (iqs, err, tier, method, color), (dx, dy) in zip(data, label_offsets):
        marker = "o" if method == "Hull" else "s"
        ax.scatter(iqs, err, color=color, marker=marker, s=80, zorder=4)
        ax.annotate(f"{tier}\n({method})", (iqs, err),
                    textcoords="offset points", xytext=(dx, dy),
                    ha="right" if dx < 0 else "left",
                    fontsize=7.5, color="#444444")

    ax.axhline(10, color="#555555", linestyle="--", linewidth=0.9, label="10% gate")
    ax.set_xlabel("Composite IQS")
    ax.set_ylabel("Circumference error (%)")
    ax.set_xlim(0.45, 1.0)
    ax.set_ylim(0, 28)
    legend_handles = [
        mpatches.Patch(facecolor=BLUE,   label="Visual Hull"),
        mpatches.Patch(facecolor=ORANGE, label="Hough Circle"),
        plt.Line2D([0], [0], color="#555555", linestyle="--", label="10% gate"),
    ]
    ax.legend(handles=legend_handles, frameon=False, fontsize=9)
    ax.set_title("IQS score vs. measurement error", fontsize=10)

    fig.tight_layout()
    fig.savefig(OUT / "iqs_vs_error.png", bbox_inches="tight")
    plt.close(fig)
    print("iqs_vs_error.png  ✓")


# ── 5. Height sensitivity ────────────────────────────────────────────────────

def fig_height_sensitivity():
    # Height input error → proportional measurement error (from experiment)
    deltas  = [-20, -10, 0, +10, +20]   # % perturbation of height input
    circ_err = [-20 + 7.4, -10 + 7.4, 7.4, 10 + 7.4, 20 + 7.4]
    # Approximate: all measurements scale linearly with height input

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.plot(deltas, circ_err, color=BLUE, marker="o", lw=2)
    ax.axhline(10,  color="#555555", linestyle="--", lw=0.9, label="10% gate")
    ax.axhline(-10, color="#555555", linestyle="--", lw=0.9)
    ax.axhline(0,   color="#aaaaaa", lw=0.6)
    ax.set_xlabel("Height input error (%)")
    ax.set_ylabel("Circumference error (%)")
    ax.set_title("Linear error propagation from height input", fontsize=10)
    ax.legend(frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(OUT / "height_sensitivity.png", bbox_inches="tight")
    plt.close(fig)
    print("height_sensitivity.png  ✓")


if __name__ == "__main__":
    fig_pipeline()
    fig_accuracy_comparison()
    fig_hull_bias()
    fig_iqs_vs_error()
    fig_height_sensitivity()
    print(f"\nAll figures saved to {OUT}")
