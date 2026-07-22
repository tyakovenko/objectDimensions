"""CLI entry point.

Usage:
    python run.py data/soup_can/good --height 4.25
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Object dimension pipeline — Phase 1")
    parser.add_argument("image_dir", type=Path, help="Directory with front/right/back/left photos")
    parser.add_argument("--height", type=float, required=True, help="True object height (inches)")
    parser.add_argument("--resolution", type=int, default=128, help="Voxel grid resolution (default 128)")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Output root directory")
    parser.add_argument(
        "--segmenter",
        choices=["hsv", "grabcut"],
        default="hsv",
        help="Segmenter backend (default hsv — fast color threshold for distinctly-colored objects)",
    )
    parser.add_argument(
        "--measurer",
        choices=["hull", "hough"],
        default="hull",
        help="Measurement backend: hull=visual hull cross-section (default), hough=per-view Hough circles (cylinder only)",
    )
    args = parser.parse_args()

    bundle = run_pipeline(
        image_dir=args.image_dir,
        reference_dimension=args.height,
        output_root=args.output,
        voxel_resolution=args.resolution,
        segmenter_name=args.segmenter,
        measurer_name=args.measurer,
    )

    print(f"\nValidation: {bundle.validation.quality_label} (IQS={bundle.validation.composite_iqs:.2f})")
    for w in bundle.validation.warnings:
        print(f"  WARN: {w}")
    print(f"\nMeasurements (inches):")
    for r in bundle.measurements.results:
        print(f"  {r.name:25s} {r.value:6.3f} {r.unit}")
    print(f"\nOutputs saved to: {bundle.output_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Last-resort handler — surface a one-line message instead of a raw traceback.
        # Re-raise under DEBUG=1 for development.
        import os
        if os.environ.get("DEBUG"):
            raise
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
