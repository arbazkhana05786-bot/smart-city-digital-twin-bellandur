"""
Graph Loader (Network & GeoJSON Parser)
=======================================
Loads the Bengaluru Bellandur / Outer Ring Road road network graph from GraphML
(or JSON fallback) and exposes spatial node lookup helpers.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import networkx as nx

try:
    from shapely.geometry import LineString
except ImportError:
    LineString = None


# Default directory for OSM graphs
DEFAULT_OSM_DIR = Path(__file__).resolve().parent.parent / "data" / "osm_graphs"


class GraphLoader:
    """Class wrapper for loading road networks, graphml models, and building polygons."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        if base_dir is None:
            base_dir = DEFAULT_OSM_DIR
        base_path = Path(base_dir)

        if base_path.is_file():
            self.base_dir = base_path.parent
            if base_path.suffix.lower() == ".graphml":
                self.graphml_file = base_path
                self.network_file = base_path.with_suffix(".json")
            else:
                self.network_file = base_path
                self.graphml_file = base_path.with_suffix(".graphml")
        else:
            self.base_dir = base_path
            self.network_file = self.base_dir / "bengaluru_bellandur_network.json"
            self.graphml_file = self.base_dir / "bengaluru_bellandur_network.graphml"

        self.buildings_file = self.base_dir / "bengaluru_buildings.geojson"

        self._network_cache: Optional[Dict[str, Any]] = None
        self._buildings_cache: Optional[Dict[str, Any]] = None
        self._nx_graph: Optional[nx.MultiDiGraph] = None

    def load(self) -> nx.MultiDiGraph:
        """Loads and returns the networkx graph."""
        return self.get_graph()

    def get_graph(self) -> nx.MultiDiGraph:
        """Returns the parsed networkx.MultiDiGraph."""
        if self._nx_graph is None:
            self._nx_graph = self._build_graph()
        return self._nx_graph

    def _build_graph(self) -> nx.MultiDiGraph:
        """Constructs MultiDiGraph from GraphML or JSON fallback with bidirectional emergency links."""
        MG = nx.MultiDiGraph(crs="EPSG:4326")

        # 1. Try GraphML
        if self.graphml_file.exists():
            try:
                G_raw = nx.read_graphml(str(self.graphml_file))
                for n, data in G_raw.nodes(data=True):
                    attrs = dict(data)
                    attrs["lat"] = float(attrs.get("lat", attrs.get("y", 0.0)))
                    attrs["lon"] = float(attrs.get("lon", attrs.get("x", 0.0)))
                    attrs["x"] = attrs["lon"]
                    attrs["y"] = attrs["lat"]
                    attrs["elevation_m"] = float(attrs.get("elevation_m", 880.0))
                    MG.add_node(n, **attrs)

                for u, v, data in G_raw.edges(data=True):
                    attrs = dict(data)
                    weight = float(attrs.get("weight", attrs.get("distance_m", 1000.0)))
                    attrs["weight"] = weight
                    attrs["baseline_weight"] = weight
                    attrs["distance_m"] = float(attrs.get("distance_m", weight))
                    attrs["is_blocked"] = bool(attrs.get("is_blocked", False))
                    if "path_coords" in attrs and isinstance(attrs["path_coords"], str):
                        try:
                            attrs["path_coords"] = json.loads(attrs["path_coords"])
                        except Exception:
                            pass
                    if "path_coords" in attrs and isinstance(attrs["path_coords"], list) and len(attrs["path_coords"]) >= 2:
                        if LineString is not None:
                            try:
                                attrs["geometry"] = LineString(attrs["path_coords"])
                            except Exception:
                                pass
                    MG.add_edge(u, v, **attrs)
            except Exception:
                MG.clear()

        # 2. Fallback to JSON if GraphML failed or was empty
        if MG.number_of_nodes() == 0 and self.network_file.exists():
            try:
                with open(self.network_file, "r", encoding="utf-8") as f:
                    net_data = json.load(f)

                for node in net_data.get("nodes", []):
                    node_id = node["id"]
                    attrs = {k: v for k, v in node.items() if k != "id"}
                    attrs["lat"] = float(attrs.get("lat", attrs.get("y", 0.0)))
                    attrs["lon"] = float(attrs.get("lon", attrs.get("x", 0.0)))
                    attrs["x"] = attrs["lon"]
                    attrs["y"] = attrs["lat"]
                    MG.add_node(node_id, **attrs)

                for edge in net_data.get("edges", []):
                    u = edge["source"]
                    v = edge["target"]
                    attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
                    dist = float(attrs.get("distance_m", 1000.0))
                    attrs["weight"] = dist
                    attrs["baseline_weight"] = dist
                    attrs["distance_m"] = dist
                    attrs["is_blocked"] = False
                    if "path_coords" in attrs and isinstance(attrs["path_coords"], list) and len(attrs["path_coords"]) >= 2:
                        if LineString is not None:
                            try:
                                attrs["geometry"] = LineString(attrs["path_coords"])
                            except Exception:
                                pass
                    MG.add_edge(u, v, **attrs)
            except Exception:
                pass

        # 3. Ensure bidirectional connectivity for emergency transit
        for u, v, data in list(MG.edges(data=True)):
            if not MG.has_edge(v, u):
                rev_data = dict(data)
                if "path_coords" in rev_data and isinstance(rev_data["path_coords"], list):
                    rev_data["path_coords"] = list(reversed(rev_data["path_coords"]))
                    if LineString is not None and len(rev_data["path_coords"]) >= 2:
                        try:
                            rev_data["geometry"] = LineString(rev_data["path_coords"])
                        except Exception:
                            pass
                MG.add_edge(v, u, **rev_data)

        return MG

    def load_network(self) -> Dict[str, Any]:
        """Load and cache the Bellandur road network JSON."""
        if self._network_cache is None:
            if not self.network_file.exists():
                raise FileNotFoundError(f"Network file not found at {self.network_file}")
            with open(self.network_file, "r", encoding="utf-8") as f:
                self._network_cache = json.load(f)
        return self._network_cache

    def load_buildings(self) -> Dict[str, Any]:
        """Load and cache the building GeoJSON collection."""
        if self._buildings_cache is None:
            if not self.buildings_file.exists():
                raise FileNotFoundError(f"Buildings file not found at {self.buildings_file}")
            with open(self.buildings_file, "r", encoding="utf-8") as f:
                self._buildings_cache = json.load(f)
        return self._buildings_cache

    def get_nodes(self) -> List[Dict[str, Any]]:
        return self.load_network().get("nodes", [])

    def get_edges(self) -> List[Dict[str, Any]]:
        return self.load_network().get("edges", [])

    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        for n in self.get_nodes():
            if n.get("id") == node_id:
                return n
        return None

    def get_edge_by_id(self, edge_id: str) -> Optional[Dict[str, Any]]:
        for e in self.get_edges():
            if e.get("id") == edge_id:
                return e
        return None


def load_graph(path=None):
    """Factory helper to load networkx graph via GraphLoader."""
    loader = GraphLoader(path) if 'GraphLoader' in globals() else None
    if loader and hasattr(loader, 'load'):
        return loader.load()
    return None


def get_nearest_node(G, lat, lon):
    """
    Returns closest node in G or a fallback node id using Euclidean distance.
    """
    if G is None:
        return 0
    best_node = None
    min_dist = float('inf')
    for n, d in G.nodes(data=True):
        n_lat = d.get('y', d.get('lat', 0))
        n_lon = d.get('x', d.get('lon', 0))
        dist = (n_lat - lat)**2 + (n_lon - lon)**2
        if dist < min_dist:
            min_dist = dist
            best_node = n
    return best_node if best_node is not None else list(G.nodes())[0]


__all__ = ["GraphLoader", "load_graph", "get_nearest_node"]


if __name__ == "__main__":
    G = load_graph()
    print(f"Loaded networkx graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    nearest = get_nearest_node(G, 12.9260, 77.6762)
    print(f"Nearest node to Bellandur Underpass: {nearest} ({G.nodes[nearest]['name']})")
