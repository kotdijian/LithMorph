from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh


UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
}


def sha256_file(path: str | Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_normalized_ply(path: str | Path) -> trimesh.Trimesh:
    path = Path(path)
    if path.suffix.lower() != ".ply":
        raise ValueError("LithMorph v0.1.0-dev1 accepts normalized PLY input only.")

    loaded = trimesh.load(path, force=None, process=False)

    if isinstance(loaded, trimesh.Scene):
        geometries = [
            g for g in loaded.geometry.values()
            if isinstance(g, trimesh.Trimesh)
        ]
        if not geometries:
            raise ValueError("No mesh geometry found in PLY.")
        mesh = trimesh.util.concatenate(geometries)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise TypeError(f"Unsupported Trimesh load result: {type(loaded)!r}")

    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise ValueError("Mesh contains no vertices or faces.")

    if mesh.faces.shape[1] != 3:
        mesh = mesh.triangulate()

    return mesh


from .asset_metadata import resolve_units


def mesh_qa(mesh: trimesh.Trimesh) -> dict:
    bounds = np.asarray(mesh.bounds, dtype=float)
    ext = bounds[1] - bounds[0]
    result = {
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "bbox_native": bounds.tolist(),
        "bbox_extents_native": ext.tolist(),
        "is_watertight": bool(mesh.is_watertight),
        "is_winding_consistent": bool(mesh.is_winding_consistent),
        "euler_number": int(mesh.euler_number),
    }
    try:
        result["body_count"] = int(mesh.body_count)
    except Exception:
        result["body_count"] = None
    return result
