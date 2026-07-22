"""Phase 1 pose estimator — no-op. Phase 2 swaps in MediaPipe via same protocol."""

from __future__ import annotations

from ..types import PoseEstimate, SegmentationResult


class NullPoseEstimator:
    def estimate(self, segmentation: SegmentationResult) -> PoseEstimate:
        return PoseEstimate(keypoints={}, confidence={})
