"""Measurement extraction from a reconstructed mesh.

MVP set: bbox height + circumference at 3 heights + width/depth at midpoint.
"""

from __future__ import annotations

import numpy as np

from ..types import MeasurementProfile, MeasurementResult, Reconstruction

DEFAULT_HEIGHT_FRACTIONS = [
    ("circumference_bottom", 0.1),
    ("circumference_mid", 0.5),
    ("circumference_top", 0.9),
]


def _bbox_height(mesh) -> float:
    bounds = mesh.bounds  # shape (2, 3): min / max
    return float(bounds[1, 2] - bounds[0, 2])


def _cross_section(mesh, z: float):
    section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if section is None:
        return None
    return section


def _perimeter_2d(section) -> float:
    planar, _ = section.to_planar()
    if len(planar.entities) == 0:
        return 0.0
    # Pick the largest closed polygon by area.
    polys = planar.polygons_full
    if len(polys) == 0:
        # Fall back: sum all entity lengths
        return float(planar.length)
    largest = max(polys, key=lambda p: p.area)
    return float(largest.length)


def _bbox_2d(section, axis: int) -> float:
    planar, _ = section.to_planar()
    if len(planar.polygons_full) == 0:
        return 0.0
    largest = max(planar.polygons_full, key=lambda p: p.area)
    minx, miny, maxx, maxy = largest.bounds
    return float((maxx - minx) if axis == 0 else (maxy - miny))


class CrossSectionMeasurer:
    def __init__(self, height_fractions=None):
        self.height_fractions = height_fractions or DEFAULT_HEIGHT_FRACTIONS

    def measure(self, reconstructions: list[Reconstruction], segmentation=None, calibration=None) -> MeasurementProfile:
        results: list[MeasurementResult] = []
        for rec in reconstructions:
            mesh = rec.mesh
            z_min, z_max = mesh.bounds[0, 2], mesh.bounds[1, 2]
            height = float(z_max - z_min)
            results.append(MeasurementResult("height", height, "in", rec.pose_id))

            for name, frac in self.height_fractions:
                z = z_min + frac * (z_max - z_min)
                section = _cross_section(mesh, z)
                value = _perimeter_2d(section) if section is not None else 0.0
                results.append(MeasurementResult(name, value, "in", rec.pose_id))

            # Width/depth at midpoint
            z_mid = z_min + 0.5 * (z_max - z_min)
            section = _cross_section(mesh, z_mid)
            if section is not None:
                results.append(
                    MeasurementResult("width_mid", _bbox_2d(section, 0), "in", rec.pose_id)
                )
                results.append(
                    MeasurementResult("depth_mid", _bbox_2d(section, 1), "in", rec.pose_id)
                )
        return MeasurementProfile(results=results, iqs=0.0)
