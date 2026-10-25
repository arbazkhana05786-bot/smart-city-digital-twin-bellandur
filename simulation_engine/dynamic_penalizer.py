"""
Dynamic Penalizer (Edge-Disaster Intersection Engine)
=====================================================
Evaluates real-time hazard proximity and spatial flood polygon intersection
against road network edges. Dynamically invalidates blocked segments (setting
infinite weight) to ensure emergency corridors navigate around flood depressions.
"""

import math
from typing import Dict, Any, List, Tuple, Union, Optional
import networkx as nx

# Bellandur Underpass low-elevation flood basin polygon [lon, lat].
# Derived from the surveyed inundation boundary of the Bellandur ORR underpass depression.
# User-authoritative polygon: (lat, lon) = [(12.9252, 77.6745), (12.9270, 77.6750), (12.9268, 77.6780), (12.9248, 77.6775)]
# Stored in [lon, lat] order for consistency with GeoJSON / PyDeck conventions.
BELLANDUR_FLOOD_POLYGON = [
    [77.6745, 12.9252],
    [77.6750, 12.9270],
    [77.6780, 12.9268],
    [77.6775, 12.9248],
    [77.6745, 12.9252]   # closed ring
]

# Alias matching the variable name specified in the task
FLOOD_POLYGON = BELLANDUR_FLOOD_POLYGON


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def point_in_polygon(lon: float, lat: float, polygon: Optional[List[List[float]]] = None) -> bool:
    """
    Ray-casting algorithm to test if (lon, lat) is strictly inside a polygon boundary.
    """
    if polygon is None:
        polygon = BELLANDUR_FLOOD_POLYGON

    inside = False
    n = len(polygon)
    p1_lon, p1_lat = polygon[0]
    for i in range(1, n + 1):
        p2_lon, p2_lat = polygon[i % n]
        if lat > min(p1_lat, p2_lat):
            if lat <= max(p1_lat, p2_lat):
                if lon <= max(p1_lon, p2_lon):
                    if p1_lat != p2_lat:
                        xinters = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
                    if p1_lon == p2_lon or lon <= xinters:
                        inside = not inside
        p1_lon, p1_lat = p2_lon, p2_lat
    return inside


def _parse_path_coords(raw) -> List[List[float]]:
    """Parses path_coords whether stored as a list or a JSON-encoded string (from GraphML)."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        import json as _json
        try:
            parsed = _json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


def edge_intersects_flood(
    u: str,
    v: str,
    data: Dict[str, Any],
    flood_polygon: Optional[List[List[float]]] = None,
    num_samples: int = 20
) -> bool:
    """
    Strict geometric test: returns True if the edge line (its waypoints or interpolated
    segments) intersects or lies inside the flood polygon boundary.
    Handles path_coords stored as a list OR as a JSON-encoded string (from GraphML).
    """
    if flood_polygon is None:
        flood_polygon = BELLANDUR_FLOOD_POLYGON

    # 1. Check path_coords (list or JSON string)
    path_coords = _parse_path_coords(data.get("path_coords", []))
    if path_coords:
        # Check every explicit waypoint
        for pt in path_coords:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                if point_in_polygon(float(pt[0]), float(pt[1]), flood_polygon):
                    return True

        # Dense linear interpolation to catch transversal intersections
        for i in range(len(path_coords) - 1):
            p_a = path_coords[i]
            p_b = path_coords[i + 1]
            for step in range(1, num_samples):
                t = step / float(num_samples)
                slon = float(p_a[0]) + t * (float(p_b[0]) - float(p_a[0]))
                slat = float(p_a[1]) + t * (float(p_b[1]) - float(p_a[1]))
                if point_in_polygon(slon, slat, flood_polygon):
                    return True

    # 2. Check geometry attribute if stored as geojson dict
    geom = data.get("geometry", None)
    if isinstance(geom, dict) and geom.get("type") == "LineString":
        coords = geom.get("coordinates", [])
        for pt in coords:
            if point_in_polygon(float(pt[0]), float(pt[1]), flood_polygon):
                return True

    # 3. Semantic tags: underpass nodes and flood-vulnerable service roads are always blocked
    edge_id = str(data.get("id", "")).lower()
    edge_name = str(data.get("name", "")).lower()
    if "underpass" in edge_id or "underpass" in edge_name:
        return True
    if data.get("vulnerable_to_flood", False) and "service" in edge_id:
        return True

    return False


def invalidate_hazard_edges(
    G: Optional[nx.MultiDiGraph] = None,
    hazard_coords: Union[Tuple[float, float], List[float]] = (12.9260, 77.6762),
    radius_meters: float = 250.0,
    flood_polygon: Optional[List[List[float]]] = None,
    rainfall_mm: float = 0.0
) -> List[Tuple[str, str]]:
    """
    Marks edges as impassable (weight=float('inf'), is_blocked=True) for any edge whose
    geometry intersects or lies inside the flood polygon, or whose endpoint/waypoint falls
    within radius_meters of hazard_coords.
    """
    if G is None:
        return []

    if flood_polygon is None:
        flood_polygon = BELLANDUR_FLOOD_POLYGON

    h_lat = float(hazard_coords[0])
    h_lon = float(hazard_coords[1])
    blocked_edges = []

    for u, v, k, data in G.edges(keys=True, data=True):
        # --- Test 1: strict geometric flood-polygon intersection ---
        is_flood_intersect = edge_intersects_flood(u, v, data, flood_polygon)

        # --- Test 2: also block if EITHER endpoint node is inside the polygon ---
        u_data = G.nodes.get(u, {})
        v_data = G.nodes.get(v, {})
        u_lat = float(u_data.get("lat", u_data.get("y", 0.0)))
        u_lon = float(u_data.get("lon", u_data.get("x", 0.0)))
        v_lat = float(v_data.get("lat", v_data.get("y", 0.0)))
        v_lon = float(v_data.get("lon", v_data.get("x", 0.0)))

        node_in_poly = (
            point_in_polygon(u_lon, u_lat, flood_polygon) or
            point_in_polygon(v_lon, v_lat, flood_polygon)
        )

        # --- Test 3: proximity radius around active hazard coordinate ---
        d_u = haversine_distance_meters(h_lat, h_lon, u_lat, u_lon)
        d_v = haversine_distance_meters(h_lat, h_lon, v_lat, v_lon)
        min_dist = min(d_u, d_v)

        path_coords = _parse_path_coords(data.get("path_coords", []))
        for pt in path_coords:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                d_pt = haversine_distance_meters(h_lat, h_lon, float(pt[1]), float(pt[0]))
                if d_pt < min_dist:
                    min_dist = d_pt

        is_near_hazard = (min_dist <= radius_meters)

        if is_flood_intersect or node_in_poly or is_near_hazard:
            data["weight"] = float("inf")
            data["is_blocked"] = True
            blocked_edges.append((u, v))

    return blocked_edges


def reset_graph_weights(G: Optional[nx.MultiDiGraph] = None) -> None:
    """
    Restores default weights for all edges across the graph.
    Resets 'is_blocked' to False.
    """
    if G is None:
        return
    for u, v, k, data in G.edges(keys=True, data=True):
        baseline = data.get("baseline_weight", data.get("distance_m", data.get("length", 1.0)))
        data["weight"] = float(baseline)
        data["is_blocked"] = False


class DynamicPenalizer:
    """Calculates hazard-induced edge impedances and passable/impassable route states."""

    def __init__(self, G: Optional[nx.MultiDiGraph] = None):
        self.G = G
        self.flood_polygon = BELLANDUR_FLOOD_POLYGON
        self.COLOR_NORMAL = [148, 163, 184, 180]
        self.COLOR_IMPASSABLE = [239, 68, 68, 240]
        self.COLOR_WARNING = [245, 158, 11, 210]
        self.COLOR_ACTIVE_EMS = [16, 185, 129, 240]
        self.COLOR_DETOUR = [56, 189, 248, 220]

    def invalidate(
        self,
        hazard_coords: Union[Tuple[float, float], List[float]] = (12.9260, 77.6762),
        radius_meters: float = 250.0,
        flood_polygon: Optional[List[List[float]]] = None
    ) -> List[Tuple[str, str]]:
        if self.G is not None:
            return invalidate_hazard_edges(self.G, hazard_coords, radius_meters, flood_polygon)
        return []

    def reset(self) -> None:
        if self.G is not None:
            reset_graph_weights(self.G)

    def penalize_network(
        self,
        edges: List[Dict[str, Any]],
        rainfall_mm: float = 0.0,
        fire_active: bool = False,
        speed_anomaly_active: bool = False,
        force_underpass_block: bool = False
    ) -> List[Dict[str, Any]]:
        penalized_edges = []
        for edge in edges:
            edge_copy = dict(edge)
            distance_m = edge_copy.get("distance_m", 1000)
            base_speed_kmh = edge_copy.get("base_speed_kmh", 40.0)

            is_blocked = False
            status_text = "CLEAR"
            penalty_multiplier = 1.0
            color = list(self.COLOR_NORMAL)

            threshold = edge_copy.get("flood_threshold_rainfall_mm", 999.0)
            if (edge_copy.get("vulnerable_to_flood", False) and (rainfall_mm >= threshold or force_underpass_block)) or \
               edge_intersects_flood(edge.get("source", ""), edge.get("target", ""), edge_copy, self.flood_polygon):
                is_blocked = True
                status_text = "IMPASSABLE_FLOODED"
                penalty_multiplier = 999.0
                color = list(self.COLOR_IMPASSABLE)
            elif fire_active and "ecospace" in edge_copy.get("id", ""):
                is_blocked = True
                status_text = "BLOCKED_FIRE_ZONE"
                penalty_multiplier = 50.0
                color = list(self.COLOR_IMPASSABLE)
            elif speed_anomaly_active and ("underpass" in edge_copy.get("id", "") or "sakra" in edge_copy.get("id", "")):
                is_blocked = True
                status_text = "GRIDLOCK_ANOMALY"
                penalty_multiplier = 100.0
                color = list(self.COLOR_IMPASSABLE)
            elif "flyover_elevated" in edge_copy.get("id", "") or "gear_school" in edge_copy.get("id", ""):
                if rainfall_mm >= 20.0 or force_underpass_block:
                    status_text = "ACTIVE_BYPASS_CORRIDOR"
                    color = list(self.COLOR_DETOUR)
                    penalty_multiplier = 0.9
            elif "sarjapur" in edge_copy.get("id", "") or "panathur" in edge_copy.get("id", ""):
                if rainfall_mm >= 20.0 or speed_anomaly_active:
                    status_text = "RECOMMENDED_DETOUR"
                    color = list(self.COLOR_ACTIVE_EMS)

            current_speed = 0.1 if is_blocked else (base_speed_kmh / penalty_multiplier)
            travel_time_sec = (distance_m / 1000.0) / (current_speed / 3600.0)

            edge_copy["is_blocked"] = is_blocked
            edge_copy["status_text"] = status_text
            edge_copy["penalty_multiplier"] = penalty_multiplier
            edge_copy["color"] = color
            edge_copy["effective_speed_kmh"] = round(current_speed, 1)
            edge_copy["effective_travel_time_sec"] = round(travel_time_sec, 1)

            penalized_edges.append(edge_copy)

        return penalized_edges


__all__ = [
    "DynamicPenalizer",
    "invalidate_hazard_edges",
    "reset_graph_weights",
    "edge_intersects_flood",
    "point_in_polygon",
    "BELLANDUR_FLOOD_POLYGON",
    "haversine_distance_meters"
]


if __name__ == "__main__":
    import sys
    from pathlib import Path
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        from simulation_engine.graph_loader import load_graph
    except ImportError:
        from graph_loader import load_graph

    G = load_graph()
    print("Initial edges count:", G.number_of_edges() if G else 0)
    blocked = invalidate_hazard_edges(G, (12.9262, 77.6765), radius_meters=300)
    print("Blocked edges around Bellandur Underpass / Flood Mesh:", len(blocked))
    reset_graph_weights(G)
    print("Graph weights successfully reset.")
