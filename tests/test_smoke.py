"""Minimal smoke tests — grows as modules stabilize."""

import numpy as np

from src.segmentation.base import clean_mask
from src.validation import _frame_coverage_score, _scale_consistency_score


def test_clean_mask_preserves_shape():
    m = np.zeros((100, 100), dtype=bool)
    m[20:80, 20:80] = True
    cleaned = clean_mask(m)
    assert cleaned.shape == m.shape
    assert cleaned.dtype == bool


def test_frame_coverage_score_ideal():
    m = np.zeros((100, 100), dtype=bool)
    m[30:60, 30:60] = True  # 9% — should score < 1
    assert 0.0 <= _frame_coverage_score(m) <= 1.0
    m2 = np.zeros((100, 100), dtype=bool)
    m2[25:75, 25:75] = True  # 25% coverage — inside ideal band
    assert _frame_coverage_score(m2) == 1.0


def test_scale_consistency_perfect():
    assert _scale_consistency_score([100, 100, 100, 100]) == 1.0


def test_scale_consistency_degraded():
    # heights [100,80,60,40] → mean=70, std≈22.36, cv≈0.32, score≈0.68
    score = _scale_consistency_score([100, 80, 60, 40])
    assert 0.65 < score < 0.72


def test_solidity_shared_import():
    # Regression: _solidity was duplicated between hsv.py and validation.py.
    # Both should now resolve to the single implementation in segmentation/base.py.
    from src.segmentation.base import solidity
    from src.segmentation.hsv import _solidity as hsv_solidity
    from src.validation import _solidity as val_solidity
    assert hsv_solidity is solidity
    assert val_solidity is solidity
