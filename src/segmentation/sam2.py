"""SAM 2 segmenter. Stub — implemented on Day 2–3 of Week 1 after GPU check (see docs/blockers.md B2)."""

from __future__ import annotations

from ..types import ImageSet, SegmentationResult


class SAM2Segmenter:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "SAM 2 segmenter not yet wired. "
            "Use GrabCutSegmenter until the GPU path is verified. "
            "See docs/blockers.md B2 and docs/research-and-data.md R1."
        )

    def segment(self, image_set: ImageSet) -> SegmentationResult:
        raise NotImplementedError
