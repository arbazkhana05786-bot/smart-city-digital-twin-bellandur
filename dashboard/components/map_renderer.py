"""
Map Renderer Component - Stage 1 Frontend
PyDeck 3D Map Visualizer for Bengaluru Bellandur / ORR Corridor.
Renders 3D extruded buildings, rising blue flood planes, road network geometries,
emergency detour paths, fire hazard perimeters, and safe assembly grounds.
"""

import json
import os
from typing import Dict, Any, List
import pydeck as pdk

# Ensure pdk.CoordinateSystem.LNGLAT exists across all pydeck versions
if not hasattr(pdk, "CoordinateSystem"):
    class _CoordinateSystem:
        LNGLAT = 1
        CARTESIAN = 0
        METER_OFFSETS = 2
        DEFAULT = 1
    pdk.CoordinateSystem = _CoordinateSystem

# ---------------------------------------------------------------------------
# Module-level paths (resolved once at import time)
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "osm_graphs")
)
_DATA_DIR               = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data")
)
_BUILDINGS_GEOJSON_PATH = os.path.join(_BASE_DIR, "bengaluru_buildings.geojson")
# Prefer dense cached network; fall back to legacy OSM network
_DENSE_NETWORK_PATH     = os.path.join(_DATA_DIR, "bellandur_dense_network.json")
_NETWORK_JSON_PATH      = os.path.join(_BASE_DIR, "bengaluru_bellandur_network.json")


def _load_json(path: str, fallback) -> Any:
    """Load a JSON file with a safe fallback on any error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _unpack_curve_points(path: List[Any], dense_net: Dict[str, Any] = None) -> List[List[float]]:
    """
    Retrieves and unpacks all intermediate curve points along consecutive edge segments
    rather than connecting junction centroids directly.
    """
    if not path:
        return []
    # If path elements are segment dicts
    if all(isinstance(p, dict) for p in path):
        out = []
        for segment in path:
            seg_pts = segment.get("coordinates") or segment.get("path_coords") or []
            for pt in seg_pts:
                if not out or out[-1] != pt:
                    out.append(pt)
        if len(out) >= 2:
            return out

    pts = [[float(p[0]), float(p[1])] for p in path if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) <= 1 or not dense_net:
        return pts

    # If already high density (>= 12 curve points), return directly
    if len(pts) >= 12:
        return pts

    edges = dense_net.get("edges", [])
    if not edges:
        return pts

    unpacked = []
    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i + 1]
        best_segment = None
        min_dist = float("inf")

        for e in edges:
            ecoords = e.get("coordinates") or e.get("path_coords") or []
            if len(ecoords) < 2:
                continue
            e_start = ecoords[0]
            e_end = ecoords[-1]
            d_fwd = (p1[0] - e_start[0])**2 + (p1[1] - e_start[1])**2 + (p2[0] - e_end[0])**2 + (p2[1] - e_end[1])**2
            d_rev = (p1[0] - e_end[0])**2 + (p1[1] - e_end[1])**2 + (p2[0] - e_start[0])**2 + (p2[1] - e_start[1])**2

            if d_fwd < min_dist:
                min_dist = d_fwd
                best_segment = ecoords
            if d_rev < min_dist:
                min_dist = d_rev
                best_segment = list(reversed(ecoords))

        if best_segment and min_dist < 0.0001:
            for pt in best_segment:
                if not unpacked or unpacked[-1] != pt:
                    unpacked.append(pt)
        else:
            if not unpacked or unpacked[-1] != p1:
                unpacked.append(p1)
            unpacked.append(p2)

    return unpacked if len(unpacked) >= len(pts) else pts


class MapRenderer:
    """Constructs PyDeck Deck with custom 3D and vector hazard layers."""

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        # Locked viewport: Bellandur Underpass tactical overview
        self.center_lat = 12.9260
        self.center_lon = 77.6762
        self.zoom = 15.0
        self.pitch = 50.0
        self.bearing = -20.0

    def create_deck(
        self,
        buildings_geojson: Dict[str, Any],
        edges: List[Dict[str, Any]],
        ems_route_info: Dict[str, Any],
        rainfall_mm: float = 0.0,
        fire_info: Dict[str, Any] = None,
        seismic_magnitude: float = 0.0,
        signal_states: List[Dict[str, Any]] = None,
        assembly_grounds: List[Dict[str, Any]] = None,
        evacuation_route_info: Dict[str, Any] = None,
    ) -> pdk.Deck:
        """
        Assemble PyDeck layers dynamically based on current simulation state.

        Layer stack (bottom → top):
          [0] Raster TileLayer basemap   — Carto Dark PNG tiles, no token needed
          [1] OSM road skeleton          — PathLayer from network JSON
          [2] OSM 3D building footprints — GeoJsonLayer extruded
          [3] Simulation buildings       — PolygonLayer with seismic tinting
          [4] Flood inundation plane     — conditional PolygonLayer
          [5] Road network (sim edges)   — PathLayer coloured by blockage
          [6] EMS bypass corridor        — PathLayer (green)
          [7] Fire CA hazard rings       — PolygonLayer (amber)
          [8] Assembly grounds + markers — ScatterplotLayer
          [9] Traffic signals            — ScatterplotLayer
        """
        layers: List[pdk.Layer] = []

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 0a — Satellite Imagery Basemap (ESRI World Imagery)
        # ─────────────────────────────────────────────────────────────────────
        # High-resolution satellite raster tiles fetched directly by the browser.
        # Zero token required — ESRI ArcGIS Online tiles are openly accessible.
        # map_provider=None + map_style=None on pdk.Deck ensures no Mapbox/GL
        # token handshake is triggered. The TileLayer IS the sole basemap.
        satellite_layer = pdk.Layer(
            "TileLayer",
            id="satellite-basemap",
            data="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            min_zoom=0,
            max_zoom=19,
            tile_size=256,
            opacity=1.0,
            # CRITICAL: LNGLAT coordinate system prevents tile frustum clipping
            # at non-zero camera pitch angles.
            coordinate_system=pdk.CoordinateSystem.LNGLAT,
        )
        layers.append(satellite_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 0b — Road Labels & Place Names Overlay (ESRI World Boundaries)
        # ─────────────────────────────────────────────────────────────────────
        # Semi-transparent overlay rendered above the satellite imagery.
        # Provides street names, tech park labels, and administrative boundaries
        # over the raw satellite tiles without obscuring the imagery beneath.
        labels_layer = pdk.Layer(
            "TileLayer",
            id="satellite-labels",
            data="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
            min_zoom=0,
            max_zoom=19,
            tile_size=256,
            opacity=0.85,
            coordinate_system=pdk.CoordinateSystem.LNGLAT,
        )
        layers.append(labels_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 1 — OSM Road Skeleton (dense curve geometry)
        # ─────────────────────────────────────────────────────────────────────
        # Prefers the dense cached network (bellandur_dense_network.json) which
        # contains multi-point 'coordinates' arrays that hug real asphalt curves.
        # Falls back to the legacy OSM network JSON if dense file is unavailable.
        _dense_net = _load_json(_DENSE_NETWORK_PATH, fallback=None)
        if _dense_net is None:
            _dense_net = _load_json(_NETWORK_JSON_PATH, fallback={"edges": []})

        osm_road_paths = []
        for edge in _dense_net.get("edges", []):
            # 'coordinates' (dense) preferred; 'path_coords' as fallback
            coords = edge.get("coordinates") or edge.get("path_coords", [])
            if len(coords) >= 2:
                raw_name = edge.get("name", "Road")
                name_str = " ".join(str(x) for x in raw_name) if isinstance(raw_name, list) else str(raw_name or "Road")
                name_lower = name_str.lower()
                osm_road_paths.append({
                    "name":        name_str,
                    "path":        coords,
                    "type":        "Road Network Corridor",
                    "status":      "BLOCKED" if edge.get("is_blocked") else "CLEAR",
                    "depth":       "Dense Asphalt Geometry",
                    "hazard_info": " | Low-Elevation Risk" if edge.get("vulnerable_to_flood") else "",
                    # Colour: blocked=red, flood-vulnerable=amber,
                    # elevated/flyover=sky-blue, regular=muted slate
                    "color": (
                        [239, 68,  68,  200] if edge.get("is_blocked") else
                        [251, 191, 36,  190] if edge.get("vulnerable_to_flood") else
                        [56,  189, 248, 200] if ("flyover" in name_lower or
                                                 "elevated" in name_lower) else
                        [100, 116, 139, 180]   # muted slate — satellite contrast
                    ),
                    "width": 6 if edge.get("is_blocked") else 3,
                })

        osm_road_layer = pdk.Layer(
            "PathLayer",
            osm_road_paths,
            id="road-skeleton",
            get_path="path",
            get_color="color",
            get_width="width",
            width_min_pixels=1,
            width_max_pixels=7,
            pickable=True,
            rounded=True,
        )
        layers.append(osm_road_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 2 — OSM Real 3D Extruded Building Footprints (GeoJsonLayer)
        # ─────────────────────────────────────────────────────────────────────
        _osm_geojson = _load_json(
            _BUILDINGS_GEOJSON_PATH,
            fallback={"type": "FeatureCollection", "features": []}
        )

        osm_buildings_layer = pdk.Layer(
            "GeoJsonLayer",
            _osm_geojson,
            id="buildings-3d",
            extruded=True,
            wireframe=True,
            # Elevation: prefer explicit height → floors*3.5 fallback → 25 m default
            get_elevation="properties.height || properties.floors * 3.5 || 25",
            elevation_scale=1,
            # Layer 2 spec: translucent slate-grey [30, 41, 59, 180]
            get_fill_color=[30, 41, 59, 180],
            get_line_color=[51, 65, 85, 255],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(osm_buildings_layer)

        # ─────────────────────────────────────────────────────────────────────
        # ─────────────────────────────────────────────────────────────────────
        # LAYER 3 — Simulation Buildings (PolygonLayer, fire & seismic tinted)
        # ─────────────────────────────────────────────────────────────────────
        # Compute building centroids for dynamic spatial adjacency in fire/seismic
        def _get_centroid(poly_coords):
            if not poly_coords or not poly_coords[0]:
                return 0.0, 0.0
            ring = poly_coords[0]
            avg_lon = sum(pt[0] for pt in ring) / len(ring)
            avg_lat = sum(pt[1] for pt in ring) / len(ring)
            return avg_lon, avg_lat

        # Resolve Fire Origin & Secondary Spread
        fire_active = bool(fire_info and fire_info.get("fire_active"))
        fire_origin_name = (fire_info.get("origin_building") or "RMZ Ecoworld Tower 4A") if fire_active else ""
        wind_speed_kmh = float(fire_info.get("wind_speed_kmh", 20.0)) if fire_active else 0.0
        fire_severity = str(fire_info.get("threat_level", fire_info.get("severity", ""))) if fire_active else ""
        is_fire_critical = "CRITICAL" in fire_severity.upper()

        secondary_spread_active = fire_active and (wind_speed_kmh > 35.0 or is_fire_critical)
        secondary_spread_building = ""

        if secondary_spread_active:
            # Find origin building centroid
            origin_centroid = None
            candidate_centroids = {}
            for feat in buildings_geojson.get("features", []):
                props = feat.get("properties", {})
                b_name = props.get("name", "")
                b_type = props.get("type", "")
                c = _get_centroid(feat.get("geometry", {}).get("coordinates", []))
                if b_name == fire_origin_name:
                    origin_centroid = c
                elif b_type not in ["hospital", "emergency_service"]:
                    candidate_centroids[b_name] = c

            if origin_centroid and candidate_centroids:
                # Calculate nearest adjacent building centroid to simulate fire spreading downwind
                min_dist_sq = float("inf")
                for cand_name, cand_c in candidate_centroids.items():
                    d_sq = (cand_c[0] - origin_centroid[0])**2 + (cand_c[1] - origin_centroid[1])**2
                    if d_sq < min_dist_sq:
                        min_dist_sq = d_sq
                        secondary_spread_building = cand_name

        bldg_data = []
        for feat in buildings_geojson.get("features", []):
            props = feat.get("properties", {})
            geom  = feat.get("geometry", {})
            coords = geom.get("coordinates", [])

            b_type = props.get("type", "commercial_office")
            b_name = props.get("name", "")
            height = props.get("height", 30.0)

            # 1. Critical Medical Node — Emergency Purple / Violet (Guardrail)
            if b_type == "hospital" or "hospital" in b_name.lower() or "sakra" in b_name.lower():
                color = [168, 85, 247, 230]
                line_color = [216, 180, 254, 255]
                b_type_label = "Critical Medical Node"
                b_status_label = "OPERATIONAL — Trauma Priority Hub"
            elif b_type == "emergency_service":
                color = [16, 185, 129, 230]
                line_color = [52, 211, 153, 200]
                b_type_label = "Emergency Response Base"
                b_status_label = "DISPATCH READY"
            elif fire_active:
                # Fire Engine Dynamics
                if b_name == fire_origin_name:
                    # Primary fire origin: deep flaming crimson with active pulsing amber boundary
                    color = [239, 68, 68, 240]
                    line_color = [251, 146, 60, 255]
                    b_type_label = "Commercial Tech Park (Fire Origin)"
                    b_status_label = "CRITICAL — Active Thermal Hazard"
                elif secondary_spread_active and b_name == secondary_spread_building:
                    # Secondary spread: amber-orange simulate downwind spread
                    color = [249, 115, 22, 220]
                    line_color = [251, 146, 60, 255]
                    b_type_label = "Commercial Tech Park (Downwind Risk)"
                    b_status_label = "WARNING — Downwind Thermal Exposure"
                else:
                    # Non-affected tech towers: operational cyan/slate
                    color = [30, 41, 59, 180]
                    line_color = [51, 65, 85, 255]
                    b_type_label = "Commercial Tech Park"
                    b_status_label = "Nominal"
            elif seismic_magnitude > 0.0:
                # Earthquake Richter Dynamics
                b_type_label = "Commercial Tech Park" if b_type != "residential" else "Residential High-Rise"
                if seismic_magnitude < 3.5:
                    # Minor (M < 3.5): 0% structural damage, all buildings stable cyan
                    color = [56, 189, 248, 180]
                    line_color = [125, 211, 252, 200]
                    b_status_label = "Nominal — Stable"
                elif 3.5 <= seismic_magnitude < 6.0:
                    # Moderate (3.5 <= M < 6.0): Masonry crack warnings on medium/high risk
                    if props.get("structural_risk") in ["high", "medium"]:
                        color = [245, 158, 11, 210]
                        line_color = [251, 191, 36, 255]
                        b_status_label = "Structural Warning — Masonry Stress"
                    else:
                        color = [56, 189, 248, 180]
                        line_color = [125, 211, 252, 160]
                        b_status_label = "Nominal — Resilient"
                else:
                    # Severe (M >= 6.0): Buildings along fault line turn deep collapse-red [220, 38, 38, 240]
                    color = [220, 38, 38, 240]
                    line_color = [239, 68, 68, 255]
                    b_status_label = "CRITICAL — Structural Collapse Hazard"
            else:
                # Default Operational View
                if b_type == "residential":
                    color = [100, 116, 139, 210]
                    line_color = [148, 163, 184, 140]
                    b_type_label = "Residential High-Rise"
                    b_status_label = "Nominal"
                else:
                    color = [56, 189, 248, 200]
                    line_color = [125, 211, 252, 160]
                    b_type_label = "Commercial Tech Park"
                    b_status_label = "Nominal"

            if coords:
                bldg_data.append({
                    "name":        props.get("name", "Building"),
                    "type":        b_type_label,
                    "status":      b_status_label,
                    "depth":       f"{int(props.get('occupancy', 1000))} occupants | Elevation {props.get('elevation', 882.0):.0f}m",
                    "hazard_info": "",
                    "height":      height * 1.5,   # Exaggerate for 3D aesthetics
                    "color":       color,
                    "line_color":  line_color,
                    "polygon":     coords[0],
                    "occupancy":   props.get("occupancy", 1000),
                    "elevation":   props.get("elevation", 882.0),
                })

        building_layer = pdk.Layer(
            "PolygonLayer",
            bldg_data,
            id="3d-buildings-layer",
            get_polygon="polygon",
            get_elevation="height",
            get_fill_color="color",
            get_line_color="line_color",
            line_width_min_pixels=1,
            extruded=True,
            wireframe=True,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(building_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 4 — Rising Flood Water Inundation Plane (Bellandur Basin)
        # ─────────────────────────────────────────────────────────────────────
        if rainfall_mm >= 30.0:
            flood_alpha     = min(210, int(90 + (rainfall_mm - 30.0) * 1.6))
            flood_elev_m    = max(5.0, (rainfall_mm - 30.0) * 0.4)
            flood_basin     = [
                [77.6710, 12.9230],
                [77.6800, 12.9240],
                [77.6825, 12.9275],
                [77.6765, 12.9295],
                [77.6715, 12.9270],
                [77.6710, 12.9230],
            ]
            flood_data = [{
                "name":        "Bellandur Underpass Flood Breach Zone",
                "type":        "Stormwater Inundation / Waterlogging",
                "depth":       "1.2 meters",
                "status":      "CRITICAL — Vehicle Submersion Risk",
                "hazard_info": f" | Low-Elevation Storm Runoff Breach ({rainfall_mm:.0f}mm rainfall)",
                "polygon":     flood_basin,
                "elevation":   flood_elev_m,
                # Layer 3 spec: semi-transparent cyan [14, 116, 144, 160]
                "color":       [14, 116, 144, 160],
            }]
            flood_layer = pdk.Layer(
                "PolygonLayer",
                flood_data,
                id="flood-inundation-layer",
                get_polygon="polygon",
                get_elevation="elevation",
                get_fill_color="color",
                get_line_color=[56, 189, 248, 250],
                line_width_min_pixels=2,
                extruded=True,
                pickable=True,
            )
            layers.append(flood_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 5 — Simulation Road Network (dynamic edges, blockage-coloured)
        # ─────────────────────────────────────────────────────────────────────
        road_paths = []
        for edge in edges:
            coords = edge.get("path_coords", [])
            if coords:
                road_paths.append({
                    "name":        edge.get("name", "Road Link"),
                    "path":        coords,
                    "color":       edge.get("color", [148, 163, 184, 180]),
                    "width":       8 if edge.get("is_blocked") else 4,
                    "type":        "Simulation Road Edge",
                    "status":      edge.get("status_text", "CLEAR"),
                    "depth":       f"Speed: {edge.get('effective_speed_kmh', 40.0):.0f} km/h",
                    "hazard_info": " | Active Traffic Link",
                })

        sim_road_layer = pdk.Layer(
            "PathLayer",
            road_paths,
            id="road-network-layer",
            get_path="path",
            get_color="color",
            get_width="width",
            width_min_pixels=3,
            width_max_pixels=10,
            pickable=True,
            rounded=True,
        )
        layers.append(sim_road_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 6 — Active EMS Corridor (Google-Maps-style dual-stroke route)
        # ─────────────────────────────────────────────────────────────────────
        # Two-layer technique: dark casing outline rendered first (behind),
        # then vibrant emerald fill on top — identical to Google Maps navigation.
        ems_path = (ems_route_info.get("path_coords") or ems_route_info.get("waypoints")) if ems_route_info else None
        if ems_route_info and ems_path:
            ems_path = _unpack_curve_points(ems_path, _dense_net)
            route_label = ems_route_info.get("route_name", "EMS Corridor")
            route_status = ems_route_info.get("status_badge", "ACTIVE")
            route_eta    = f"{ems_route_info.get('est_time_min', 5.0):.1f} min"

            # 6a — Dark contrast casing (outline / backing stroke)
            ems_casing_data = [{
                "name":        route_label,
                "path":        ems_path,
                "color":       [6, 78, 59, 200],   # Deep forest green casing
                "type":        "Active EMS Corridor",
                "status":      route_status,
                "depth":       f"ETA: {route_eta}",
                "hazard_info": " | Signal Preemption Engaged",
            }]
            ems_casing_layer = pdk.Layer(
                "PathLayer",
                ems_casing_data,
                id="ems-corridor-casing",
                get_path="path",
                get_color="color",
                get_width=9,                   # wider than fill = visible outline
                width_min_pixels=7,
                width_max_pixels=18,
                pickable=False,
                rounded=True,
            )
            layers.append(ems_casing_layer)

            # 6b — Vibrant emerald fill (primary visible stroke)
            ems_fill_data = [{
                "name":        route_label,
                "path":        ems_path,
                "color":       [16, 185, 129, 255],  # Emerald green #10B981
                "type":        "Active EMS Corridor",
                "status":      route_status,
                "depth":       f"ETA: {route_eta}",
                "hazard_info": " | Green Wave Preempted",
            }]
            ems_fill_layer = pdk.Layer(
                "PathLayer",
                ems_fill_data,
                id="ems-corridor-fill",
                get_path="path",
                get_color="color",
                get_width=6,
                width_min_pixels=4,
                width_max_pixels=12,
                pickable=True,
                rounded=True,
            )
            layers.append(ems_fill_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 6c — Evacuation Route / Safe Assembly Corridor
        # ─────────────────────────────────────────────────────────────────────
        evac_path = (
            evacuation_route_info.get("path_coords") or
            evacuation_route_info.get("evacuation_corridor_coords") or
            evacuation_route_info.get("waypoints")
        ) if evacuation_route_info else None
        if evacuation_route_info and evac_path:
            evac_path = _unpack_curve_points(evac_path, _dense_net)
            evac_label = evacuation_route_info.get("route_name", "Safe Evacuation Corridor")

            # Evacuation casing (dark outline)
            layers.append(pdk.Layer(
                "PathLayer",
                [{
                    "name":        evac_label,
                    "path":        evac_path,
                    "color":       [6, 78, 59, 200],
                    "type":        "Safe Evacuation Corridor",
                    "status":      "OPEN & PASSABLE",
                    "depth":       "Pedestrian & Light Vehicle Transit",
                    "hazard_info": "",
                }],
                id="evacuation-corridor-casing",
                get_path="path",
                get_color="color",
                get_width=10,
                width_min_pixels=8,
                width_max_pixels=18,
                pickable=False,
                rounded=True,
            ))

            # Evacuation line (clean emerald green line)
            layers.append(pdk.Layer(
                "PathLayer",
                [{
                    "name":        evac_label,
                    "path":        evac_path,
                    "color":       [16, 185, 129, 255],
                    "type":        "Safe Evacuation Corridor",
                    "status":      "OPEN & PASSABLE",
                    "depth":       "Pedestrian & Light Vehicle Transit",
                    "hazard_info": "",
                }],
                id="evacuation-corridor-fill",
                get_path="path",
                get_color="color",
                get_width=6,
                width_min_pixels=4,
                width_max_pixels=12,
                pickable=True,
                rounded=True,
            ))

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 7 — Fire CA Hazard Boundary Rings (orange/amber)
        # ─────────────────────────────────────────────────────────────────────
        if fire_info and fire_info.get("fire_active") and fire_info.get("rings"):
            fire_data = [
                {
                    "name":        f"Fire Boundary ({ring.get('ring_name')})",
                    "polygon":     ring.get("polygon"),
                    "type":        "Thermal Hazard Perimeter",
                    "status":      "ACTIVE SPREAD",
                    "depth":       "Heat Radiation Radius",
                    "hazard_info": " | Evacuate Area",
                    "color":       ring.get("color", [249, 115, 22, 180]),
                }
                for ring in fire_info["rings"]
            ]
            fire_layer = pdk.Layer(
                "PolygonLayer",
                fire_data,
                id="fire-spread-ca-layer",
                get_polygon="polygon",
                get_fill_color="color",
                get_line_color=[255, 237, 213, 220],
                line_width_min_pixels=2,
                extruded=False,
                pickable=True,
            )
            layers.append(fire_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 8 — Safe Assembly Grounds & Medical Nodes (ScatterplotLayer)
        # ─────────────────────────────────────────────────────────────────────
        point_markers = []
        if assembly_grounds:
            for g in assembly_grounds:
                point_markers.append({
                    "name":        g.get("name"),
                    "coordinates": [g.get("lon"), g.get("lat")],
                    "color":       [168, 85, 247, 240],   # Purple shelter
                    "radius":      55,
                    "type":        "Safe Assembly Ground",
                    "status":      "OPEN & SAFE",
                    "depth":       f"Capacity: {g.get('current_count')}/{g.get('max_capacity')} Sheltered",
                    "hazard_info": "",
                })

        # Fixed anchors
        point_markers.extend([
            {
                "name":        "Sakra World Hospital (Critical Medical Node)",
                "coordinates": [77.6875, 12.9282],
                "color":       [168, 85, 247, 240],   # Emergency Purple
                "radius":      65,
                "type":        "Trauma & Emergency Care Hub",
                "status":      "OPERATIONAL — Trauma Priority Hub",
                "depth":       "Level-1 Trauma & Surgical Facility",
                "hazard_info": " | Priority Ingress",
            },
            {
                "name":        "Iblur EMS Dispatch Base",
                "coordinates": [77.6655, 12.9208],
                "color":       [16, 185, 129, 255],
                "radius":      50,
                "type":        "Rapid Response Ambulance Station",
                "status":      "DISPATCH READY",
                "depth":       "Ambulance Staging Hub",
                "hazard_info": "",
            },
        ])

        points_layer = pdk.Layer(
            "ScatterplotLayer",
            point_markers,
            id="key-markers-layer",
            get_position="coordinates",
            get_fill_color="color",
            get_radius="radius",
            radius_min_pixels=6,
            radius_max_pixels=16,
            pickable=True,
        )
        layers.append(points_layer)

        # ─────────────────────────────────────────────────────────────────────
        # LAYER 9 — Adaptive Traffic Signals Overlay
        # ─────────────────────────────────────────────────────────────────────
        if signal_states:
            sig_data = [
                {
                    "name":        f"Signal: {sig.get('name')}",
                    "coordinates": [sig.get("lon"), sig.get("lat")],
                    "color":       sig.get("color_rgb", [34, 197, 94]) + [255],
                    "radius":      32,
                    "type":        "Adaptive Traffic Signal",
                    "status":      f"Mode: {sig.get('mode', 'DYNAMIC')}",
                    "depth":       f"Green: {sig.get('green_duration_sec', 60)}s | Red: {sig.get('red_duration_sec', 60)}s",
                    "hazard_info": "",
                }
                for sig in signal_states
            ]
            signals_layer = pdk.Layer(
                "ScatterplotLayer",
                sig_data,
                id="traffic-signals-layer",
                get_position="coordinates",
                get_fill_color="color",
                get_radius="radius",
                radius_min_pixels=5,
                radius_max_pixels=10,
                pickable=True,
            )
            layers.append(signals_layer)

        # ─────────────────────────────────────────────────────────────────────
        # ViewState — with seismic jitter offset when magnitude ≥ 4.5
        # ─────────────────────────────────────────────────────────────────────
        pitch   = self.pitch   + (2.5 if seismic_magnitude >= 4.5 else 0.0)
        bearing = self.bearing + (3.0 if seismic_magnitude >= 4.5 else 0.0)

        view_state = pdk.ViewState(
            latitude=12.9260,
            longitude=77.6762,
            zoom=15.0,
            pitch=pitch,
            bearing=bearing,
        )

        tooltip = {
            "html": (
                "<b>{name}</b><br/>"
                "<span style='color: #94a3b8;'>Type:</span> {type}<br/>"
                "<span style='color: #38bdf8;'>Status:</span> {status}<br/>"
                "<span style='color: #f87171;'>Detail:</span> {depth}{hazard_info}"
            ),
            "style": {
                "backgroundColor": "#0f172a",
                "color": "#f8fafc",
                "fontSize": "12px",
                "borderRadius": "6px",
                "padding": "8px 12px",
                "border": "1px solid #334155",
            },
        }

        # ─────────────────────────────────────────────────────────────────────
        # Assemble Deck
        # ─────────────────────────────────────────────────────────────────────
        # map_provider=None  → no Mapbox / Carto GL style loader is started
        # map_style=None     → PyDeck renders a transparent canvas background
        #
        # The raster TileLayer at layers[0] IS the basemap.
        # This is the only configuration that works without a Mapbox API key:
        # - Any map_style string   → triggers Mapbox GL JS loader → token missing → BLACK
        # - map_provider="carto"   → still uses GL renderer path  → token missing → BLACK
        # - map_style=None + TileLayer → browser fetches PNG tiles directly → ✅ RENDERS
        # map_provider=None + map_style=None: no Mapbox GL token handshake.
        # The raster TileLayer at layers[0] (with LNGLAT coordinate_system) IS
        # the sole basemap.  ANY map_style string triggers the Mapbox GL loader
        # which returns a black void when the token is absent.
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
            map_provider=None,
            map_style=None,
        )

        return deck
