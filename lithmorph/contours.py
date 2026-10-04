from __future__ import annotations

from collections import defaultdict, deque

import numpy as np

from .models import ContourComponent


def polyline_length(points: np.ndarray) -> float:
    points = np.asarray(points, dtype=float)
    if len(points) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def resample_polyline(
    points: np.ndarray,
    count: int = 256,
    closed: bool = False,
) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    if len(points) < 2:
        return points.copy()

    if closed:
        if np.linalg.norm(points[0] - points[-1]) > 0:
            p = np.vstack([points, points[0]])
        else:
            p = points
    else:
        p = points

    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(cumulative[-1])
    if total <= 0:
        return np.repeat(p[:1], count, axis=0)

    if closed:
        targets = np.linspace(0.0, total, count, endpoint=False)
    else:
        targets = np.linspace(0.0, total, count, endpoint=True)

    out = np.empty((len(targets), 3), dtype=float)
    for dim in range(3):
        out[:, dim] = np.interp(targets, cumulative, p[:, dim])
    return out


def assemble_contours(
    segments: np.ndarray,
    tolerance: float,
) -> list[ContourComponent]:
    """Assemble unordered 3D line segments into paths using quantized endpoints.

    This is intentionally conservative: large gaps are never bridged.
    """
    segments = np.asarray(segments, dtype=float)
    if segments.size == 0:
        return []
    if segments.ndim != 3 or segments.shape[1:] != (2, 3):
        raise ValueError("segments must have shape (N,2,3)")

    tol = float(tolerance)
    if tol <= 0:
        raise ValueError("tolerance must be positive")

    key_to_node: dict[tuple[int, int, int], int] = {}
    sums: list[np.ndarray] = []
    counts: list[int] = []

    def node_for(point: np.ndarray) -> int:
        key = tuple(np.rint(point / tol).astype(np.int64).tolist())
        idx = key_to_node.get(key)
        if idx is None:
            idx = len(sums)
            key_to_node[key] = idx
            sums.append(np.asarray(point, dtype=float).copy())
            counts.append(1)
        else:
            sums[idx] += point
            counts[idx] += 1
        return idx

    edges: list[tuple[int, int]] = []
    seen_edges: set[tuple[int, int]] = set()
    for seg in segments:
        a = node_for(seg[0])
        b = node_for(seg[1])
        if a == b:
            continue
        e = (a, b) if a < b else (b, a)
        if e in seen_edges:
            continue
        seen_edges.add(e)
        edges.append((a, b))

    if not edges:
        return []

    nodes = np.asarray(
        [s / float(c) for s, c in zip(sums, counts)],
        dtype=float,
    )
    adjacency: dict[int, list[int]] = defaultdict(list)
    for ei, (a, b) in enumerate(edges):
        adjacency[a].append(ei)
        adjacency[b].append(ei)

    unused = set(range(len(edges)))
    paths: list[ContourComponent] = []

    def other(ei: int, node: int) -> int:
        a, b = edges[ei]
        return b if a == node else a

    while unused:
        seed_edge = next(iter(unused))
        component_edges = set()
        q = deque([seed_edge])
        while q:
            ei = q.popleft()
            if ei in component_edges:
                continue
            component_edges.add(ei)
            a, b = edges[ei]
            for node in (a, b):
                for ej in adjacency[node]:
                    if ej not in component_edges:
                        q.append(ej)

        component_nodes = set()
        for ei in component_edges:
            component_nodes.update(edges[ei])

        degree = {
            node: sum(1 for ei in adjacency[node] if ei in component_edges)
            for node in component_nodes
        }
        branched = any(d > 2 for d in degree.values())

        local_unused = set(component_edges)

        def trace(start_node: int, start_edge: int) -> list[int]:
            result = [start_node]
            node = start_node
            edge = start_edge
            while True:
                if edge not in local_unused:
                    break
                local_unused.remove(edge)
                nxt = other(edge, node)
                result.append(nxt)
                node = nxt

                candidates = [
                    ei for ei in adjacency[node]
                    if ei in local_unused
                ]
                if not candidates:
                    break
                if node == start_node:
                    break
                edge = candidates[0]
            return result

        # Open/branched paths first, beginning at non-degree-2 nodes.
        terminals = sorted(
            [n for n, d in degree.items() if d != 2],
            key=lambda n: tuple(nodes[n]),
        )
        for node in terminals:
            while True:
                candidates = [
                    ei for ei in adjacency[node]
                    if ei in local_unused
                ]
                if not candidates:
                    break
                ids = trace(node, candidates[0])
                pts = nodes[ids]
                closed = len(ids) > 2 and ids[0] == ids[-1]
                paths.append(
                    ContourComponent(
                        points=pts,
                        closed=closed,
                        branched=branched,
                    )
                )

        # Remaining edges are cycles.
        while local_unused:
            ei = next(iter(local_unused))
            a, _b = edges[ei]
            ids = trace(a, ei)
            if ids[-1] != ids[0]:
                # A degree-2 cycle should return to its start. If numerical
                # topology failed, preserve it as open rather than force-close.
                closed = False
            else:
                closed = True
            paths.append(
                ContourComponent(
                    points=nodes[ids],
                    closed=closed,
                    branched=branched,
                )
            )

        unused -= component_edges

    return paths
