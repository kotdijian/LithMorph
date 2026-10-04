from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from .export import export_analysis
from .io import load_normalized_ply, mesh_qa, resolve_units, sha256_file
from .models import AnalysisContext
from .optional import run_selected
from .planform import analyze_planform
from .sampling import SamplingPreset, build_sampling_plan
from .sections import SurfaceSlicer


def analyze_mesh(
    ply_path: str | Path,
    out_dir: str | Path | None = None,
    preset: SamplingPreset | str = SamplingPreset.DEFAULT,
    input_unit: str | None = "auto",
    resample_points: int = 256,
    optional: list[str] | tuple[str, ...] = (),
    planform_profile_samples: int = 1001,
) -> AnalysisContext:
    """Run LithMorph basic analysis on a normalized PLY."""
    ply_path = Path(ply_path)
    if out_dir is None:
        out_dir = ply_path.parent / "lithic_surface_analysis" / ply_path.stem
    out_dir = Path(out_dir)

    t_all = time.perf_counter()

    t0 = time.perf_counter()
    mesh = load_normalized_ply(ply_path)
    unit, unit_to_mm, _transform_metadata = resolve_units(
        ply_path,
        input_unit=input_unit,
    )
    source_sha = sha256_file(ply_path)
    qa = mesh_qa(mesh)
    load_sec = time.perf_counter() - t0

    bbox = np.asarray(mesh.bounds, dtype=float)
    ext = bbox[1] - bbox[0]
    sampling = build_sampling_plan(ext, preset=preset)

    t0 = time.perf_counter()
    slicer = SurfaceSlicer(mesh.vertices, mesh.faces)
    slicer_init_sec = time.perf_counter() - t0

    t0 = time.perf_counter()
    planform = analyze_planform(
        slicer,
        profile_samples=planform_profile_samples,
    )
    planform_sec = time.perf_counter() - t0

    t0 = time.perf_counter()
    xz, xz_points = slicer.series(
        "XZ",
        sampling.xz_positions,
        resample_points=resample_points,
    )
    xz_sec = time.perf_counter() - t0

    t0 = time.perf_counter()
    yz, yz_points = slicer.series(
        "YZ",
        sampling.yz_positions,
        resample_points=resample_points,
    )
    yz_sec = time.perf_counter() - t0

    context = AnalysisContext(
        source_path=ply_path,
        source_sha256=source_sha,
        mesh=mesh,
        input_unit=unit,
        unit_to_mm=unit_to_mm,
        bbox_native=bbox,
        sampling_plan=sampling,
        planform=planform,
        sections=[*xz, *yz],
        timings={
            "load_and_qa": load_sec,
            "slicer_init": slicer_init_sec,
            "planform": planform_sec,
            "xz_sections": xz_sec,
            "yz_sections": yz_sec,
        },
    )

    if optional:
        context.optional_results = run_selected(context, optional)

    t0 = time.perf_counter()
    export_analysis(
        context,
        section_point_rows=[*xz_points, *yz_points],
        out_dir=out_dir,
        qa=qa,
    )
    context.timings["export"] = time.perf_counter() - t0
    context.timings["total"] = time.perf_counter() - t_all

    # Re-export summary once so final timing values are included.
    export_analysis(
        context,
        section_point_rows=[*xz_points, *yz_points],
        out_dir=out_dir,
        qa=qa,
    )
    return context
