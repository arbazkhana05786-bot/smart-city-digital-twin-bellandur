"""
generate_dense_roads.py
=======================
Fetches the full drivable road network around Bellandur using OSMnx and
caches it as data/bellandur_dense_network.json so the dashboard never
re-fetches from the internet on every app rerun.

Each edge in the output includes a 'coordinates' key with a dense list of
[lon, lat] pairs extracted from the Shapely LineString geometry (or the
straight line between nodes when no geometry is stored).

Usage:
    python generate_dense_roads.py
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

CENTER_LAT   = 12.9260
CENTER_LON   = 77.6830
RADIUS_M     = 2200
NETWORK_TYPE = "drive"

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH  = PROJECT_ROOT / "data" / "bellandur_dense_network.json"


def geom_to_coords(geom) -> List[List[float]]:
    if geom is None:
        return []
    try:
        xs, ys = geom.xy
        return [[float(x), float(y)] for x, y in zip(xs, ys)]
    except Exception:
        return []


def straight_line_coords(G, u, v) -> List[List[float]]:
    u_data = G.nodes.get(u, {})
    v_data = G.nodes.get(v, {})
    return [
        [float(u_data.get("x", u_data.get("lon", 77.6762))),
         float(u_data.get("y", u_data.get("lat", 12.9260)))],
        [float(v_data.get("x", v_data.get("lon", 77.6830))),
         float(v_data.get("y", v_data.get("lat", 12.9260)))],
    ]


def build_from_osmnx() -> Dict[str, Any]:
    import osmnx as ox
    print(f"[generate_dense_roads] Fetching via OSMnx centre=({CENTER_LAT},{CENTER_LON}) radius={RADIUS_M}m")
    G = ox.graph_from_point((CENTER_LAT, CENTER_LON), dist=RADIUS_M,
                             network_type=NETWORK_TYPE, simplify=True, retain_all=False)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    nodes_out = [{"id": str(n), "lat": float(d.get("y", 0)), "lon": float(d.get("x", 0)),
                  "elevation_m": float(d.get("elevation", 882.0))}
                 for n, d in G.nodes(data=True)]

    edges_out = []
    for u, v, key, data in G.edges(data=True, keys=True):
        geom   = data.get("geometry")
        coords = geom_to_coords(geom) if geom else straight_line_coords(G, u, v)
        hw     = data.get("highway", "unclassified")
        edges_out.append({
            "source": str(u), "target": str(v), "key": key,
            "name": data.get("name", hw if isinstance(hw, str) else "Road"),
            "highway": hw if isinstance(hw, str) else str(hw),
            "distance_m": round(float(data.get("length", 100.0)), 1),
            "speed_kmh":  round(float(data.get("speed_kph", 40)), 1),
            "oneway": bool(data.get("oneway", False)),
            "coordinates": coords,
            "path_coords": coords,
        })

    return {"source": "osmnx", "center": [CENTER_LAT, CENTER_LON],
            "radius_m": RADIUS_M, "network_type": NETWORK_TYPE,
            "nodes": nodes_out, "edges": edges_out}


DENSE_COORDS_OVERRIDE = {
    "edge_bellandur_flyover_elevated": [
        [77.6655, 12.9208], [77.6685, 12.9222], [77.6710, 12.9235],
        [77.6728, 12.9248], [77.6748, 12.9256], [77.6765, 12.9262],
        [77.6795, 12.9260], [77.6820, 12.9254], [77.6842, 12.9250],
    ],
    "edge_bellandur_to_gear_school": [
        [77.6710, 12.9235], [77.6728, 12.9248], [77.6748, 12.9256],
        [77.6765, 12.9262],
    ],
    "edge_gear_school_to_sakra": [
        [77.6765, 12.9262], [77.6795, 12.9260], [77.6820, 12.9254],
        [77.6842, 12.9250], [77.6858, 12.9265], [77.6875, 12.9282],
    ],
    "edge_sarjapur_bypass_corridor": [
        [77.6655,12.9208],[77.6665,12.9195],[77.6675,12.9182],[77.6685,12.9175],
        [77.6700,12.9162],[77.6710,12.9153],[77.6720,12.9150],
    ],
    "edge_sarjapur_to_doddakannelli": [
        [77.6720,12.9150],[77.6745,12.9145],[77.6770,12.9142],[77.6800,12.9140],
        [77.6835,12.9137],[77.6865,12.9136],[77.6890,12.9135],
    ],
    "edge_doddakannelli_to_panathur": [
        [77.6890,12.9135],[77.6905,12.9155],[77.6918,12.9175],[77.6928,12.9195],
        [77.6937,12.9212],[77.6948,12.9232],[77.6960,12.9252],[77.6972,12.9268],
        [77.6985,12.9282],[77.6995,12.9290],
    ],
    "edge_kadubeesanahalli_to_marathahalli": [
        [77.6955,12.9355],[77.6962,12.9378],[77.6970,12.9400],[77.6975,12.9422],
        [77.6978,12.9445],[77.6982,12.9468],[77.6990,12.9492],[77.7000,12.9515],
        [77.7010,12.9550],
    ],
    "edge_evac_ecospace_to_kaikondrahalli": [
        [77.6842,12.9250],[77.6825,12.9238],[77.6808,12.9228],[77.6790,12.9218],
        [77.6775,12.9210],[77.6758,12.9202],[77.6748,12.9190],[77.6742,12.9175],
        [77.6740,12.9155],[77.6740,12.9125],
    ],
    "edge_evac_bellandur_to_sports": [
        [77.6710,12.9235],[77.6707,12.9252],[77.6705,12.9268],[77.6703,12.9282],
        [77.6700,12.9296],[77.6700,12.9308],[77.6702,12.9318],[77.6710,12.9320],
    ],
    "edge_iblur_to_bellandur_underpass": [
        [77.6655,12.9208],[77.6672,12.9215],[77.6685,12.9222],[77.6700,12.9230],
        [77.6710,12.9235],[77.6725,12.9245],[77.6740,12.9252],[77.6752,12.9258],
        [77.6765,12.9262],
    ],
    "edge_underpass_to_ecospace": [
        [77.6765,12.9262],[77.6778,12.9260],[77.6790,12.9258],[77.6800,12.9256],
        [77.6815,12.9254],[77.6828,12.9252],[77.6842,12.9250],
    ],
}


def build_from_fallback() -> Dict[str, Any]:
    fallback_path = PROJECT_ROOT / "data" / "osm_graphs" / "bengaluru_bellandur_network.json"
    print("[generate_dense_roads] Using fallback handcrafted network ...")
    if not fallback_path.exists():
        raise FileNotFoundError(f"Not found: {fallback_path}")
    with open(fallback_path, "r", encoding="utf-8") as fh:
        base = json.load(fh)
    edges_out = []
    for edge in base.get("edges", []):
        eid    = edge.get("id", "")
        coords = DENSE_COORDS_OVERRIDE.get(eid) or edge.get("path_coords", [])
        new_edge = dict(edge)
        new_edge["coordinates"] = coords
        new_edge["path_coords"] = coords
        edges_out.append(new_edge)
    return {"source": "fallback_handcrafted", "center": [CENTER_LAT, CENTER_LON],
            "radius_m": RADIUS_M, "network_type": NETWORK_TYPE,
            "nodes": base.get("nodes", []), "edges": edges_out}


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = build_from_osmnx()
    except Exception as exc:
        print(f"[generate_dense_roads] OSMnx failed ({exc}). Using fallback.")
        try:
            result = build_from_fallback()
        except Exception as exc2:
            print(f"[generate_dense_roads] ERROR: {exc2}", file=sys.stderr)
            sys.exit(1)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    curve_count = sum(1 for e in result["edges"] if len(e.get("coordinates", [])) >= 3)
    print(f"[generate_dense_roads] Saved to {OUTPUT_PATH}")
    print(f"  Edges: {len(result['edges'])}   with 3+ curve pts: {curve_count}")


if __name__ == "__main__":
    main()
