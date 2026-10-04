from __future__ import annotations

import numpy as np

from .contours import assemble_contours, polyline_length, resample_polyline
from .models import ContourComponent, SectionResult


class SurfaceSlicer:
    """Memory-conscious repeated plane slicer for normalized triangle meshes.

    It precomputes per-face X/Y coordinate ranges once. Each section then
    evaluates only faces whose coordinate range can intersect the plane.
    """

    def __init__(self, vertices: np.ndarray, faces: np.ndarray):
        self.vertices = np.asarray(vertices, dtype=float)
        self.faces = np.asarray(faces, dtype=np.int64)
        if self.faces.ndim != 2 or self.faces.shape[1] != 3:
            raise ValueError("faces must be triangular with shape (N,3)")

        self.bounds = np.array([
            self.vertices.min(axis=0),
            self.vertices.max(axis=0),
        ])
        self.extents = self.bounds[1] - self.bounds[0]
        self.diagonal = float(np.linalg.norm(self.extents))

        # Precompute only X/Y face intervals; Z-normal slicing is not currently
        # part of LithMorph basic analysis.
        self.face_ranges: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        for axis in (0, 1):
            coord = self.vertices[:, axis]
            tri_coord = coord[self.faces]
            self.face_ranges[axis] = (
                tri_coord.min(axis=1),
                tri_coord.max(axis=1),
            )

        self.eps = max(self.diagonal * 1e-10, 1e-12)
        self.stitch_tolerance = max(self.diagonal * 1e-8, 1e-10)

    def _candidate_face_indices(self, axis: int, coordinate: float) -> np.ndarray:
        fmin, fmax = self.face_ranges[axis]
        eps = self.eps
        return np.flatnonzero(
            (fmin <= coordinate + eps) &
            (fmax >= coordinate - eps)
        )

    def _segments_for_plane(
        self,
        axis: int,
        coordinate: float,
        chunk_size: int = 50_000,
    ) -> np.ndarray:
        ids = self._candidate_face_indices(axis, coordinate)
        if len(ids) == 0:
            return np.empty((0, 2, 3), dtype=float)

        all_segments: list[np.ndarray] = []
        edge_pairs = ((0, 1), (1, 2), (2, 0))
        eps = self.eps

        for start in range(0, len(ids), chunk_size):
            sub = ids[start:start + chunk_size]
            tri = self.vertices[self.faces[sub]]
            d = tri[:, :, axis] - float(coordinate)
            m = len(tri)

            pts = np.full((m, 3, 3), np.nan, dtype=float)
            valid = np.zeros((m, 3), dtype=bool)

            for ej, (ia, ib) in enumerate(edge_pairs):
                a = tri[:, ia, :]
                b = tri[:, ib, :]
                da = d[:, ia]
                db = d[:, ib]

                a_on = np.abs(da) <= eps
                b_on = np.abs(db) <= eps
                both_on = a_on & b_on

                crosses = (
                    ((da < -eps) & (db > eps)) |
                    ((da > eps) & (db < -eps)) |
                    (a_on ^ b_on)
                )
                crosses &= ~both_on

                denom = da - db
                safe = crosses & (np.abs(denom) > eps)
                t = np.zeros(m, dtype=float)
                t[safe] = da[safe] / denom[safe]
                # Exact endpoint hits.
                t[a_on & ~b_on] = 0.0
                t[b_on & ~a_on] = 1.0

                good = crosses
                pts[good, ej, :] = (
                    a[good] + t[good, None] * (b[good] - a[good])
                )
                valid[good, ej] = True

            counts = valid.sum(axis=1)

            # Fast path: exactly two edge intersections.
            rows2 = np.flatnonzero(counts == 2)
            if len(rows2):
                order = np.argsort(~valid[rows2], axis=1)
                p0 = pts[rows2, order[:, 0], :]
                p1 = pts[rows2, order[:, 1], :]
                length = np.linalg.norm(p1 - p0, axis=1)
                keep = length > eps
                if np.any(keep):
                    all_segments.append(
                        np.stack([p0[keep], p1[keep]], axis=1)
                    )

            # Rare vertex/coplanar-edge cases.
            rows_other = np.flatnonzero(counts >= 3)
            for ri in rows_other:
                candidates = pts[ri, valid[ri]]
                unique: list[np.ndarray] = []
                for p in candidates:
                    if not any(np.linalg.norm(p - q) <= eps for q in unique):
                        unique.append(p)
                if len(unique) < 2:
                    continue
                if len(unique) == 2:
                    p0, p1 = unique
                else:
                    arr = np.asarray(unique)
                    delta = arr[:, None, :] - arr[None, :, :]
                    dist2 = np.sum(delta * delta, axis=2)
                    ii, jj = np.unravel_index(np.argmax(dist2), dist2.shape)
                    p0, p1 = arr[ii], arr[jj]
                if np.linalg.norm(p1 - p0) > eps:
                    all_segments.append(
                        np.asarray([[p0, p1]], dtype=float)
                    )

        if not all_segments:
            return np.empty((0, 2, 3), dtype=float)
        return np.concatenate(all_segments, axis=0)

    def planform_scanline_bounds(
        self,
        position_normalized: float,
    ) -> tuple[float, float, float]:
        """Return (y, x_left, x_right) for the XY projected outer envelope.

        This is a lightweight planform primitive. It intersects the surface
        with an X-Z plane at the requested normalized Y position and uses the
        leftmost/rightmost X coordinates of all resulting segments. It does
        not assemble contour topology, so it is much cheaper than a full
        SectionResult and is suitable for dense planform profiling.
        """
        p = float(position_normalized)
        if not 0.0 <= p <= 1.0:
            raise ValueError("position_normalized must be in [0, 1]")

        y = float(self.bounds[0, 1] + p * self.extents[1])

        # At bbox tangency planes, direct triangle-plane intersection is
        # numerically ambiguous. Use vertices on the extreme plane instead.
        if p <= 0.0 or p >= 1.0:
            target = self.bounds[0, 1] if p <= 0.0 else self.bounds[1, 1]
            mask = np.abs(self.vertices[:, 1] - target) <= self.eps
            x = self.vertices[mask, 0]
        else:
            segments = self._segments_for_plane(1, y)
            if len(segments) == 0:
                return y, float("nan"), float("nan")
            x = segments[:, :, 0].reshape(-1)

        if len(x) == 0:
            return y, float("nan"), float("nan")
        return y, float(np.min(x)), float(np.max(x))

    @staticmethod
    def _uv(points: np.ndarray, plane: str) -> np.ndarray:
        points = np.asarray(points, dtype=float)
        if plane == "XZ":
            return points[:, [0, 2]]
        if plane == "YZ":
            return points[:, [1, 2]]
        raise ValueError(plane)

    def section(
        self,
        plane: str,
        index: int,
        count: int,
        position_normalized: float,
        resample_points: int = 256,
    ) -> tuple[SectionResult, list[dict]]:
        plane = plane.upper()
        if plane == "XZ":
            normal_axis = 1
            coordinate = (
                self.bounds[0, 1]
                + position_normalized * self.extents[1]
            )
        elif plane == "YZ":
            normal_axis = 0
            coordinate = (
                self.bounds[0, 0]
                + position_normalized * self.extents[0]
            )
        else:
            raise ValueError("plane must be XZ or YZ")

        segments = self._segments_for_plane(normal_axis, coordinate)
        components = assemble_contours(
            segments,
            tolerance=self.stitch_tolerance,
        )

        result = SectionResult(
            plane=plane,
            index=index,
            count=count,
            position_normalized=float(position_normalized),
            coordinate_native=float(coordinate),
            components=components,
        )

        point_rows: list[dict] = []
        if not components:
            return result, point_rows

        all_points = np.vstack([c.points for c in components if len(c.points)])
        uv_all = self._uv(all_points, plane)
        result.extent_u_native = float(np.ptp(uv_all[:, 0]))
        result.extent_v_native = float(np.ptp(uv_all[:, 1]))

        closed = [c for c in components if c.closed and not c.branched]
        open_ = [c for c in components if not c.closed or c.branched]

        if any(c.branched for c in components):
            result.status = "branched"
        elif len(closed) == 1 and not open_:
            result.status = "closed"
        elif len(closed) > 1 and not open_:
            result.status = "multiple_closed_components"
        elif closed and open_:
            result.status = "mixed_closed_open"
        elif len(open_) == 1:
            result.status = "open"
        else:
            result.status = "multiple_open_components"

        if closed:
            areas = []
            centroids = []
            perimeters = []
            for comp in closed:
                uv = self._uv(comp.points, plane)
                if np.linalg.norm(uv[0] - uv[-1]) > 0:
                    uv = np.vstack([uv, uv[0]])

                perimeters.append(
                    float(np.linalg.norm(np.diff(uv, axis=0), axis=1).sum())
                )

                x = uv[:-1, 0]
                y = uv[:-1, 1]
                xn = uv[1:, 0]
                yn = uv[1:, 1]
                cross = x * yn - xn * y
                signed_area = 0.5 * float(cross.sum())
                area = abs(signed_area)
                if area <= self.eps * self.eps:
                    continue

                cx = float(((x + xn) * cross).sum() / (6.0 * signed_area))
                cy = float(((y + yn) * cross).sum() / (6.0 * signed_area))
                areas.append(area)
                centroids.append((cx, cy))

            result.perimeter_native = (
                float(sum(perimeters)) if perimeters else None
            )
            if areas:
                total_area = float(sum(areas))
                result.enclosed_area_native2 = total_area
                result.centroid_u_native = float(
                    sum(a * c[0] for a, c in zip(areas, centroids)) / total_area
                )
                result.centroid_v_native = float(
                    sum(a * c[1] for a, c in zip(areas, centroids)) / total_area
                )

        if open_:
            result.open_contour_length_native = float(
                sum(polyline_length(c.points) for c in open_)
            )

        for component_index, comp in enumerate(components, start=1):
            sampled = resample_polyline(
                comp.points,
                count=resample_points,
                closed=comp.closed,
            )
            for point_index, p in enumerate(sampled):
                point_rows.append({
                    "plane": plane,
                    "section_index": index,
                    "section_count": count,
                    "position_normalized": float(position_normalized),
                    "coordinate_native": float(coordinate),
                    "component_index": component_index,
                    "component_closed": bool(comp.closed),
                    "component_branched": bool(comp.branched),
                    "point_index": point_index,
                    "point_count": int(len(sampled)),
                    "x_native": float(p[0]),
                    "y_native": float(p[1]),
                    "z_native": float(p[2]),
                })

        return result, point_rows

    def series(
        self,
        plane: str,
        positions: np.ndarray,
        resample_points: int = 256,
    ) -> tuple[list[SectionResult], list[dict]]:
        positions = np.asarray(positions, dtype=float)
        results: list[SectionResult] = []
        point_rows: list[dict] = []
        count = len(positions)
        for i, pos in enumerate(positions, start=1):
            result, rows = self.section(
                plane=plane,
                index=i,
                count=count,
                position_normalized=float(pos),
                resample_points=resample_points,
            )
            results.append(result)
            point_rows.extend(rows)
        return results, point_rows
