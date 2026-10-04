from pathlib import Path
import tempfile
import json

import numpy as np
import trimesh

from lithmorph.analysis import analyze_mesh
from lithmorph.sampling import build_sampling_plan


def main():
    plan = build_sampling_plan(np.array([40.0, 100.0, 10.0]), "Sparse")
    assert plan.xz_count == 9
    assert plan.yz_count == 5

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        mesh = trimesh.creation.box(extents=[40.0, 100.0, 10.0])
        ply = td / "box_rev.ply"
        mesh.export(ply)

        transform = {
            "source": {
                "input_unit": "mm",
                "unit_to_mm": 1.0
            }
        }
        (td / "transform.json").write_text(
            json.dumps(transform),
            encoding="utf-8",
        )

        out = td / "analysis"
        context = analyze_mesh(
            ply,
            out_dir=out,
            preset="Sparse",
            planform_profile_samples=201,
        )

        assert (out / "summary.json").exists()
        assert (out / "section_summary.csv").exists()
        assert (out / "section_points.csv").exists()
        assert np.isclose(
            context.planform.area_native2,
            4000.0,
            rtol=1e-4,
        )

    print("SELF TEST PASSED")


if __name__ == "__main__":
    main()
