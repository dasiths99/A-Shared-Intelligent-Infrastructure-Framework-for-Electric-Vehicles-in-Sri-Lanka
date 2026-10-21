"""Road graph router (model 3.3) on Sri Lanka OSM major roads - shortest / fastest / energy-aware routes.

Built by database/seed.py. Edges in both directions unless one-way. Node elevation (Copernicus DEM) is smoothed
over the road network (DEM noise between points ~20 m apart would otherwise create fake climbs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

G, RHO = 9.81, 1.2


@dataclass
class Path_:
    nodes: np.ndarray
    edges: np.ndarray  # directed edge indices along the path


class RoadGraph:
    def __init__(self, processed: Path, smooth_iter: int = 4):
        n = pd.read_parquet(processed / "road_graph_nodes.parquet")
        e = pd.read_parquet(processed / "road_graph_edges.parquet")
        fwd = e[["u", "v", "length_m", "speed_kmh", "highway"]]
        back = e.loc[~e.oneway, ["v", "u", "length_m", "speed_kmh", "highway"]].set_axis(fwd.columns, axis=1)
        d = pd.concat([fwd, back], ignore_index=True)
        # one edge per directed node pair (sparse matrices would ADD duplicate pairs)
        d = d.sort_values("length_m").drop_duplicates(["u", "v"]).reset_index(drop=True)
        self.u, self.v = d.u.to_numpy(), d.v.to_numpy()
        self._pair = pd.Series(np.arange(len(d)), index=pd.MultiIndex.from_arrays([self.u, self.v]))
        self.length = d.length_m.to_numpy().clip(min=0.1)
        self.speed = d.speed_kmh.to_numpy()
        self.highway = d.highway.to_numpy()
        self.lon, self.lat = n.lon.to_numpy(), n.lat.to_numpy()
        N = len(n)
        adj = sparse.coo_matrix((np.ones(len(e) * 2), (np.r_[e.u, e.v], np.r_[e.v, e.u])), shape=(N, N)).tocsr()
        adj.data[:] = 1
        deg = np.asarray(adj.sum(axis=1)).ravel()
        z = n.elev_m.to_numpy(dtype=float)
        for _ in range(smooth_iter):
            z = (z + adj @ z) / (1 + deg)
        self.elev = z
        self.N = N
        self.lat0 = float(np.mean(self.lat))
        self._tree = cKDTree(np.c_[self.lon * np.cos(np.radians(self.lat0)), self.lat])

    # -------------------------------------------------------------- helpers
    def snap(self, lat: float, lon: float) -> tuple[int, float]:
        d, i = self._tree.query([lon * np.cos(np.radians(self.lat0)), lat])
        return int(i), float(d * 111_320)

    def time_s(self) -> np.ndarray:
        return self.length / (self.speed / 3.6)

    def energy_kwh(self, p: dict, ambient_c: float) -> np.ndarray:
        """Physics energy per edge for one vehicle (no acceleration term - stop/go unknown on a map)."""
        v = self.speed / 3.6
        dz = self.elev[self.v] - self.elev[self.u]
        ew = (p["mass_kg"] * G * p["crr"] + 0.5 * RHO * p["cda_m2"] * v ** 2) * self.length + p["mass_kg"] * G * dz
        eb = np.where(ew > 0, ew / p["eta_drive"], ew * p["eta_regen"]) / 3.6e6
        aux = (p["aux_base_kw"] + p["aux_cold_kw_per_C"] * max(0, 18 - ambient_c)
               + p["aux_hot_kw_per_C"] * max(0, ambient_c - 24)) * self.time_s() / 3600
        return eb + aux

    def shortest(self, src: int, dst: int, weight: np.ndarray) -> Path_ | None:
        w = np.maximum(weight, 1e-6)  # Dijkstra needs non-negative weights (regen edges -> almost free)
        A = sparse.csr_matrix((w, (self.u, self.v)), shape=(self.N, self.N))
        dist, pred = dijkstra(A, directed=True, indices=src, return_predecessors=True, min_only=False)
        if not np.isfinite(dist[dst]):
            return None
        nodes = [dst]
        while nodes[-1] != src:
            nodes.append(pred[nodes[-1]])
        nodes = np.array(nodes[::-1])
        edges = self._pair.loc[list(zip(nodes[:-1], nodes[1:]))].to_numpy()
        return Path_(nodes=nodes, edges=edges)
