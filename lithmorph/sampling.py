from __future__ import annotations

from enum import Enum

import numpy as np

from .models import SamplingPlan


class SamplingPreset(str, Enum):
    SPARSE = "Sparse"
    LOW = "Low"
    DEFAULT = "Default"
    HIGH = "High"


BASE_COUNTS = {
    SamplingPreset.SPARSE: 9,
    SamplingPreset.LOW: 25,
    SamplingPreset.DEFAULT: 49,
    SamplingPreset.HIGH: 99,
}


def _nearest_half_odd(n: int) -> int:
    """Return the odd integer nearest to n/2.

    Required mapping for LithMorph:
      9 -> 5
      25 -> 13
      49 -> 25
      99 -> 49
    """
    value = (int(n) + 1) // 2
    if value % 2 == 0:
        value -= 1
    return max(1, value)


def normalized_positions(count: int) -> np.ndarray:
    """Equally spaced internal positions k/(N+1), k=1..N.

    For odd N this always contains the 50% section and excludes 0/100%.
    """
    count = int(count)
    if count < 1:
        raise ValueError("section count must be >= 1")
    return np.arange(1, count + 1, dtype=float) / float(count + 1)


def build_sampling_plan(
    bbox_extents_xyz: np.ndarray,
    preset: SamplingPreset | str = SamplingPreset.DEFAULT,
) -> SamplingPlan:
    """Choose XZ/YZ section counts from normalized bbox proportions.

    Coordinate semantics:
      X = width
      Y = length
      Z = thickness

    Shape classes:
      elongated_y : Y > 2X
      intermediate: X/2 <= Y <= 2X
      broad_x     : Y < X/2

    Allocation:
      elongated_y : XZ=N,   YZ≈N/2
      intermediate: XZ=N,   YZ=N
      broad_x     : XZ≈N/2, YZ=N
    """
    if isinstance(preset, str):
        preset = SamplingPreset(preset)

    ext = np.asarray(bbox_extents_xyz, dtype=float)
    if ext.shape != (3,) or not np.isfinite(ext).all():
        raise ValueError("bbox_extents_xyz must be a finite (3,) array")

    x = float(ext[0])
    y = float(ext[1])
    if x <= 0 or y <= 0:
        raise ValueError("bbox X and Y extents must be positive")

    ratio = y / x
    base = BASE_COUNTS[preset]
    reduced = _nearest_half_odd(base)

    if ratio > 2.0:
        shape_class = "elongated_y"
        xz_count = base
        yz_count = reduced
    elif ratio < 0.5:
        shape_class = "broad_x"
        xz_count = reduced
        yz_count = base
    else:
        shape_class = "intermediate"
        xz_count = base
        yz_count = base

    return SamplingPlan(
        preset=preset.value,
        base_count=base,
        reduced_count=reduced,
        shape_class=shape_class,
        bbox_ratio_y_over_x=ratio,
        xz_count=xz_count,
        yz_count=yz_count,
        xz_positions=normalized_positions(xz_count),
        yz_positions=normalized_positions(yz_count),
    )
