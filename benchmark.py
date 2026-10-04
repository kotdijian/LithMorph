from __future__ import annotations

import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import trimesh

from lithmorph.planform import analyze_planform
from lithmorph.sampling import SamplingPreset, build_sampling_plan
from lithmorph.sections import SurfaceSlicer


def _integrate_profile(results, axis_extent: float, attr: str) -> float | None:
    pos = []
    val = []
    for r in results:
        value = getattr(r, attr)
        if value is None or not np.isfinite(value):
            continue
        pos.append(float(r.position_normalized))
        val.append(float(value))
    if len(pos) < 2:
        return None
    pos = np.asarray(pos, dtype=float)
    val = np.asarray(val, dtype=float)
    # Diagnostic quadrature for artifact-like tapered solids. Bbox tangency
    # endpoints are treated as zero area/width. Do not use as the primary
    # production volume calculation.
    pos = np.r_[0.0, pos, 1.0]
    val = np.r_[0.0, val, 0.0]
    return float(np.trapezoid(val, pos * float(axis_extent)))


def _status_counts(results) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="LithMorph benchmark")
    parser.add_argument("ply", type=Path)
    parser.add_argument("--out", type=Path, default=Path("lithmorph_benchmark"))
    parser.add_argument("--planform-samples", type=int, default=1001)
    parser.add_argument("--resample-points", type=int, default=256)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    t0 = time.perf_counter()
    mesh = trimesh.load(args.ply, force="mesh", process=False)
    load_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    slicer = SurfaceSlicer(mesh.vertices, mesh.faces)
    slicer_init_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    planform = analyze_planform(slicer, profile_samples=args.planform_samples)
    planform_s = time.perf_counter() - t0

    rows = []
    true_volume = abs(float(mesh.volume)) if mesh.is_watertight else None
    x_extent, y_extent, _z_extent = map(float, mesh.extents)

    for preset in SamplingPreset:
        plan = build_sampling_plan(mesh.extents, preset)

        t0 = time.perf_counter()
        xz, _ = slicer.series(
            "XZ", plan.xz_positions, resample_points=args.resample_points
        )
        xz_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        yz, _ = slicer.series(
            "YZ", plan.yz_positions, resample_points=args.resample_points
        )
        yz_s = time.perf_counter() - t0

        vol_xz = _integrate_profile(xz, y_extent, "enclosed_area_native2")
        vol_yz = _integrate_profile(yz, x_extent, "enclosed_area_native2")
        area_xz = _integrate_profile(xz, y_extent, "extent_u_native")
        area_yz = _integrate_profile(yz, x_extent, "extent_u_native")

        row = {
            "preset": preset.value,
            "shape_class": plan.shape_class,
            "base_count": plan.base_count,
            "xz_count": plan.xz_count,
            "yz_count": plan.yz_count,
            "xz_seconds": xz_s,
            "yz_seconds": yz_s,
            "section_total_seconds": xz_s + yz_s,
            "xz_ms_per_section": xz_s * 1000.0 / plan.xz_count,
            "yz_ms_per_section": yz_s * 1000.0 / plan.yz_count,
            "xz_status": json.dumps(_status_counts(xz), ensure_ascii=False),
            "yz_status": json.dumps(_status_counts(yz), ensure_ascii=False),
            "diagnostic_volume_xz": vol_xz,
            "diagnostic_volume_yz": vol_yz,
            "diagnostic_volume_xz_error_percent": (
                None if true_volume is None or vol_xz is None
                else 100.0 * (vol_xz / true_volume - 1.0)
            ),
            "diagnostic_volume_yz_error_percent": (
                None if true_volume is None or vol_yz is None
                else 100.0 * (vol_yz / true_volume - 1.0)
            ),
            "diagnostic_planform_area_xz": area_xz,
            "diagnostic_planform_area_yz": area_yz,
        }
        rows.append(row)
        print(
            f"{preset.value:7s}: XZ={plan.xz_count:3d} {xz_s:7.3f}s / "
            f"YZ={plan.yz_count:3d} {yz_s:7.3f}s"
        )

    csv_path = args.out / "benchmark.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "application": "LithMorph",
        "version": "0.1.0-dev2",
        "source": str(args.ply),
        "file_size_bytes": args.ply.stat().st_size,
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "bbox_extents_native": mesh.extents.tolist(),
        "bbox_y_x_ratio": float(mesh.extents[1] / mesh.extents[0]),
        "watertight": bool(mesh.is_watertight),
        "mesh_volume_native3": true_volume,
        "planform": {
            "profile_samples": args.planform_samples,
            "area_native2": planform.area_native2,
            "perimeter_native": planform.perimeter_native,
            "max_width_native": planform.max_width_native,
            "max_width_position_percent": (
                planform.max_width_position_normalized * 100.0
            ),
        },
        "fixed_timings_seconds": {
            "load": load_s,
            "slicer_init": slicer_init_s,
            "planform": planform_s,
        },
        "max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "total_benchmark_seconds": time.perf_counter() - started,
        "presets": rows,
    }
    (args.out / "benchmark.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
