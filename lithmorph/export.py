from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .models import AnalysisContext, SectionResult


def _jsonable(value: Any):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def section_summary_rows(
    context: AnalysisContext,
) -> list[dict]:
    unit_to_mm = context.unit_to_mm
    rows = []
    for s in context.sections:
        row = {
            "plane": s.plane,
            "section_index": s.index,
            "section_count": s.count,
            "position_normalized": s.position_normalized,
            "position_percent": s.position_normalized * 100.0,
            "coordinate_native": s.coordinate_native,
            "coordinate_mm": s.coordinate_native * unit_to_mm,
            "component_count": len(s.components),
            "status": s.status,
            "contour_perimeter_native": s.perimeter_native,
            "contour_perimeter_mm": (
                None if s.perimeter_native is None
                else s.perimeter_native * unit_to_mm
            ),
            "open_contour_length_native": s.open_contour_length_native,
            "open_contour_length_mm": (
                None if s.open_contour_length_native is None
                else s.open_contour_length_native * unit_to_mm
            ),
            "enclosed_area_native2": s.enclosed_area_native2,
            "enclosed_area_mm2": (
                None if s.enclosed_area_native2 is None
                else s.enclosed_area_native2 * (unit_to_mm ** 2)
            ),
            "centroid_u_native": s.centroid_u_native,
            "centroid_v_native": s.centroid_v_native,
            "centroid_u_mm": (
                None if s.centroid_u_native is None
                else s.centroid_u_native * unit_to_mm
            ),
            "centroid_v_mm": (
                None if s.centroid_v_native is None
                else s.centroid_v_native * unit_to_mm
            ),
            "extent_u_native": s.extent_u_native,
            "extent_v_native": s.extent_v_native,
            "extent_u_mm": (
                None if s.extent_u_native is None
                else s.extent_u_native * unit_to_mm
            ),
            "extent_v_mm": (
                None if s.extent_v_native is None
                else s.extent_v_native * unit_to_mm
            ),
        }
        rows.append(row)
    return rows


def export_analysis(
    context: AnalysisContext,
    section_point_rows: list[dict],
    out_dir: str | Path,
    qa: dict,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    u = context.unit_to_mm

    planform_profile = []
    for row in context.planform.profile_rows:
        r = dict(row)
        for key in (
            "y_native", "x_left_native", "x_right_native",
            "width_native", "width_smooth_native", "center_x_native",
        ):
            value = r.get(key)
            r[key.replace("_native", "_mm")] = (
                None if value is None else float(value) * u
            )
        planform_profile.append(r)

    planform_outline = []
    for row in context.planform.outline_rows:
        r = dict(row)
        r["x_mm"] = float(r["x_native"]) * u
        r["y_mm"] = float(r["y_native"]) * u
        planform_outline.append(r)

    section_summary = section_summary_rows(context)

    points_out = []
    for row in section_point_rows:
        r = dict(row)
        r["coordinate_mm"] = float(r["coordinate_native"]) * u
        r["x_mm"] = float(r["x_native"]) * u
        r["y_mm"] = float(r["y_native"]) * u
        r["z_mm"] = float(r["z_native"]) * u
        points_out.append(r)

    profile_path = out_dir / "planform_profile.csv"
    outline_path = out_dir / "planform_outline.csv"
    section_path = out_dir / "section_summary.csv"
    point_path = out_dir / "section_points.csv"
    summary_path = out_dir / "summary.json"
    qa_path = out_dir / "qa.json"

    _write_csv(
        profile_path,
        [
            "position_normalized", "position_percent",
            "y_native", "y_mm",
            "x_left_native", "x_left_mm",
            "x_right_native", "x_right_mm",
            "width_native", "width_mm",
            "width_smooth_native", "width_smooth_mm",
            "center_x_native", "center_x_mm",
        ],
        planform_profile,
    )
    _write_csv(
        outline_path,
        ["ring_index", "point_index", "x_native", "x_mm", "y_native", "y_mm"],
        planform_outline,
    )
    _write_csv(
        section_path,
        [
            "plane", "section_index", "section_count",
            "position_normalized", "position_percent",
            "coordinate_native", "coordinate_mm",
            "component_count", "status",
            "contour_perimeter_native", "contour_perimeter_mm",
            "open_contour_length_native", "open_contour_length_mm",
            "enclosed_area_native2", "enclosed_area_mm2",
            "centroid_u_native", "centroid_u_mm",
            "centroid_v_native", "centroid_v_mm",
            "extent_u_native", "extent_u_mm",
            "extent_v_native", "extent_v_mm",
        ],
        section_summary,
    )
    _write_csv(
        point_path,
        [
            "plane", "section_index", "section_count",
            "position_normalized", "position_percent",
            "coordinate_native", "coordinate_mm",
            "component_index", "component_closed", "component_branched",
            "point_index", "point_count",
            "x_native", "x_mm", "y_native", "y_mm", "z_native", "z_mm",
        ],
        [
            {
                **r,
                "position_percent": float(r["position_normalized"]) * 100.0,
            }
            for r in points_out
        ],
    )

    bbox = context.bbox_native
    ext = bbox[1] - bbox[0]
    p = context.planform

    statuses: dict[str, int] = {}
    for s in context.sections:
        statuses[s.status] = statuses.get(s.status, 0) + 1

    summary = {
        "application": "LithMorph",
        "version": "0.1.0-dev2",
        "source": {
            "file": str(context.source_path),
            "sha256": context.source_sha256,
            "input_unit": context.input_unit,
            "unit_to_mm": context.unit_to_mm,
        },
        "coordinate_system": {
            "X": "width",
            "Y": "length",
            "Z": "thickness",
            "planform": "XY",
            "transverse_section": "XZ (y = constant)",
            "longitudinal_section": "YZ (x = constant)",
        },
        "bbox": {
            "native": bbox.tolist(),
            "extents_native": ext.tolist(),
            "extents_mm": (ext * u).tolist(),
        },
        "sampling": context.sampling_plan.to_dict(),
        "planform": {
            "area_mm2": p.area_native2 * (u ** 2),
            "perimeter_mm": p.perimeter_native * u,
            "centroid_x_mm": p.centroid_x_native * u,
            "centroid_y_mm": p.centroid_y_native * u,
            "max_width_mm": p.max_width_native * u,
            "raw_max_width_mm": p.raw_max_width_native * u,
            "max_width_position_normalized": p.max_width_position_normalized,
            "max_width_position_percent": p.max_width_position_normalized * 100.0,
            "max_width_y_mm": p.max_width_y_native * u,
            "max_width_x_left_mm": p.max_width_x_left_native * u,
            "max_width_x_right_mm": p.max_width_x_right_native * u,
            "max_width_position_reference": "Ymin=0%, Ymax=100%",
            "max_width_note": (
                "Position and ellipticity/sharpness are separate descriptors. "
                "Only numerical ties at the maximum are averaged; no 99% plateau "
                "criterion is used."
            ),
        },
        "sections": {
            "total_count": len(context.sections),
            "status_counts": statuses,
            "resampled_points_per_component": (
                int(section_point_rows[0]["point_count"])
                if section_point_rows else None
            ),
        },
        "optional_results": context.optional_results,
        "timings_seconds": context.timings,
    }

    summary_path.write_text(
        json.dumps(_jsonable(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    qa_path.write_text(
        json.dumps(_jsonable(qa), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "summary": summary_path,
        "qa": qa_path,
        "planform_profile": profile_path,
        "planform_outline": outline_path,
        "section_summary": section_path,
        "section_points": point_path,
    }
