from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SamplingPlan:
    preset: str
    base_count: int
    reduced_count: int
    shape_class: str
    bbox_ratio_y_over_x: float
    xz_count: int
    yz_count: int
    xz_positions: np.ndarray
    yz_positions: np.ndarray

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "base_count": self.base_count,
            "reduced_count": self.reduced_count,
            "shape_class": self.shape_class,
            "bbox_ratio_y_over_x": float(self.bbox_ratio_y_over_x),
            "xz_count": int(self.xz_count),
            "yz_count": int(self.yz_count),
            "xz_positions_normalized": self.xz_positions.tolist(),
            "yz_positions_normalized": self.yz_positions.tolist(),
        }


@dataclass
class ContourComponent:
    points: np.ndarray
    closed: bool
    branched: bool = False


@dataclass
class SectionResult:
    plane: str
    index: int
    count: int
    position_normalized: float
    coordinate_native: float
    components: list[ContourComponent] = field(default_factory=list)
    status: str = "no_intersection"
    perimeter_native: float | None = None
    open_contour_length_native: float | None = None
    enclosed_area_native2: float | None = None
    centroid_u_native: float | None = None
    centroid_v_native: float | None = None
    extent_u_native: float | None = None
    extent_v_native: float | None = None


@dataclass
class PlanformResult:
    area_native2: float
    perimeter_native: float
    centroid_x_native: float
    centroid_y_native: float
    max_width_native: float
    max_width_position_normalized: float
    max_width_y_native: float
    max_width_x_left_native: float
    max_width_x_right_native: float
    raw_max_width_native: float
    profile_rows: list[dict[str, float | None]]
    outline_rows: list[dict[str, float | int]]


@dataclass
class AnalysisContext:
    source_path: Path
    source_sha256: str
    mesh: Any
    input_unit: str
    unit_to_mm: float
    bbox_native: np.ndarray
    sampling_plan: SamplingPlan
    planform: PlanformResult
    sections: list[SectionResult]
    timings: dict[str, float] = field(default_factory=dict)
    optional_results: dict[str, Any] = field(default_factory=dict)
