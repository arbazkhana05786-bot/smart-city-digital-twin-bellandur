"""
Seed Sample & Benchmark Datasets
================================
Populates representative benchmark datasets for all 4 project domains
and exports the Bellandur GIS network to GraphML format.
"""

import os
import sys
import json
import random
from pathlib import Path
import networkx as nx

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

random.seed(42)

BASE_DIR = Path(__file__).resolve().parent

# 1. Convert JSON network to GraphML in data/osm_graphs/
json_path = BASE_DIR / "osm_graphs" / "bengaluru_bellandur_network.json"
graphml_path = BASE_DIR / "osm_graphs" / "bengaluru_bellandur_network.graphml"

if json_path.exists():
    with open(json_path, "r", encoding="utf-8") as f:
        net_data = json.load(f)

    G = nx.DiGraph(name=net_data.get("network_name", "Bellandur Network"), crs="EPSG:4326")
    for node in net_data.get("nodes", []):
        node_id = node["id"]
        attrs = {k: v for k, v in node.items() if k != "id"}
        attrs["signalized"] = int(attrs.get("signalized", False))
        G.add_node(node_id, **attrs)

    for edge in net_data.get("edges", []):
        u = edge["source"]
        v = edge["target"]
        attrs = {}
        for k, val in edge.items():
            if k in ("source", "target"):
                continue
            if isinstance(val, (list, dict)):
                attrs[k] = json.dumps(val)
            elif isinstance(val, bool):
                attrs[k] = int(val)
            else:
                attrs[k] = val
        attrs["weight"] = float(edge.get("distance_m", 100))
        G.add_edge(u, v, **attrs)

    nx.write_graphml(G, str(graphml_path))
    print(f"[✓] Wrote GraphML ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges) -> {graphml_path.name}")

# 2. Generate Earthquake Richter's Predictor Benchmark
eq_dir = BASE_DIR / "raw" / "earthquake"
eq_dir.mkdir(parents=True, exist_ok=True)
val_path = eq_dir / "train_values.csv"
lbl_path = eq_dir / "train_labels.csv"

val_rows = [
    "building_id,geo_level_1_id,geo_level_2_id,geo_level_3_id,count_floors_pre_eq,age,area_percentage,height_percentage,land_surface_condition,foundation_type,roof_type,ground_floor_type,other_floor_type,position,plan_configuration,has_superstructure_adobe_mud,has_superstructure_mud_mortar_stone,has_superstructure_stone_flag,has_superstructure_cement_mortar_stone,has_superstructure_mud_mortar_brick,has_superstructure_cement_mortar_brick,has_superstructure_timber,has_superstructure_bamboo,has_superstructure_rc_non_engineered,has_superstructure_rc_engineered,has_superstructure_other,legal_ownership_status,count_families,has_secondary_use"
]
lbl_rows = ["building_id,damage_grade"]

for i in range(1, 351):
    bid = 100000 + i
    g1 = random.choice([6, 8, 12, 17, 21, 26])
    g2 = g1 * 20 + random.randint(1, 15)
    g3 = g2 * 10 + random.randint(1, 9)
    floors = random.choices([1, 2, 3, 4, 5], weights=[0.2, 0.45, 0.25, 0.08, 0.02])[0]
    age = random.choices([5, 10, 15, 20, 30, 45, 60, 80], weights=[0.1, 0.2, 0.25, 0.2, 0.1, 0.08, 0.05, 0.02])[0]
    area = random.randint(5, 25)
    height = floors * 3 + random.randint(0, 2)
    l_surf = random.choice(["t", "n", "o"])
    found = random.choices(["r", "w", "i", "u", "h"], weights=[0.6, 0.15, 0.15, 0.07, 0.03])[0]
    roof = random.choices(["n", "q", "x"], weights=[0.6, 0.25, 0.15])[0]
    g_flr = random.choices(["f", "x", "v", "z", "m"], weights=[0.6, 0.15, 0.18, 0.05, 0.02])[0]
    o_flr = random.choices(["q", "s", "x", "j"], weights=[0.5, 0.3, 0.15, 0.05])[0]
    pos = random.choices(["s", "t", "j", "o"], weights=[0.65, 0.2, 0.1, 0.05])[0]
    plan = "d"

    adobe = 1 if random.random() < 0.15 else 0
    mud_mortar_stone = 1 if found == "r" and random.random() < 0.75 else 0
    stone_flag = 1 if random.random() < 0.08 else 0
    cement_stone = 1 if found in ("w", "i") and random.random() < 0.2 else 0
    mud_brick = 1 if random.random() < 0.1 else 0
    cement_brick = 1 if found in ("i", "u") and random.random() < 0.45 else 0
    timber = 1 if random.random() < 0.25 else 0
    bamboo = 1 if random.random() < 0.1 else 0
    rc_non_eng = 1 if found == "i" and random.random() < 0.3 else 0
    rc_eng = 1 if found == "i" and rc_non_eng == 0 and random.random() < 0.25 else 0
    other = 0
    legal = random.choice(["v", "a"])
    fam = random.choice([1, 1, 1, 2, 2, 3])
    sec_use = 1 if random.random() < 0.1 else 0

    val_rows.append(
        f"{bid},{g1},{g2},{g3},{floors},{age},{area},{height},{l_surf},{found},{roof},{g_flr},{o_flr},{pos},{plan},{adobe},{mud_mortar_stone},{stone_flag},{cement_stone},{mud_brick},{cement_brick},{timber},{bamboo},{rc_non_eng},{rc_eng},{other},{legal},{fam},{sec_use}"
    )

    if rc_eng or (cement_brick and age < 15 and floors <= 2):
        grade = random.choices([1, 2, 3], weights=[0.7, 0.25, 0.05])[0]
    elif mud_mortar_stone or adobe:
        grade = random.choices([1, 2, 3], weights=[0.08, 0.42, 0.50])[0]
    else:
        grade = random.choices([1, 2, 3], weights=[0.25, 0.55, 0.20])[0]
    lbl_rows.append(f"{bid},{grade}")

with open(val_path, "w", encoding="utf-8") as f:
    f.write("\n".join(val_rows))
with open(lbl_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lbl_rows))
print(f"[✓] Wrote {len(val_rows)-1} records -> {val_path.name} & {lbl_path.name}")

# 3. Generate Flood Rainfall-Runoff Benchmark
flood_dir = BASE_DIR / "raw" / "flood"
flood_dir.mkdir(parents=True, exist_ok=True)
flood_path = flood_dir / "rainfall_runoff.csv"

flood_rows = [
    "timestamp,catchment_zone,rainfall_intensity_mm_hr,cumulative_rainfall_mm,soil_saturation_index,drain_capacity_pct,bellandur_lake_inflow_cusecs,water_level_underpass_m,pumping_station_status,flood_alert_level"
]

zones = [
    "Bellandur_Underpass_Basin",
    "Ecospace_Storm_Spur",
    "Iblur_Junction_Catchment",
    "Devarabisanahalli_Sump_Zone"
]
cum_rain = 0.0
for hour in range(144):  # 6 days hourly logs
    day = 1 + hour // 24
    h = hour % 24
    ts = f"2026-09-0{day} {h:02d}:00:00"

    # Peak monsoon cloudburst on day 3
    if day == 3 and 13 <= h <= 18:
        rain = round(random.uniform(55.0, 92.5), 1)
    elif day in (2, 3):
        rain = round(random.uniform(20.0, 48.0), 1)
    elif day == 4 and h <= 8:
        rain = round(random.uniform(15.0, 32.0), 1)
    else:
        rain = round(random.uniform(0.0, 8.5), 1)

    cum_rain = round(cum_rain * 0.96 + rain, 1)
    sat_idx = round(min(0.98, 0.35 + cum_rain / 180.0), 2)
    drain_fill = round(min(100.0, 20.0 + (rain * 0.9) + (cum_rain * 0.15)), 1)
    inflow = round(850 + (rain * 90) + (cum_rain * 22), 0)

    if rain > 50.0 or drain_fill > 90.0:
        water_level = round(min(1.85, 0.3 + (drain_fill - 50) * 0.025), 2)
        pump_stat = "SUMP_BACKFLOW" if water_level > 1.2 else "ACTIVE_DISCHARGE"
        alert = "RED" if water_level > 1.0 else "ORANGE"
    elif rain > 25.0 or drain_fill > 70.0:
        water_level = round(min(0.85, 0.1 + (rain * 0.015)), 2)
        pump_stat = "ACTIVE_DISCHARGE"
        alert = "ORANGE" if water_level > 0.5 else "YELLOW"
    else:
        water_level = round(random.uniform(0.02, 0.18), 2)
        pump_stat = "OPTIMAL"
        alert = "GREEN"

    zone = zones[hour % len(zones)]
    flood_rows.append(f"{ts},{zone},{rain},{cum_rain},{sat_idx},{drain_fill},{inflow},{water_level},{pump_stat},{alert}")

with open(flood_path, "w", encoding="utf-8") as f:
    f.write("\n".join(flood_rows))
print(f"[✓] Wrote {len(flood_rows)-1} records -> {flood_path.name}")

# 4. Generate Traffic Sensor Benchmark
traf_dir = BASE_DIR / "raw" / "traffic"
traf_dir.mkdir(parents=True, exist_ok=True)
traf_path = traf_dir / "traffic_speeds_sensor.csv"

traf_rows = [
    "timestamp,sensor_id,corridor_name,segment_start,segment_end,flow_rate_pcu_hr,avg_speed_kmh,free_flow_speed_kmh,congestion_index,occupancy_percentage,incident_detected"
]

sensors = [
    ("CAM-ORR-01", "Iblur Junction", "Bellandur Gate"),
    ("CAM-ORR-04", "Bellandur Underpass", "Ecospace Gate 1"),
    ("CAM-ORR-08", "Ecospace Gate 2", "Devarabisanahalli Ramp"),
    ("CAM-ORR-12", "Devarabisanahalli Flyover Ramp", "Kadubeesanahalli Spine"),
    ("CAM-ORR-16", "Kadubeesanahalli Spine", "Marathahalli Bridge")
]

for hour in range(96):  # 4 days hourly
    day = 1 + hour // 24
    h = hour % 24
    ts = f"2026-10-1{day} {h:02d}:00:00"

    is_peak = (8 <= h <= 11) or (17 <= h <= 21)

    for s_id, s_start, s_end in sensors:
        if is_peak:
            flow = random.randint(2600, 3450)
            if s_id == "CAM-ORR-04":
                spd = round(random.uniform(4.5, 12.0), 1)
                cong = round(random.uniform(0.82, 0.98), 2)
                occ = round(random.uniform(85.0, 98.0), 1)
                inc = "WATERLOGGED_CHOKEPOINT"
            else:
                spd = round(random.uniform(14.0, 26.0), 1)
                cong = round(random.uniform(0.60, 0.80), 2)
                occ = round(random.uniform(65.0, 84.0), 1)
                inc = "NONE"
        else:
            flow = random.randint(650, 1850)
            spd = round(random.uniform(42.0, 58.0), 1)
            cong = round(random.uniform(0.12, 0.35), 2)
            occ = round(random.uniform(15.0, 42.0), 1)
            inc = "NONE"

        traf_rows.append(
            f"{ts},{s_id},Bellandur Outer Ring Road Arterial,{s_start},{s_end},{flow},{spd},60.0,{cong},{occ},{inc}"
        )

with open(traf_path, "w", encoding="utf-8") as f:
    f.write("\n".join(traf_rows))
print(f"[✓] Wrote {len(traf_rows)-1} records -> {traf_path.name}")

# 5. Generate Road Damage / Potholes Benchmark
rd_dir = BASE_DIR / "raw" / "road_damage"
rd_dir.mkdir(parents=True, exist_ok=True)
rd_path = rd_dir / "pothole_annotations.csv"

rd_rows = [
    "image_id,camera_feed,location,latitude,longitude,damage_type,severity,estimated_width_cm,estimated_depth_cm,yolo_bbox,confidence_score,bbmp_ward,repair_priority"
]

locs = [
    ("Bellandur Underpass Service Lane (Southbound)", 12.9262, 77.6765),
    ("Ecospace Gate 2 Ingress Road", 12.9255, 77.6835),
    ("Devarabisanahalli Service Road Ramp", 12.9288, 77.6890),
    ("Iblur Junction Left-Turn Spur", 12.9210, 77.6660),
    ("ORR Central Median Transition Spall", 12.9248, 77.6740)
]

for i in range(1, 151):
    img_id = f"BLR_ROAD_HAZ_{i:04d}.jpg"
    feed = random.choice(["ORR_MOBILE_PATROL_04", "CITIZEN_PWA_FIELD_FEED", "BTP_SURVEILLANCE_DRONE_02"])
    loc_name, base_lat, base_lon = random.choice(locs)
    lat = round(base_lat + random.uniform(-0.0015, 0.0015), 5)
    lon = round(base_lon + random.uniform(-0.0015, 0.0015), 5)

    dtype = random.choices(
        ["Pothole", "Deep Road Cavity", "Longitudinal Pavement Fracture", "Sunken Manhole Spall"],
        weights=[0.5, 0.2, 0.2, 0.1]
    )[0]
    sev = random.choices(["CRITICAL", "MODERATE", "MINOR"], weights=[0.35, 0.45, 0.20])[0]

    if sev == "CRITICAL":
        width = round(random.uniform(55.0, 140.0), 1)
        depth = round(random.uniform(12.0, 26.0), 1)
        priority = "P1_URGENT_BBMP_DISPATCH"
    elif sev == "MODERATE":
        width = round(random.uniform(25.0, 54.0), 1)
        depth = round(random.uniform(5.0, 11.5), 1)
        priority = "P2_SCHEDULED_REPAIR"
    else:
        width = round(random.uniform(10.0, 24.0), 1)
        depth = round(random.uniform(2.0, 4.8), 1)
        priority = "P3_ROUTINE_PATCH"

    xmin = random.randint(120, 400)
    ymin = random.randint(180, 500)
    xmax = xmin + random.randint(80, 250)
    ymax = ymin + random.randint(60, 200)
    bbox = f"[{xmin}, {ymin}, {xmax}, {ymax}]"
    conf = round(random.uniform(0.85, 0.98), 2)

    rd_rows.append(
        f"{img_id},{feed},{loc_name},{lat},{lon},{dtype},{sev},{width},{depth},\"{bbox}\",{conf},Ward 150 - Bellandur,{priority}"
    )

with open(rd_path, "w", encoding="utf-8") as f:
    f.write("\n".join(rd_rows))
print(f"[✓] Wrote {len(rd_rows)-1} records -> {rd_path.name}")
print("\n[SUCCESS] All benchmark datasets and GIS graph successfully populated.")
