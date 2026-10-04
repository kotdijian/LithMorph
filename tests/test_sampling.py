import numpy as np

from lithmorph.sampling import build_sampling_plan


def test_default_elongated():
    p = build_sampling_plan(np.array([40.0, 100.0, 10.0]), "Default")
    assert p.shape_class == "elongated_y"
    assert p.xz_count == 49
    assert p.yz_count == 25
    assert np.isclose(p.xz_positions[24], 0.5)
    assert np.isclose(p.yz_positions[12], 0.5)


def test_default_intermediate():
    p = build_sampling_plan(np.array([60.0, 100.0, 10.0]), "Default")
    assert p.shape_class == "intermediate"
    assert p.xz_count == 49
    assert p.yz_count == 49


def test_default_broad():
    p = build_sampling_plan(np.array([100.0, 40.0, 10.0]), "Default")
    assert p.shape_class == "broad_x"
    assert p.xz_count == 25
    assert p.yz_count == 49


def test_preset_reduced_counts():
    expected = {
        "Sparse": (9, 5),
        "Low": (25, 13),
        "Default": (49, 25),
        "High": (99, 49),
    }
    for name, (base, reduced) in expected.items():
        p = build_sampling_plan(np.array([10.0, 30.0, 2.0]), name)
        assert p.base_count == base
        assert p.reduced_count == reduced
