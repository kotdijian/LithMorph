import numpy as np
import trimesh

from lithmorph.planform import analyze_planform
from lithmorph.sections import SurfaceSlicer


def test_box_planform():
    mesh = trimesh.creation.box(extents=[40.0, 100.0, 10.0])
    slicer = SurfaceSlicer(mesh.vertices, mesh.faces)
    result = analyze_planform(slicer, profile_samples=401)
    assert np.isclose(result.area_native2, 4000.0, rtol=1e-4)
    assert np.isclose(result.perimeter_native, 280.0, rtol=1e-4)
    assert np.isclose(result.max_width_native, 40.0, rtol=5e-4)
    assert np.isclose(result.max_width_position_normalized, 0.5, atol=5e-3)


def test_box_center_sections():
    mesh = trimesh.creation.box(extents=[40.0, 100.0, 10.0])
    slicer = SurfaceSlicer(mesh.vertices, mesh.faces)

    xz, _ = slicer.section("XZ", 1, 1, 0.5)
    assert xz.status == "closed"
    assert np.isclose(xz.enclosed_area_native2, 400.0, rtol=1e-6)
    assert np.isclose(xz.perimeter_native, 100.0, rtol=1e-6)
    assert np.isclose(xz.centroid_u_native, 0.0, atol=1e-8)
    assert np.isclose(xz.centroid_v_native, 0.0, atol=1e-8)

    yz, _ = slicer.section("YZ", 1, 1, 0.5)
    assert yz.status == "closed"
    assert np.isclose(yz.enclosed_area_native2, 1000.0, rtol=1e-6)
    assert np.isclose(yz.perimeter_native, 220.0, rtol=1e-6)
    assert np.isclose(yz.centroid_u_native, 0.0, atol=1e-8)
    assert np.isclose(yz.centroid_v_native, 0.0, atol=1e-8)
