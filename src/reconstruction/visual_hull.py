"""Visual hull reconstruction from 4 silhouettes.

MVP assumption: cameras are at fixed orthographic positions around the object —
front/right/back/left at 0/90/180/270 degrees. Object vertical axis = Z.

Later (extension): feature-matched camera pose, perspective projection.
"""

from __future__ import annotations

import numpy as np
import trimesh
from skimage import measure

from ..types import (
    CalibrationResult,
    PoseEstimate,
    Reconstruction,
    SegmentationResult,
)


# View → (image-x axis in world, image-y axis in world).
# Object vertical (image-y top→bottom) maps to world -Z (pixel y grows downward).
_VIEW_AXES = {
    "front": ("x", "-z"),   # camera looking at +Y. Image x = world x.
    "right": ("-y", "-z"),  # camera looking at -X. Image x = world -y.
    "back":  ("-x", "-z"),  # camera looking at -Y. Image x = world -x.
    "left":  ("y", "-z"),   # camera looking at +X. Image x = world y.
}


def _axis_vector(name: str) -> np.ndarray:
    sign = -1.0 if name.startswith("-") else 1.0
    axis = name[-1]
    base = {"x": np.array([1, 0, 0]), "y": np.array([0, 1, 0]), "z": np.array([0, 0, 1])}
    return sign * base[axis]


class VisualHullReconstructor:
    def __init__(self, resolution: int = 128, padding: float = 1.1):
        self.resolution = resolution
        self.padding = padding

    def reconstruct(
        self,
        segmentation: SegmentationResult,
        calibration: CalibrationResult,
        pose: PoseEstimate,
        pose_id: str,
    ) -> Reconstruction:
        # Use the first view's scale as the world-unit-per-pixel (inches per pixel).
        cam0 = calibration.cameras[0]
        inches_per_pixel = 1.0 / cam0.pixels_per_unit

        # Object bounds: height from reference, width assumed <= height * 1.5 to be safe.
        half_extent = calibration.reference_dimension * self.padding / 2.0
        grid_res = self.resolution
        coords = np.linspace(-half_extent, half_extent, grid_res)
        xs, ys, zs = np.meshgrid(coords, coords, coords, indexing="ij")
        voxels = np.stack([xs.ravel(), ys.ravel(), zs.ravel()], axis=1)

        occupied = np.ones(voxels.shape[0], dtype=bool)

        for seg in segmentation.segmented:
            view = seg.source.view
            if view not in _VIEW_AXES:
                raise ValueError(f"Unknown view: {view}")
            ax_u, ax_v = _VIEW_AXES[view]
            u_vec = _axis_vector(ax_u)
            v_vec = _axis_vector(ax_v)
            u_world = voxels @ u_vec
            v_world = voxels @ v_vec

            mask = seg.mask
            h_px, w_px = mask.shape
            # Object centered horizontally in the image; base at bottom of mask's bbox.
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            r_idx = np.where(rows)[0]
            c_idx = np.where(cols)[0]
            top_row = r_idx[0]
            bottom_row = r_idx[-1]
            left_col = c_idx[0]
            right_col = c_idx[-1]
            col_center = (left_col + right_col) / 2.0

            u_px = col_center + u_world / inches_per_pixel
            # Object is centered in the voxel grid at z=0, extending ±height/2.
            # v_vec = -z, so v_world = -z_world.
            # z=+height/2 (top) → v_world=-height/2 → top_row
            # z=-height/2 (base) → v_world=+height/2 → bottom_row
            height = calibration.reference_dimension
            center_row = (top_row + bottom_row) / 2.0
            v_px = center_row + (v_world / height) * (bottom_row - top_row)

            u_int = np.round(u_px).astype(int)
            v_int = np.round(v_px).astype(int)

            in_frame = (
                (u_int >= 0) & (u_int < w_px) & (v_int >= 0) & (v_int < h_px)
            )
            inside = np.zeros(voxels.shape[0], dtype=bool)
            inside[in_frame] = mask[v_int[in_frame], u_int[in_frame]]
            occupied &= inside

        volume = occupied.reshape((grid_res, grid_res, grid_res))
        if not volume.any():
            raise RuntimeError("Empty visual hull — check mask alignment and calibration")

        verts, faces, _, _ = measure.marching_cubes(volume.astype(float), level=0.5)
        # Rescale verts from voxel index space back to world coordinates.
        voxel_size = (2 * half_extent) / grid_res
        verts = verts * voxel_size - half_extent
        mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
        return Reconstruction(
            pose_id=pose_id,
            mesh=mesh,
            voxel_resolution=grid_res,
            method="visual_hull",
        )
