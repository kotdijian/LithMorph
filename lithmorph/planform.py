from __future__ import annotations

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.signal import savgol_filter

from .models import PlanformResult
from .sections import SurfaceSlicer


def _odd_window(length: int, fraction: float) -> int:
    desired = max(5, int(round(length * float(fraction))))
    if desired % 2 == 0:
        desired += 1
    max_odd = length if length % 2 == 1 else length - 1
    desired = min(desired, max_odd)
    return desired if desired >= 5 else 0


def analyze_planform(
    slicer: SurfaceSlicer,
    profile_samples: int = 1001,
    smoothing_fraction: float = 0.01,
) -> PlanformResult:
    """Analyze the XY planform as a dense surface-derived scanline envelope.

    This implementation deliberately avoids projected-triangle polygon union.
    On multi-million-face PLY models that route can require heavy spatial-index
    dependencies and large transient memory. Instead, LithMorph reuses the same
    triangle/plane intersection engine as serial section analysis.

    For each Y scanline, the XY silhouette's left/right X bounds are obtained
    from an X-Z surface intersection. Basic planform metrics are then integrated
    over the dense profile. The method assumes the archaeological artifact's
    external planform can be represented by one outer left/right envelope; any
    internal holes are intentionally not treated as separate basic-planform area.
    """
    profile_samples = int(profile_samples)
    if profile_samples < 21:
        raise ValueError("profile_samples must be >= 21")
    if profile_samples % 2 == 0:
        profile_samples += 1

    positions = np.linspace(0.0, 1.0, profile_samples)
    ys = np.empty(profile_samples, dtype=float)
    left = np.empty(profile_samples, dtype=float)
    right = np.empty(profile_samples, dtype=float)

    for i, pos in enumerate(positions):
        y, x0, x1 = slicer.planform_scanline_bounds(float(pos))
        ys[i] = y
        left[i] = x0
        right[i] = x1

    valid = np.isfinite(left) & np.isfinite(right)
    if valid.sum() < 5:
        raise RuntimeError("Planform scanline profile contains too few valid samples.")

    # Fill only numerical gaps in the profile; do not alter valid geometry.
    idx = np.arange(profile_samples)
    if not valid.all():
        left = np.interp(idx, idx[valid], left[valid])
        right = np.interp(idx, idx[valid], right[valid])

    width = np.maximum(right - left, 0.0)
    center = (left + right) * 0.5

    window = _odd_window(profile_samples, smoothing_fraction)
    if window:
        smooth_width = savgol_filter(
            width,
            window_length=window,
            polyorder=min(3, window - 2),
            mode="interp",
        )
        smooth_width = np.maximum(smooth_width, 0.0)
    else:
        smooth_width = width.copy()

    raw_i = int(np.argmax(width))
    raw_max = float(width[raw_i])

    # Continuous maximum from the robust width profile. The selected section
    # preset does not affect this calculation.
    interp = PchipInterpolator(positions, smooth_width, extrapolate=False)
    dense_positions = np.linspace(0.0, 1.0, 10001)
    dense_width = np.asarray(interp(dense_positions), dtype=float)
    max_w = float(np.nanmax(dense_width))
    atol = max(abs(max_w) * 1e-8, 1e-12)
    tied = np.flatnonzero(
        np.isclose(dense_width, max_w, rtol=1e-8, atol=atol)
    )
    if len(tied):
        max_pos = float(np.mean(dense_positions[tied]))
    else:
        max_pos = float(dense_positions[int(np.nanargmax(dense_width))])

    max_y = float(np.interp(max_pos, positions, ys))
    x_left = float(np.interp(max_pos, positions, left))
    x_right = float(np.interp(max_pos, positions, right))

    # Planform area and centroid from horizontal-strip integration.
    area = float(np.trapezoid(width, ys))
    if area <= 0:
        raise RuntimeError("Planform area is not positive.")
    centroid_x = float(np.trapezoid(center * width, ys) / area)
    centroid_y = float(np.trapezoid(ys * width, ys) / area)

    # Exterior perimeter approximation from left and right outer envelopes,
    # including possible flat terminal segments at Ymin/Ymax.
    left_curve = np.column_stack([left, ys])
    right_curve = np.column_stack([right, ys])
    perimeter = float(
        np.linalg.norm(np.diff(left_curve, axis=0), axis=1).sum()
        + np.linalg.norm(np.diff(right_curve, axis=0), axis=1).sum()
        + abs(float(right[0] - left[0]))
        + abs(float(right[-1] - left[-1]))
    )

    profile_rows: list[dict[str, float | None]] = []
    for i in range(profile_samples):
        profile_rows.append({
            "position_normalized": float(positions[i]),
            "position_percent": float(positions[i] * 100.0),
            "y_native": float(ys[i]),
            "x_left_native": float(left[i]),
            "x_right_native": float(right[i]),
            "width_native": float(width[i]),
            "width_smooth_native": float(smooth_width[i]),
            "center_x_native": float(center[i]),
        })

    # One closed outer ring: left side Ymin->Ymax, then right side Ymax->Ymin.
    outline = np.vstack([
        left_curve,
        right_curve[::-1],
        left_curve[:1],
    ])
    outline_rows = [
        {
            "ring_index": 1,
            "point_index": i,
            "x_native": float(p[0]),
            "y_native": float(p[1]),
        }
        for i, p in enumerate(outline)
    ]

    return PlanformResult(
        area_native2=area,
        perimeter_native=perimeter,
        centroid_x_native=centroid_x,
        centroid_y_native=centroid_y,
        max_width_native=max_w,
        max_width_position_normalized=max_pos,
        max_width_y_native=max_y,
        max_width_x_left_native=x_left,
        max_width_x_right_native=x_right,
        raw_max_width_native=raw_max,
        profile_rows=profile_rows,
        outline_rows=outline_rows,
    )
