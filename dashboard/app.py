"""
Smart City Planning and Simulation Engine (Bengaluru Base)
Stage 1: Frontend Command Hub & Simulation Orchestrator
Pilot Corridor: Outer Ring Road (ORR) - Bellandur - Devarabisanahalli Corridor
"""

import sys
from pathlib import Path
import yaml
import pydeck as pdk

# Ensure pdk.CoordinateSystem.LNGLAT exists across all pydeck versions
if not hasattr(pdk, "CoordinateSystem"):
    class _CoordinateSystem:
        LNGLAT = 1
        CARTESIAN = 0
        METER_OFFSETS = 2
        DEFAULT = 1
    pdk.CoordinateSystem = _CoordinateSystem

import streamlit as st

# Setup import paths
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Simulation and Model Imports
try:
    from simulation_engine.graph_loader import GraphLoader, load_graph, get_nearest_node
except ImportError:
    try:
        from simulation_engine.graph_loader import GraphLoader
        load_graph = lambda *args, **kwargs: None
        get_nearest_node = lambda G, lat, lon: 0
    except Exception as e:
        st.warning(f"Graph loader note: {e}")
try:
    from simulation_engine.dynamic_penalizer import DynamicPenalizer, invalidate_hazard_edges, reset_graph_weights
except ImportError:
    try:
        from simulation_engine.dynamic_penalizer import DynamicPenalizer
        invalidate_hazard_edges = lambda *args, **kwargs: []
        reset_graph_weights = lambda *args, **kwargs: None
    except Exception as e:
        DynamicPenalizer = None
        invalidate_hazard_edges = lambda *args, **kwargs: []
        reset_graph_weights = lambda *args, **kwargs: None

from simulation_engine.adaptive_signal_controller import AdaptiveSignalController
from simulation_engine.anomaly_speed_detector import AnomalySpeedDetector

try:
    from simulation_engine.ambulance_router import (
        AmbulanceRouter,
        compute_green_corridor,
        START_COORDS,
        PRIMARY_TARGET,
        SECONDARY_FALLBACK,
        GEAR_SCHOOL_NORTH_BYPASS,
        SARJAPUR_SOUTH_BYPASS
    )
except ImportError:
    START_COORDS = (12.9260, 77.6762)
    PRIMARY_TARGET = (12.9248, 77.6833)
    SECONDARY_FALLBACK = (12.9166, 77.6782)
    # Dense elevated ORR flyover bypass coordinates [lon, lat] — ORR elevated flyover skirting flood basin
    GEAR_SCHOOL_NORTH_BYPASS = [
        [77.6710, 12.9235],
        [77.6712, 12.9278],
        [77.6740, 12.9304],
        [77.6768, 12.9312],
        [77.6805, 12.9305],
        [77.6838, 12.9288],
        [77.6875, 12.9282]
    ]
    SARJAPUR_SOUTH_BYPASS = [
        [77.6655, 12.9208],
        [77.6685, 12.9175],
        [77.6720, 12.9150],
        [77.6800, 12.9140],
        [77.6890, 12.9135],
        [77.6940, 12.9210],
        [77.6995, 12.9290]
    ]
    AmbulanceRouter = None
    compute_green_corridor = lambda *args, **kwargs: {
        "waypoints": GEAR_SCHOOL_NORTH_BYPASS,
        "lat_lon_waypoints": [[pt[1], pt[0]] for pt in GEAR_SCHOOL_NORTH_BYPASS],
        "total_distance_km": 1.6,
        "eta_minutes": 2.0,
        "hospital_name": "Sakra World Hospital (Primary Trauma Center)",
        "is_rerouted": False,
        "path_nodes": [],
        "route_status": "OFFLINE ELEVATED FLYOVER BYPASS"
    }
from simulation_engine.evacuation_router import EvacuationRouter

from models.inference.vision_detector import MockVisionDetector
from models.inference.disaster_predictor import MockDisasterPredictor
from models.inference.fire_spread_ca import MockFireSpreadCA

from dashboard.components.map_renderer import MapRenderer
from dashboard.components.control_panel import ControlPanel
from dashboard.components.action_card import ActionCardRenderer
from dashboard.components.citizen_feed import CitizenFeedRenderer

# -----------------------------------------------------------------------------
# Streamlit Page Setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BLR Central Crisis Hub — Smart City Simulation",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = "BTP-8042"
if "portal_tab" not in st.session_state:
    st.session_state.portal_tab = "OPERATIONS CONTROL"
if "nav_view" not in st.session_state:
    st.session_state.nav_view = "MONITORING"  # MONITORING | DISASTER | DISASTER_FLOOD | DISASTER_FIRE | DISASTER_EARTHQUAKE | TRAFFIC | CITIZEN_REPORT

# Ticket triage session state
if "ticket_status" not in st.session_state:
    st.session_state.ticket_status = {
        "1042": "PENDING",
        "1043": "PENDING",
        "1044": "PENDING",
        "1045": "PENDING"
    }

# Action plan execution state
if "plan_executed" not in st.session_state:
    st.session_state.plan_executed = {
        "flood": False,
        "fire": False,
        "earthquake": False,
        "traffic": False
    }

# Contextual Hazard Options per Operational Domain
CONTEXTUAL_HAZARDS = {
    "flood": [
        "🌊 Waterlogging / Lake Overflow",
        "🌊 Low-Elevation Storm Runoff Breach",
        "🌊 Sump Pump Station 4 Backflow",
        "🚧 Silt & Mud Accumulation Blockage",
        "⚠️ Other / Custom Hazard"
    ],
    "fire": [
        "🔥 Fire / Toxic Smoke Drift",
        "🔥 Structural Commercial SEZ Blaze",
        "🔥 Electrical Transformer Explosion",
        "🔥 Flammable Chemical Storage Hazard",
        "⚠️ Other / Custom Hazard"
    ],
    "earthquake": [
        "🧱 Collapsed Structural Debris / Spalling",
        "🚧 Road Cave-In / Ramp Fracture",
        "⚡ Ground Fissure / Pavement Displacement",
        "⚠️ Flyover Expansion Joint Dislodged",
        "⚠️ Other / Custom Hazard"
    ],
    "traffic": [
        "🚧 Tanker Breakdown / Deadlock Chokepoint",
        "🚗 Multi-Vehicle Collision / Pileup",
        "🌳 Fallen Tree / Lane Obstruction",
        "🛑 Stalled Public Transit Bus (BMTC)",
        "⚠️ Other / Custom Hazard"
    ]
}

# Standardized Target Road Network Segments for Human Ingestion
TARGET_ROAD_SEGMENTS = {
    "Bellandur Underpass": {
        "blocked_path": [
            [77.6710, 12.9235],
            [77.6765, 12.9262],
            [77.6800, 12.9256],
            [77.6842, 12.9250]
        ],
        "bypass_path": [
            [77.6710, 12.9235],
            [77.6712, 12.9278],
            [77.6740, 12.9304],
            [77.6768, 12.9312],
            [77.6805, 12.9305],
            [77.6838, 12.9288],
            [77.6875, 12.9282]
        ],
        "bypass_name": "RECALCULATED BYPASS: Bellandur Elevated Flyover & Gear School Road to Sakra Hospital"
    },
    "Ecospace Gate 2": {
        "blocked_path": [
            [77.6800, 12.9256],
            [77.6842, 12.9250],
            [77.6875, 12.9282]
        ],
        "bypass_path": [
            [77.6705, 12.9235],
            [77.6712, 12.9278],
            [77.6740, 12.9304],
            [77.6768, 12.9312],
            [77.6820, 12.9300],
            [77.6875, 12.9282]
        ],
        "bypass_name": "RECALCULATED BYPASS: Outer Service Lane Diverter via Ecospace North"
    },
    "Devarabisanahalli Flyover Ramp": {
        "blocked_path": [
            [77.6875, 12.9282],
            [77.6905, 12.9305]
        ],
        "bypass_path": [
            [77.6842, 12.9250],
            [77.6875, 12.9282],
            [77.6860, 12.9320],
            [77.6955, 12.9355]
        ],
        "bypass_name": "RECALCULATED BYPASS: At-Grade Ground Diverter to Kadubeesanahalli"
    },
    "Iblur / Sarjapur Junction Exit": {
        "blocked_path": [
            [77.6655, 12.9208],
            [77.6710, 12.9235]
        ],
        "bypass_path": [
            [77.6655, 12.9208],
            [77.6685, 12.9175],
            [77.6720, 12.9150],
            [77.6770, 12.9265],
            [77.6875, 12.9282]
        ],
        "bypass_name": "RECALCULATED BYPASS: Kaikondrahalli Arterial Diverter to ORR Mainline"
    }
}

# -----------------------------------------------------------------------------
# Dynamic Fire Corridor Building Registry & Spatial Adjacency
# -----------------------------------------------------------------------------
CORRIDOR_FIRE_BUILDINGS = [
    "RMZ Ecoworld Tower 4A",
    "Ecospace Campus 2B",
    "Ecospace Campus 1A - Tech Tower",
    "Intel Campus Block 3",
    "Green Glen Residential Hub",
    "Bellandur Commercial Complex"
]

BUILDING_ACCESS_LANES = {
    "RMZ Ecoworld Tower 4A": [
        [77.6865, 12.9220],
        [77.6890, 12.9220],
        [77.6890, 12.9238]
    ],
    "Ecospace Campus 2B": [
        [77.6842, 12.9235],
        [77.6865, 12.9240],
        [77.6865, 12.9255]
    ],
    "Ecospace Campus 1A - Tech Tower": [
        [77.6820, 12.9240],
        [77.6842, 12.9242],
        [77.6842, 12.9260]
    ],
    "Intel Campus Block 3": [
        [77.6890, 12.9235],
        [77.6915, 12.9240],
        [77.6920, 12.9260]
    ],
    "Green Glen Residential Hub": [
        [77.6735, 12.9275],
        [77.6760, 12.9280],
        [77.6760, 12.9300]
    ],
    "Bellandur Commercial Complex": [
        [77.6765, 12.9240],
        [77.6790, 12.9242],
        [77.6790, 12.9262]
    ],
    "RMZ Ecoworld The Bay Club": [
        [77.6892, 12.9215],
        [77.6912, 12.9215],
        [77.6920, 12.9235]
    ],
    "Bellandur Lakeview Apartments (Low Depression Zone)": [
        [77.6730, 12.9250],
        [77.6748, 12.9250],
        [77.6750, 12.9265]
    ],
    "Devarabisanahalli Tech Hub Block C": [
        [77.6915, 12.9300],
        [77.6932, 12.9300],
        [77.6935, 12.9320]
    ],
    "Prestige Tech Park Horizon": [
        [77.6945, 12.9340],
        [77.6970, 12.9340],
        [77.6970, 12.9360]
    ]
}

def get_building_access_lane(bldg_name, centroid=None):
    """Retrieve or generate access lane coordinates for any corridor building."""
    if bldg_name in BUILDING_ACCESS_LANES:
        return BUILDING_ACCESS_LANES[bldg_name]
    if centroid:
        lon, lat = centroid
        return [
            [lon - 0.0018, lat - 0.0010],
            [lon, lat],
            [lon + 0.0018, lat + 0.0010]
        ]
    return [[77.6842, 12.9235], [77.6865, 12.9240], [77.6865, 12.9255]]

def find_nearest_adjacent_building(origin_name, buildings_geojson, exclude_types=("hospital", "emergency_service")):
    """
    Finds the building in buildings_geojson whose polygon centroid is closest to origin_name's centroid.
    Returns (nearest_name, nearest_centroid, origin_centroid).
    """
    origin_c = None
    candidates = {}
    for feat in buildings_geojson.get("features", []):
        props = feat.get("properties", {})
        name = props.get("name", "")
        b_type = props.get("type", "")
        coords = feat.get("geometry", {}).get("coordinates", [])
        if coords and coords[0]:
            ring = coords[0]
            avg_lon = sum(pt[0] for pt in ring) / len(ring)
            avg_lat = sum(pt[1] for pt in ring) / len(ring)
            c = (avg_lon, avg_lat)
            if name == origin_name:
                origin_c = c
            elif b_type not in exclude_types:
                candidates[name] = c

    if not origin_c or not candidates:
        return None, None, origin_c

    min_dist_sq = float("inf")
    nearest_name = None
    nearest_c = None
    for cand_name, cand_c in candidates.items():
        dist_sq = (cand_c[0] - origin_c[0]) ** 2 + (cand_c[1] - origin_c[1]) ** 2
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            nearest_name = cand_name
            nearest_c = cand_c

    return nearest_name, nearest_c, origin_c

# -----------------------------------------------------------------------------
# Tactical City Background SVG (Bengaluru Radial Arteries & Ring Roads)
# -----------------------------------------------------------------------------
TACTICAL_BG_SVG = """
<div class="tactical-bg-layer" aria-hidden="true">
  <svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="hubGlow" cx="50%" cy="48%" r="60%">
        <stop offset="0%" stop-color="#161F30" stop-opacity="0.95" />
        <stop offset="55%" stop-color="#0B0F19" stop-opacity="0.98" />
        <stop offset="100%" stop-color="#05070D" stop-opacity="1" />
      </radialGradient>
      
      <linearGradient id="amberRoadGlow" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#F59E0B" stop-opacity="0.75" />
        <stop offset="50%" stop-color="#F59E0B" stop-opacity="0.3" />
        <stop offset="100%" stop-color="#F59E0B" stop-opacity="0.05" />
      </linearGradient>

      <linearGradient id="emeraldRoadGlow" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#10B981" stop-opacity="0.8" />
        <stop offset="70%" stop-color="#10B981" stop-opacity="0.2" />
        <stop offset="100%" stop-color="#10B981" stop-opacity="0.02" />
      </linearGradient>

      <pattern id="tacticalGrid" width="60" height="60" patternUnits="userSpaceOnUse">
        <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#161F30" stroke-width="1" stroke-opacity="0.45" />
        <circle cx="0" cy="0" r="1.5" fill="#F59E0B" fill-opacity="0.25" />
      </pattern>
    </defs>

    <rect width="100%" height="100%" fill="url(#hubGlow)" />
    <rect width="100%" height="100%" fill="url(#tacticalGrid)" />

    <!-- Concentric Ring Roads of Bengaluru -->
    <circle cx="800" cy="480" r="150" fill="none" stroke="#1E293B" stroke-width="1.8" stroke-dasharray="6,4" opacity="0.6" />
    <circle cx="800" cy="480" r="270" fill="none" stroke="#161F30" stroke-width="2" stroke-opacity="0.8" />
    <circle cx="800" cy="480" r="410" fill="none" stroke="#F59E0B" stroke-width="2.2" stroke-opacity="0.4" />
    <circle cx="800" cy="480" r="410" fill="none" stroke="#10B981" stroke-width="1.2" stroke-dasharray="14,10" opacity="0.75" />
    <circle cx="800" cy="480" r="620" fill="none" stroke="#1E293B" stroke-width="1.5" stroke-dasharray="8,8" opacity="0.4" />

    <!-- Radial Arteries -->
    <line x1="800" y1="480" x2="1480" y2="820" stroke="url(#amberRoadGlow)" stroke-width="4.5" />
    <line x1="800" y1="480" x2="1480" y2="820" stroke="#F59E0B" stroke-width="1.5" stroke-dasharray="8,6" />
    <line x1="800" y1="480" x2="1320" y2="990" stroke="#10B981" stroke-width="2.5" stroke-opacity="0.5" />
    <line x1="800" y1="480" x2="1580" y2="520" stroke="#1E293B" stroke-width="2.5" stroke-opacity="0.7" />
    <line x1="800" y1="480" x2="800" y2="20" stroke="#1E293B" stroke-width="3" stroke-opacity="0.75" />
    <line x1="800" y1="480" x2="220" y2="90" stroke="#1E293B" stroke-width="2" stroke-opacity="0.6" />
  </svg>
</div>
"""

# -----------------------------------------------------------------------------
# Custom CSS Design System
# -----------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap');

html, body, .stApp {
    background-color: #0B0F19 !important;
    color: #F8FAFC !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    overflow-x: hidden !important;
}

.tactical-bg-layer {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
}

.main .block-container {
    position: relative;
    z-index: 1;
    padding-top: 0.8rem !important;
    padding-bottom: 1.5rem !important;
    max-width: 1400px !important;
}

#MainMenu, footer, header[data-testid="stHeader"] {
    background: transparent !important;
}

/* Persistent Header Bar */
.crisis-top-header {
    background: rgba(22, 31, 48, 0.9);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(245, 158, 11, 0.28);
    border-radius: 10px;
    padding: 10px 18px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.45);
}

.crisis-brand-group {
    display: flex;
    align-items: center;
    gap: 12px;
}

.crisis-badge-icon {
    width: 38px;
    height: 38px;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.25) 0%, rgba(239, 68, 68, 0.15) 100%);
    border: 1.5px solid #F59E0B;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
}

.crisis-title-main {
    margin: 0;
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 0.6px;
    color: #FFFFFF;
    text-transform: uppercase;
    line-height: 1.2;
}

.crisis-sub-title {
    margin: 2px 0 0 0;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.4px;
    color: #F59E0B;
    text-transform: uppercase;
}

.incident-status-pill {
    background: rgba(245, 158, 11, 0.12);
    border: 1.5px solid rgba(245, 158, 11, 0.6);
    border-radius: 9999px;
    padding: 6px 15px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.amber-indicator-dot {
    width: 10px;
    height: 10px;
    background-color: #F59E0B;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 8px #F59E0B;
    animation: pulseAmber 1.8s infinite ease-in-out;
}

@keyframes pulseAmber {
    0% { transform: scale(0.92); opacity: 0.85; }
    50% { transform: scale(1.18); opacity: 1; box-shadow: 0 0 12px #F59E0B; }
    100% { transform: scale(0.92); opacity: 0.85; }
}

.status-pill-text {
    font-size: 11.5px;
    font-weight: 600;
    color: #F8FAFC;
}

/* Persistent Breadcrumb Bar */
.breadcrumb-container {
    background: rgba(22, 31, 48, 0.85);
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.6px;
    height: 42px;
}

.bc-node {
    color: #94A3B8;
    text-transform: uppercase;
}

.bc-sep {
    color: #F59E0B;
    font-weight: 900;
}

.bc-active {
    color: #F59E0B;
    text-transform: uppercase;
}

.bc-tag {
    background: rgba(16, 185, 129, 0.2);
    color: #10B981;
    border: 1px solid #10B981;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 10px;
    margin-left: 6px;
}

/* 4 Clear Cards for Right Column */
.plan-card {
    background: rgba(22, 31, 48, 0.92);
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.25);
}

.plan-card-title {
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.plan-card-body {
    font-size: 12px;
    color: #CBD5E1;
    line-height: 1.42;
    margin: 0;
}

/* Standard Buttons */
.stButton > button {
    background: #F59E0B !important;
    color: #0B0F19 !important;
    font-weight: 800 !important;
    font-size: 13.5px !important;
    letter-spacing: 0.6px !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 16px !important;
    width: 100% !important;
    box-shadow: 0 4px 14px rgba(245, 158, 11, 0.35) !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    background: #D97706 !important;
    color: #000000 !important;
    transform: translateY(-1px) !important;
}

/* Primary Big Red Button (Used for Emergency Civic Submissions) */
button[kind="primary"] {
    background: #EF4444 !important;
    color: #FFFFFF !important;
    font-weight: 900 !important;
    font-size: 14.5px !important;
    letter-spacing: 0.8px !important;
    border: none !important;
    border-radius: 9px !important;
    padding: 12px 18px !important;
    width: 100% !important;
    box-shadow: 0 4px 18px rgba(239, 68, 68, 0.5) !important;
    transition: all 0.2s ease !important;
}

button[kind="primary"]:hover {
    background: #DC2626 !important;
    color: #FFFFFF !important;
    box-shadow: 0 6px 24px rgba(239, 68, 68, 0.7) !important;
    transform: translateY(-2px) !important;
}

/* Primary Selection Cards on 3-Card Main Hub */
.primary-card-wrapper {
    background: rgba(22, 31, 48, 0.88);
    backdrop-filter: blur(14px);
    border: 1.5px solid #334155;
    border-radius: 14px;
    padding: 20px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 10px 25px rgba(0,0,0,0.4);
    transition: all 0.25s ease;
}

.primary-card-wrapper:hover {
    border-color: #F59E0B;
    transform: translateY(-2px);
}

.pcard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.pcard-badge {
    padding: 3px 9px;
    border-radius: 99px;
    font-size: 10.5px;
    font-weight: 800;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}

.pcard-title {
    margin: 0 0 6px 0;
    font-size: 19px;
    font-weight: 800;
    color: #FFFFFF;
}

.pcard-desc {
    font-size: 12.5px;
    color: #94A3B8;
    line-height: 1.45;
    margin-bottom: 12px;
}

.pcard-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 14px;
}

.pcard-tag-pill {
    background: #0B0F19;
    border: 1px solid #334155;
    color: #CBD5E1;
    padding: 3px 7px;
    border-radius: 5px;
    font-size: 10.5px;
    font-weight: 700;
}

/* Citizen Triage Viewfinder */
.cctv-viewfinder {
    background: #05070D;
    border: 1.5px solid #334155;
    border-radius: 8px;
    padding: 12px;
    position: relative;
    margin-bottom: 12px;
}

.cctv-topbar {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    color: #10B981;
    margin-bottom: 10px;
}

.cctv-box {
    border: 2px dashed #F59E0B;
    background: rgba(245, 158, 11, 0.08);
    border-radius: 6px;
    padding: 16px;
    text-align: center;
}

.cctv-bbox-label {
    background: #F59E0B;
    color: #0B0F19;
    font-size: 10px;
    font-weight: 800;
    padding: 2px 6px;
    border-radius: 3px;
    display: inline-block;
    margin-bottom: 6px;
}

/* Compact Slider Adjustments */
div[data-testid="stSlider"],
div[data-testid="stSelectSlider"] {
    margin-top: -6px !important;
    margin-bottom: -4px !important;
}

div[data-testid="stSlider"] label,
div[data-testid="stSelectSlider"] label {
    font-size: 11.5px !important;
    font-weight: 700 !important;
    color: #CBD5E1 !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label {
    font-size: 11px !important;
    font-weight: 700 !important;
    color: #94A3B8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    margin-bottom: 2px !important;
}
</style>
"""

# Render Background & Global CSS
st.markdown(TACTICAL_BG_SVG, unsafe_allow_html=True)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# High-Contrast CSS: Prevent dark-on-black blending and enforce crisp readable typography
st.markdown("""
<style>
    /* Force all widget labels, radio text, and descriptions to crisp readable white/amber */
    .stRadio label, .stRadio div[role="radiogroup"] p, .stRadio span {
        color: #F8FAFC !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }
    .stSelectbox label, .stTextInput label, .stSlider label, .stSelectSlider label {
        color: #F59E0B !important; /* Amber headings */
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
    }
    /* Fix Select Slider tick labels (Off-Peak, Normal, Peak) */
    div[data-testid="stSliderTickBarMin"], 
    div[data-testid="stSliderTickBarMax"],
    div[data-testid="stTickBarItem"],
    div[data-testid="stSlider"] p,
    div[data-testid="stSliderTickBar"] span {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
    }
    /* Ensure input boxes have high contrast text inside */
    div[data-baseweb="select"] span, 
    div[data-baseweb="select"] div[role="button"],
    div[data-baseweb="select"] div[class*="ValueContainer"],
    div[data-baseweb="input"] input {
        color: #0F172A !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="select"] svg {
        fill: #0F172A !important;
        color: #0F172A !important;
    }
    /* High contrast input container backgrounds */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] {
        background-color: #F8FAFC !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 6px !important;
    }
    div[data-baseweb="popover"] ul li {
        color: #0F172A !important;
        background-color: #FFFFFF !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="popover"] ul li:hover {
        background-color: #E2E8F0 !important;
    }
    /* Alerts High Contrast */
    div[data-testid="stAlert"] div, div[data-testid="stAlert"] p {
        color: #F8FAFC !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    /* Solid Red Emergency Hazard Button */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%) !important;
        color: #FFFFFF !important;
        font-weight: 800 !important;
        border: 1px solid #B91C1C !important;
        box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4) !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #DC2626 0%, #B91C1C 100%) !important;
        border-color: #991B1B !important;
        box-shadow: 0 6px 18px rgba(239, 68, 68, 0.6) !important;
    }
    /* File uploader styling */
    div[data-testid="stFileUploader"] label {
        color: #F59E0B !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stFileUploader"] section {
        background-color: #161F30 !important;
        border: 1.5px dashed #475569 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stFileUploader"] section:hover {
        border-color: #F59E0B !important;
    }
    div[data-testid="stFileUploader"] span, div[data-testid="stFileUploader"] small {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Top Header Bar (Persistent Across All Views)
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="crisis-top-header">
        <div class="crisis-brand-group">
            <div class="crisis-badge-icon">🏛️</div>
            <div>
                <h1 class="crisis-title-main">SMART CITY PLANNING & SIMULATION ENGINE</h1>
                <p class="crisis-sub-title">BENGALURU CENTRAL CRISIS HUB (BELLANDUR / ORR)</p>
            </div>
        </div>
        <div class="incident-status-pill">
            <span class="amber-indicator-dot"></span>
            <span class="status-pill-text">Current Incident Level: <strong>ORANGE</strong> (High Traffic / Monsoon Overflow)</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# -----------------------------------------------------------------------------
# Helper: Lazy Init Engine Services
# -----------------------------------------------------------------------------
@st.cache_resource
def load_simulation_assets():
    data_dir = PROJECT_ROOT / "data" / "osm_graphs"
    loader = GraphLoader(data_dir)
    network = loader.load_network()
    buildings = loader.load_buildings()

    with open(PROJECT_ROOT / "config" / "settings.yaml", "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    penalizer = DynamicPenalizer()
    signals = AdaptiveSignalController()
    speed_detector = AnomalySpeedDetector()
    amb_router = AmbulanceRouter()
    evac_router = EvacuationRouter()

    vision = MockVisionDetector()
    disaster_pred = MockDisasterPredictor()
    fire_ca = MockFireSpreadCA()

    return {
        "loader": loader,
        "network": network,
        "buildings": buildings,
        "settings": settings,
        "penalizer": penalizer,
        "signals": signals,
        "speed_detector": speed_detector,
        "amb_router": amb_router,
        "evac_router": evac_router,
        "vision": vision,
        "disaster_pred": disaster_pred,
        "fire_ca": fire_ca
    }


# =============================================================================
# VIEW 0: DUAL-ACCESS LOGIN INTERFACE (When not authenticated)
# =============================================================================
if not st.session_state.logged_in:
    center_ratio = 2.4 if st.session_state.portal_tab == "CIVIC REPORTER" else 1.8
    pad_l, center_col, pad_r = st.columns([1, center_ratio, 1])
    with center_col:
        with st.container(border=True):
            st.markdown(
                """
                <div style="margin-bottom:14px;">
                    <span style="background:rgba(245,158,11,0.15); border:1px solid rgba(245,158,11,0.4); padding:3px 9px; border-radius:6px; font-size:10.5px; font-weight:700; color:#F59E0B; text-transform:uppercase;">
                        Sector 4 • Bellandur / ORR Crisis Node
                    </span>
                    <h2 style="margin:8px 0 2px 0; font-size:24px; font-weight:800; color:#FFFFFF;">Welcome back</h2>
                    <p style="margin:0; font-size:13px; color:#94A3B8;">Access the command center or submit field reports.</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            portal_mode = st.radio(
                "Access Mode",
                options=["OPERATIONS CONTROL", "CIVIC REPORTER"],
                index=0 if st.session_state.portal_tab == "OPERATIONS CONTROL" else 1,
                horizontal=True,
                label_visibility="collapsed",
                key="login_radio"
            )
            st.session_state.portal_tab = portal_mode

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

            # -------------------------------------------------------------
            # TAB 1: OPERATIONS CONTROL
            # -------------------------------------------------------------
            if portal_mode == "OPERATIONS CONTROL":
                force_id = st.text_input(
                    "Enter Municipal / Force ID",
                    value=st.session_state.user_id,
                    placeholder="e.g., BTP-8042"
                )

                col_p1, col_p2 = st.columns([0.84, 0.16])
                with col_p2:
                    show_p = st.checkbox("Show", key="chk_show_pass")
                with col_p1:
                    st.text_input(
                        "Access Passphrase",
                        value="••••••••••••" if not show_p else "BLR-SECTOR4-OVERRIDE",
                        type="default" if show_p else "password",
                        placeholder="Enter authorized passphrase"
                    )

                st.toggle("Secure OTP via Command Link", value=True)

                if st.button("AUTHORIZE & ENTER COMMAND", key="btn_login_auth"):
                    st.session_state.logged_in = True
                    st.session_state.user_id = force_id if force_id.strip() else "BTP-8042"
                    st.session_state.nav_view = "MONITORING"
                    st.rerun()

                st.markdown(
                    """
                    <div style="display:flex; justify-content:center; gap:14px; margin-top:16px; padding-top:12px; border-top:1px solid #334155; font-size:12px; color:#94A3B8;">
                        <span>Secure Access Help</span>
                        <span style="color:#475569;">|</span>
                        <span>Request ID Authorization</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # -------------------------------------------------------------
            # TAB 2: CIVIC REPORTER (Fully Embedded Mobile Reporting Interface)
            # -------------------------------------------------------------
            else:
                # 1. Header & Location Details
                st.markdown(
                    """
                    <div style="margin-bottom:12px;">
                        <h3 style="margin:4px 0 2px 0; color:#F8FAFC; font-size:20px; font-weight:800;">🚨 Report Emergency Hazard in 3 Taps</h3>
                        <p style="font-size:12.5px; color:#94A3B8; margin:0 0 10px 0; line-height:1.4;">
                            Fast-track road obstruction alert directly to Bengaluru Emergency Dispatch.
                        </p>
                        <div style="background:#0F172A; border:1px solid #334155; border-radius:6px; padding:8px 12px; display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:12px; font-weight:700; color:#38BDF8;">📍 GPS: 12.9262° N, 77.6765° E (Bellandur ORR - Ward 150)</span>
                            <span style="background:rgba(16,185,129,0.2); color:#10B981; border:1px solid #10B981; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:800;">AUTO-LOCKED</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # 2. Live Environmental Vital Signs Card
                col_rain, col_aqi, col_lake = st.columns(3)
                with col_rain:
                    st.markdown(
                        """
                        <div style="background:#161F30; border:1px solid #334155; border-radius:8px; padding:10px 8px; text-align:center;">
                            <div style="font-size:11px; font-weight:700; color:#94A3B8; text-transform:uppercase; margin-bottom:2px;">🌧️ Rainfall Intensity</div>
                            <div style="font-size:17px; font-weight:800; color:#38BDF8;">45.0 mm/hr</div>
                            <div style="font-size:10px; font-weight:600; color:#CBD5E1; margin-top:2px;">Monsoon Downpour Active</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                with col_aqi:
                    st.markdown(
                        """
                        <div style="background:#161F30; border:1px solid #334155; border-radius:8px; padding:10px 8px; text-align:center;">
                            <div style="font-size:11px; font-weight:700; color:#94A3B8; text-transform:uppercase; margin-bottom:2px;">💨 Air Quality (AQI)</div>
                            <div style="font-size:17px; font-weight:800; color:#F59E0B;">142 PM2.5</div>
                            <div style="font-size:10px; font-weight:600; color:#CBD5E1; margin-top:2px;">Moderate / Sensitive Alert</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                with col_lake:
                    st.markdown(
                        """
                        <div style="background:#161F30; border:1px solid #334155; border-radius:8px; padding:10px 8px; text-align:center;">
                            <div style="font-size:11px; font-weight:700; color:#94A3B8; text-transform:uppercase; margin-bottom:2px;">🌊 Bellandur Lake Level</div>
                            <div style="font-size:17px; font-weight:800; color:#EF4444;">92% Capacity</div>
                            <div style="font-size:10px; font-weight:600; color:#CBD5E1; margin-top:2px;">High Flood Overflow Risk</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

                # 3. Active Road Advisory Banner
                st.warning("⚠️ ACTIVE ROAD ADVISORY: Bellandur Underpass is closed due to 1.4m water accumulation. Use ORR Elevated Flyover for all bypass transit.")

                st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

                # 4. Interactive 3-Step Reporting Inputs
                # Step 1: Select Hazard Category
                st.markdown("<div style='font-size:12px; font-weight:700; color:#F59E0B; text-transform:uppercase; letter-spacing:0.5px; margin:8px 0 4px 0;'>Step 1: Select Hazard Category</div>", unsafe_allow_html=True)
                civic_cat = st.radio(
                    "Hazard Category",
                    options=[
                        "🌊 Flooded Road / Water Rising",
                        "🌳 Fallen Tree / Blocked Road",
                        "🕳️ Road Cave-In / Deep Pothole",
                        "⚡ Fire / Exposed Wire Hazard"
                    ],
                    index=0,
                    label_visibility="collapsed",
                    key="civic_hazard_category"
                )

                # Step 2: Upload Photo
                st.markdown("<div style='font-size:12px; font-weight:700; color:#F59E0B; text-transform:uppercase; letter-spacing:0.5px; margin:12px 0 4px 0;'>Step 2: Upload Photo</div>", unsafe_allow_html=True)
                uploaded_photo = st.file_uploader(
                    "Snap or Upload Hazard Photo (YOLOv8 Auto-Verification)",
                    type=['jpg', 'jpeg', 'png'],
                    key="civic_photo_uploader"
                )

                # Step 3: Road Passability Impact
                st.markdown("<div style='font-size:12px; font-weight:700; color:#F59E0B; text-transform:uppercase; letter-spacing:0.5px; margin:12px 0 4px 0;'>Step 3: Road Passability Impact</div>", unsafe_allow_html=True)
                civic_impact = st.radio(
                    "Road Passability Impact",
                    options=[
                        "🔴 Completely Blocked (Cars cannot pass)",
                        "🟡 Slow Moving (One lane open)",
                        "🟢 Minor Caution (Surface issue)"
                    ],
                    index=0,
                    label_visibility="collapsed",
                    key="civic_passability_impact"
                )

                # Step 4: Field Observation Details
                st.markdown("<div style='font-size:12px; font-weight:700; color:#F59E0B; text-transform:uppercase; letter-spacing:0.5px; margin:12px 0 4px 0;'>Step 4: Field Observation Details</div>", unsafe_allow_html=True)
                civic_notes = st.text_input(
                    "Observation Notes (Optional):",
                    placeholder="e.g., Water rising above car tires near Ecospace gate...",
                    key="civic_notes_input"
                )

                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

                # Primary Action Button
                if st.button("🚨 SUBMIT EMERGENCY HAZARD TICKET", type="primary", use_container_width=True, key="btn_submit_civic_ticket"):
                    st.session_state.ticket_status["1045"] = "PENDING"
                    st.session_state.civic_ticket_submitted = True
                    st.session_state.civic_submitted_data = {
                        "category": civic_cat,
                        "impact": civic_impact,
                        "desc": civic_notes if civic_notes.strip() else "Water rising above car tires near Ecospace gate; road impassable.",
                        "has_photo": uploaded_photo is not None
                    }
                    st.success("✓ Emergency Hazard Ticket #1045 Transmitted Live to BBMP Ward 150 Operations Command.")

                st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

                # 5. Emergency Helplines & Non-Emergency Handoff Footer
                st.info("📞 EMERGENCY CONTACTS: Police: 112 | Ambulance: 108 | Fire: 101 | BBMP Flood Control: 1533 / 1912")

                st.markdown(
                    """
                    <div style="background:#161F30; border:1px solid #334155; border-radius:8px; padding:12px 14px; margin:10px 0 12px 0; font-size:12px; color:#F8FAFC; line-height:1.5;">
                        <div style="font-weight:700; margin-bottom:5px; color:#F59E0B;">🏛️ Not an immediate life-safety disaster?</div>
                        <div style="color:#CBD5E1; margin-bottom:8px;">For uncollected waste, broken streetlights, or routine civic maintenance, please report through official government portals:</div>
                        <div style="display:flex; flex-direction:column; gap:5px; font-weight:600;">
                            <div>• <a href="https://bbmp.gov.in" target="_blank" style="color:#38BDF8; text-decoration:none;">BBMP Sahaaya 2.0 (bbmp.gov.in)</a></div>
                            <div>• <a href="https://swachhatah-mohua.gov.in" target="_blank" style="color:#10B981; text-decoration:none;">Swachhata-MoHUA Portal (swachhata.gov.in)</a></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button("← Return to Operations Control", use_container_width=True, key="btn_return_ops_tab"):
                    st.session_state.portal_tab = "OPERATIONS CONTROL"
                    st.rerun()


# =============================================================================
# AUTHENTICATED WORKSPACE
# =============================================================================
else:
    # -------------------------------------------------------------------------
    # 1. PERSISTENT TOP NAVIGATION & BREADCRUMBS
    # -------------------------------------------------------------------------
    col_bc_left, col_bc_right = st.columns([0.78, 0.22])

    with col_bc_left:
        # Build breadcrumb HTML based on active nav_view
        if st.session_state.nav_view == "MONITORING":
            bc_html = """
            <div class="breadcrumb-container">
                <span class="bc-active">MONITORING</span>
                <span class="bc-tag">MAIN 3-CARD HUB</span>
            </div>
            """
        elif st.session_state.nav_view == "DISASTER":
            bc_html = """
            <div class="breadcrumb-container">
                <span class="bc-node">MONITORING</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-active">DISASTER</span>
                <span class="bc-tag">SUB-SYSTEMS</span>
            </div>
            """
        elif st.session_state.nav_view == "DISASTER_FLOOD":
            bc_html = """
            <div class="breadcrumb-container">
                <span class="bc-node">MONITORING</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-node">DISASTER</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-node">FLOOD &amp; WATER</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-active">ANALYSIS</span>
                <span class="bc-tag">LIVE SIMULATION</span>
            </div>
            """
        elif st.session_state.nav_view == "DISASTER_FIRE":
            bc_html = """
            <div class="breadcrumb-container">
                <span class="bc-node">MONITORING</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-node">DISASTER</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-node">URBAN FIRE</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-active">ANALYSIS</span>
                <span class="bc-tag">LIVE SIMULATION</span>
            </div>
            """
        elif st.session_state.nav_view == "DISASTER_EARTHQUAKE":
            bc_html = """
            <div class="breadcrumb-container">
                <span class="bc-node">MONITORING</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-node">DISASTER</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-node">EARTHQUAKE</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-active">ANALYSIS</span>
                <span class="bc-tag">LIVE SIMULATION</span>
            </div>
            """
        elif st.session_state.nav_view == "TRAFFIC":
            bc_html = """
            <div class="breadcrumb-container">
                <span class="bc-node">MONITORING</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-active">TRAFFIC</span>
                <span class="bc-tag">CORRIDOR VELOCITY</span>
            </div>
            """
        elif st.session_state.nav_view == "CITIZEN_REPORT":
            bc_html = """
            <div class="breadcrumb-container">
                <span class="bc-node">MONITORING</span>
                <span class="bc-sep">&gt;</span>
                <span class="bc-active">CITIZEN REPORT</span>
                <span class="bc-tag">TRIAGE CONSOLE</span>
            </div>
            """
        else:
            bc_html = '<div class="breadcrumb-container"><span class="bc-active">MONITORING</span></div>'

        st.markdown(bc_html, unsafe_allow_html=True)

    with col_bc_right:
        # Clean button to safely reset back to 3-Card Hub (or Logout if already in Monitoring)
        if st.session_state.nav_view != "MONITORING":
            if st.button("← Back to Monitoring", key="btn_nav_back_mon_top"):
                st.session_state.nav_view = "MONITORING"
                st.rerun()
        else:
            if st.button("🔒 Lock Console", key="btn_nav_logout_top"):
                st.session_state.logged_in = False
                st.session_state.nav_view = "MONITORING"
                st.rerun()

    # Load shared map and model assets
    assets = load_simulation_assets()
    buildings = assets["buildings"]
    network = assets["network"]

    # =========================================================================
    # VIEW: MAIN 3-CARD MONITORING HUB (`MONITORING`)
    # =========================================================================
    if st.session_state.nav_view == "MONITORING":
        st.markdown(
            """
            <div style="margin: 4px 0 16px 0;">
                <h2 style="margin:0; font-size:21px; font-weight:800; color:#FFFFFF;">
                    MUNICIPAL OPERATIONS & CRISIS MONITORING HUB
                </h2>
                <p style="margin:3px 0 0 0; font-size:12.5px; color:#94A3B8;">
                    Outer Ring Road (ORR) - Bellandur Corridor. Select an operational domain below.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        c1, c2, c3 = st.columns(3)

        # Card 1: [1] DISASTER
        with c1:
            st.markdown(
                """
                <div class="primary-card-wrapper">
                    <div>
                        <div class="pcard-header">
                            <span class="pcard-badge" style="background:rgba(239,68,68,0.2); color:#EF4444; border:1px solid #EF4444;">
                                THREAT LEVEL: HIGH
                            </span>
                            <span style="font-size:24px;">🌪️</span>
                        </div>
                        <h3 class="pcard-title">[1] DISASTER</h3>
                        <p class="pcard-desc">
                            Multi-hazard early warning & spatial risk modeling for flood inundation, urban fire spread, and seismic damage zones.
                        </p>
                        <div class="pcard-tags">
                            <span class="pcard-tag-pill">Flood &amp; Water</span>
                            <span class="pcard-tag-pill">Fire Spread CA</span>
                            <span class="pcard-tag-pill">Earthquake Seismic</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Go to Disaster Dashboard", key="btn_main_goto_disaster"):
                st.session_state.nav_view = "DISASTER"
                st.rerun()

        # Card 2: [2] TRAFFIC
        with c2:
            st.markdown(
                """
                <div class="primary-card-wrapper">
                    <div>
                        <div class="pcard-header">
                            <span class="pcard-badge" style="background:rgba(245,158,11,0.2); color:#F59E0B; border:1px solid #F59E0B;">
                                CONGESTION DETECTED
                            </span>
                            <span style="font-size:24px;">🚦</span>
                        </div>
                        <h3 class="pcard-title">[2] TRAFFIC</h3>
                        <p class="pcard-desc">
                            Arterial network velocity tracking, sudden deadlock anomaly detection, and emergency ambulance green wave preemption.
                        </p>
                        <div class="pcard-tags">
                            <span class="pcard-tag-pill">Street Density</span>
                            <span class="pcard-tag-pill">Speed Drops (0 km/h)</span>
                            <span class="pcard-tag-pill">Emergency Green Corridors</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Go to Traffic Dashboard", key="btn_main_goto_traffic"):
                st.session_state.nav_view = "TRAFFIC"
                st.rerun()

        # Card 3: [3] CITIZEN REPORT
        with c3:
            pending_count = sum(1 for s in st.session_state.ticket_status.values() if s == "PENDING")
            st.markdown(
                f"""
                <div class="primary-card-wrapper">
                    <div>
                        <div class="pcard-header">
                            <span class="pcard-badge" style="background:rgba(16,185,129,0.2); color:#10B981; border:1px solid #10B981;">
                                {pending_count} TICKETS PENDING
                            </span>
                            <span style="font-size:24px;">📢</span>
                        </div>
                        <h3 class="pcard-title">[3] CITIZEN REPORT</h3>
                        <p class="pcard-desc">
                            Crowdsourced ground-truth telemetry, 3-tap mobile reporting, and field incident verification for municipal dispatch.
                        </p>
                        <div class="pcard-tags">
                            <span class="pcard-tag-pill">Road Obstacles</span>
                            <span class="pcard-tag-pill">Potholes</span>
                            <span class="pcard-tag-pill">Flooded Spots</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Go to Citizen Dashboard", key="btn_main_goto_citizen"):
                st.session_state.nav_view = "CITIZEN_REPORT"
                st.rerun()

    # =========================================================================
    # VIEW: DISASTER SUB-MENU (`MONITORING > DISASTER`)
    # =========================================================================
    elif st.session_state.nav_view == "DISASTER":
        st.markdown(
            """
            <div style="margin: 4px 0 16px 0;">
                <h2 style="margin:0; font-size:21px; font-weight:800; color:#FFFFFF;">
                    DISASTER MONITORING & EARLY WARNING SUB-SYSTEMS
                </h2>
                <p style="margin:3px 0 0 0; font-size:12.5px; color:#94A3B8;">
                    Select an incident vector to launch the standard 2-column spatial simulation and operational action plan.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        sub1, sub2, sub3 = st.columns(3)

        with sub1:
            st.markdown(
                """
                <div class="primary-card-wrapper" style="border-left: 4px solid #38BDF8;">
                    <div>
                        <div class="pcard-header">
                            <span class="pcard-badge" style="background:rgba(56,189,248,0.2); color:#38BDF8; border:1px solid #38BDF8;">
                                MONSOON INUNDATION
                            </span>
                            <span style="font-size:24px;">🌊</span>
                        </div>
                        <h3 class="pcard-title">Flood &amp; Water</h3>
                        <p class="pcard-desc">
                            Bellandur Underpass depression submerged under 1.2m stormwater runoff. Low-lying catchment breach and sump overflow.
                        </p>
                        <div class="pcard-tags">
                            <span class="pcard-tag-pill">Rainfall Runoff</span>
                            <span class="pcard-tag-pill">Underpass Blockage</span>
                            <span class="pcard-tag-pill">Sakra EMS Bypass</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Open Flood & Water Analysis", key="btn_goto_flood_analysis"):
                st.session_state.nav_view = "DISASTER_FLOOD"
                st.rerun()

        with sub2:
            st.markdown(
                """
                <div class="primary-card-wrapper" style="border-left: 4px solid #F97316;">
                    <div>
                        <div class="pcard-header">
                            <span class="pcard-badge" style="background:rgba(249,115,22,0.2); color:#F97316; border:1px solid #F97316;">
                                STRUCTURAL BLAZE
                            </span>
                            <span style="font-size:24px;">🔥</span>
                        </div>
                        <h3 class="pcard-title">Urban Fire</h3>
                        <p class="pcard-desc">
                            Dynamic multi-building thermal spread and Cellular Automata simulation across ORR corridor with dynamic building origin selection and thermal containment.
                        </p>
                        <div class="pcard-tags">
                            <span class="pcard-tag-pill">Any-Building Origin</span>
                            <span class="pcard-tag-pill">Thermal Catchment</span>
                            <span class="pcard-tag-pill">Tender Corridor</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Open Urban Fire Analysis", key="btn_goto_fire_analysis"):
                st.session_state.nav_view = "DISASTER_FIRE"
                st.rerun()

        with sub3:
            st.markdown(
                """
                <div class="primary-card-wrapper" style="border-left: 4px solid #A855F7;">
                    <div>
                        <div class="pcard-header">
                            <span class="pcard-badge" style="background:rgba(168,85,247,0.2); color:#A855F7; border:1px solid #A855F7;">
                                SEISMIC TREMOR
                            </span>
                            <span style="font-size:24px;">⚡</span>
                        </div>
                        <h3 class="pcard-title">Earthquake &amp; Seismic</h3>
                        <p class="pcard-desc">
                            5.4 Richter shear tremor with debris hazards along Devarabisanahalli ramps and pedestrian evacuation to open wetlands.
                        </p>
                        <div class="pcard-tags">
                            <span class="pcard-tag-pill">Debris Quarantine</span>
                            <span class="pcard-tag-pill">Flyover Integrity</span>
                            <span class="pcard-tag-pill">Kaikondrahalli Ground</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("Open Earthquake Analysis", key="btn_goto_earthquake_analysis"):
                st.session_state.nav_view = "DISASTER_EARTHQUAKE"
                st.rerun()

    # =========================================================================
    # VIEW: STANDARD 2-COLUMN SIMULATION MODES (FLOOD, FIRE, EARTHQUAKE, TRAFFIC)
    # =========================================================================
    elif st.session_state.nav_view in ["DISASTER_FLOOD", "DISASTER_FIRE", "DISASTER_EARTHQUAKE", "TRAFFIC"]:
        mode = st.session_state.nav_view
        action_key = (
            "flood" if mode == "DISASTER_FLOOD" else (
                "fire" if mode == "DISASTER_FIRE" else (
                    "earthquake" if mode == "DISASTER_EARTHQUAKE" else "traffic"
                )
            )
        )

        # Active telemetry & slider values (synchronized across reruns)
        current_rainfall_mm = float(st.session_state.get("flood_rainfall_slider", 55.0))
        current_wind_speed = float(st.session_state.get("fire_wind_slider", 24.0))
        current_quake_mag = float(st.session_state.get("earthquake_mag_slider", 5.4))

        # Resolve active fire origin building
        default_fire_bldg = "RMZ Ecoworld Tower 4A"
        if "fire_origin_building" not in st.session_state:
            st.session_state["fire_origin_building"] = default_fire_bldg
        active_fire_bldg = st.session_state["fire_origin_building"]

        col_map, col_actions = st.columns([65, 35])

        # -------------------------------------------------------------
        # RIGHT COLUMN (col_actions - 35% width): Human Ingestion Controls + 4 Cards
        # -------------------------------------------------------------
        with col_actions:
            # Mode Switcher at top of Section 1
            st.markdown("<div style='font-size:11px; font-weight:800; color:#F59E0B; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:2px;'>Incident Ingestion Mode:</div>", unsafe_allow_html=True)
            ingest_mode = st.radio(
                "Incident Ingestion Mode:",
                options=["🤖 AI Auto-Detect", "✍️ Manual Human Input"],
                index=0 if not st.session_state.get(f"is_manual_{action_key}", False) else 1,
                horizontal=True,
                label_visibility="collapsed",
                key=f"ingest_mode_radio_{action_key}"
            )
            st.session_state[f"is_manual_{action_key}"] = (ingest_mode == "✍️ Manual Human Input")

            # Check if Manual Human Input is selected
            if ingest_mode == "✍️ Manual Human Input":
                st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

                if action_key == "fire":
                    # Dynamic Origin Dropdown for Urban Fire Module
                    active_corridor_bldgs = [
                        f["properties"]["name"] for f in buildings.get("features", [])
                        if f.get("properties", {}).get("name") in CORRIDOR_FIRE_BUILDINGS
                    ]
                    for b in CORRIDOR_FIRE_BUILDINGS:
                        if b not in active_corridor_bldgs:
                            active_corridor_bldgs.append(b)

                    def_bldg_idx = active_corridor_bldgs.index(active_fire_bldg) if active_fire_bldg in active_corridor_bldgs else 0

                    selected_fire_origin_building = st.selectbox(
                        "SELECT FIRE ORIGIN BUILDING:",
                        options=active_corridor_bldgs,
                        index=def_bldg_idx,
                        key="h_fire_origin_building_select"
                    )
                    active_fire_bldg = selected_fire_origin_building
                    st.session_state["fire_origin_building"] = active_fire_bldg
                    human_target = active_fire_bldg
                else:
                    target_options = [
                        "Bellandur Underpass",
                        "Ecospace Gate 2",
                        "Devarabisanahalli Flyover Ramp",
                        "Iblur / Sarjapur Junction Exit"
                    ]
                    default_target_idx = 0
                    if action_key == "flood":
                        default_target_idx = 0
                    elif action_key == "earthquake":
                        default_target_idx = 2
                    elif action_key == "traffic":
                        default_target_idx = 3

                    human_target = st.selectbox(
                        "Select Target Road Segment:",
                        options=target_options,
                        index=default_target_idx,
                        key=f"h_target_{action_key}"
                    )

                hazard_options = list(CONTEXTUAL_HAZARDS.get(action_key, [
                    "🌊 Waterlogging / Lake Overflow",
                    "🌳 Fallen Tree / Debris Obstacle",
                    "🚧 Road Cave-In / Tanker Breakdown",
                    "🔥 Fire / Toxic Smoke Drift"
                ]))
                if "⚠️ Other / Custom Hazard" not in hazard_options:
                    hazard_options.append("⚠️ Other / Custom Hazard")

                human_hazard = st.selectbox(
                    "Select Hazard Type:",
                    options=hazard_options,
                    index=0,
                    key=f"h_hazard_{action_key}"
                )

                # Dynamic text input when Other / Custom Hazard is selected
                if human_hazard == "⚠️ Other / Custom Hazard":
                    custom_hazard_name = st.text_input(
                        "Specify Custom Hazard Name:",
                        placeholder="e.g., Chemical spill, overturned truck, etc.",
                        key=f"custom_hazard_name_{action_key}"
                    )
                    effective_hazard = (
                        custom_hazard_name.strip()
                        if custom_hazard_name and custom_hazard_name.strip()
                        else "Other / Custom Hazard"
                    )
                else:
                    effective_hazard = human_hazard

                human_sev = st.selectbox(
                    "Select Road Impact:",
                    options=["🔴 Critical (100% Closed - Full Diversion)", "🟡 Moderate (50% Blocked - Speed Halved)", "🟢 Minor (Caution Warning)"],
                    key=f"h_sev_{action_key}"
                )
                human_density = st.select_slider(
                    "Corridor Traffic Inflow:",
                    options=["🟢 Off-Peak (Late Night)", "🟡 Normal Midday", "🔴 Peak Monsoon Rush Hour"],
                    value="🔴 Peak Monsoon Rush Hour",
                    key=f"h_density_{action_key}"
                )
                human_note = st.text_input(
                    "Custom Operator Note:",
                    value="Heavy disruption reported by field unit; access lanes impassable.",
                    key=f"h_note_{action_key}"
                )

                # Spatial Adjacency and Spread Physics
                nearest_bldg_name, nearest_bldg_c, fire_origin_c = find_nearest_adjacent_building(
                    active_fire_bldg, buildings
                )
                is_fire_critical = "Critical" in human_sev if action_key == "fire" else False
                secondary_spread_active = (mode == "DISASTER_FIRE") and (current_wind_speed > 35.0 or is_fire_critical)
                secondary_spread_bldg = nearest_bldg_name if (secondary_spread_active and nearest_bldg_name) else ""

                if action_key == "fire":
                    c1_title = "1. WHAT IS THE PROBLEM? (MANUAL FIRE OVERRIDE)"
                    spread_note = (
                        f" Downwind thermal spread threat active toward <b>{secondary_spread_bldg}</b> ({current_wind_speed:.0f} km/h wind)."
                        if secondary_spread_active and secondary_spread_bldg
                        else f" Prevailing wind ({current_wind_speed:.0f} km/h) below 35 km/h spread threshold."
                    )
                    c1_text = f"Field operator logged <b>{effective_hazard}</b> at primary origin <b>{active_fire_bldg}</b> ({human_sev}).{spread_note} Note: '{human_note}'."
                    c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                    c2_text = f"Unmitigated blaze at {active_fire_bldg} will breach structural firewalls within 14 minutes, trapping occupants and releasing toxic smoke onto Outer Ring Road expressway."
                    c3_title = "3. HISTORICAL RESOLUTION BACKING"
                    c3_text = "Grounded in Karnataka State Fire & Emergency Services Standard Operating Protocol: Enforcing immediate 300m containment perimeter and dedicated tender corridor reduces commercial losses by 74%."
                    c4_title = "4. AI PRESCRIBED SOLUTION"
                    c4_text = f"1. Invalidate access lanes to {active_fire_bldg} (Thermal Exclusion Zone).<br/>2. Clear dedicated Fire-Tender Rapid Corridor from Sarjapur Base to scene.<br/>3. Recompute dynamic EMS evacuation route avoiding thermal hazard via NetworkX."
                    btn_label = f"APPLY & RUN FIRE ACTION PLAN ({active_fire_bldg.upper()})"
                else:
                    c1_title = "1. WHAT IS THE PROBLEM? (HUMAN OVERRIDE)"
                    c1_text = f"Field operator logged <b>{effective_hazard}</b> at <b>{human_target}</b>. Status marked as <b>{human_sev}</b> during {human_density}. Note: '{human_note}'."
                    c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                    c2_text = f"Unmitigated disruption at {human_target} will halt arterial circulation across Sector 4. Traffic queues will cascade into Outer Ring Road mainline, blocking emergency responders and amplifying life-safety risks."
                    c3_title = "3. HISTORICAL RESOLUTION BACKING"
                    c3_text = "Grounded in Bengaluru Traffic Police & BBMP Disaster Incident Registry: Enforcing immediate road-edge invalidation and dynamic bypass metering mitigates secondary bottleneck delays by 68% across ORR corridors."
                    c4_title = "4. AI PRESCRIBED SOLUTION"
                    c4_text = f"1. Invalidate road segment '{human_target}' on GIS network due to {effective_hazard} and establish dynamic emergency bypass.<br/>2. Force signal preemption along adjacent arterial spines.<br/>3. Dispatch BBMP Ward 150 incident response squad based on field note: '{human_note}'."
                    btn_label = f"APPLY & RUN ACTION PLAN ({human_target.upper()})"

            else:
                # 🤖 AI Auto-Detect Defaults
                # Secondary spread logic: active if wind > 35 km/h or Fire Severity is Critical
                nearest_bldg_name, nearest_bldg_c, fire_origin_c = find_nearest_adjacent_building(
                    active_fire_bldg, buildings
                )
                is_fire_critical = False
                secondary_spread_active = (mode == "DISASTER_FIRE") and (current_wind_speed > 35.0 or is_fire_critical)
                secondary_spread_bldg = nearest_bldg_name if (secondary_spread_active and nearest_bldg_name) else ""

                if mode == "DISASTER_FLOOD":
                    c1_title = "1. WHAT IS THE PROBLEM?"
                    c1_text = "Automated sensor CAM-04 detected stormwater pooling exceeding 1.2m at Bellandur Underpass following a 55 mm/hr cloudburst. Low-elevation service road is completely submerged and impassable for ambulances and passenger traffic."

                    c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                    c2_text = "Outer Ring Road arterial will sever completely. Ambulance transit to Sakra Trauma Hub faces +45 minute delays, causing life-safety risks. Stalled vehicles will trigger a 9 km gridlock spanning Silk Board to Marathahalli with severe drowning hazards."

                    c3_title = "3. HISTORICAL RESOLUTION BACKING"
                    c3_text = "Grounded in BBMP Monsoon Audit (Sept 2022 Bellandur & Rainbow Drive Inundation): immediate deployment of heavy diesel dewatering sumps combined with elevated flyover diversion restored emergency ambulance flow within 18 minutes."

                    c4_title = "4. AI PRESCRIBED SOLUTION"
                    c4_text = "1. Invalidate Bellandur Underpass link and reroute EMS via Elevated Flyover Bypass.<br/>2. Force 120s green wave priority along Sarjapur-Ecospace corridor.<br/>3. Dispatch Ward 150 mobile dewatering pump and open Sump 4 discharge."

                    btn_label = "APPLY & RUN FLOOD ACTION PLAN"

                elif mode == "DISASTER_FIRE":
                    c1_title = "1. WHAT IS THE PROBLEM?"
                    spread_str = (
                        f"High wind gusts ({current_wind_speed:.0f} km/h NE) are driving rapid cellular fire propagation toward {secondary_spread_bldg}."
                        if secondary_spread_active and secondary_spread_bldg
                        else f"Prevailing wind ({current_wind_speed:.0f} km/h NE) is currently below critical spread threshold (35 km/h)."
                    )
                    c1_text = (
                        f"Thermal infrared sensor FIR-02 detected a structural blaze at <b>{active_fire_bldg}</b>. "
                        f"{spread_str} Immediate structural isolation enforced."
                    )

                    c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                    c2_text = (
                        f"Flames will breach structural firewalls at {active_fire_bldg} within 14 minutes, endangering building occupants. "
                        f"Dense toxic smoke will descend onto ORR expressway, blinding motorists and triggering secondary high-speed pileups."
                    )

                    c3_title = "3. HISTORICAL RESOLUTION BACKING"
                    c3_text = "Grounded in Karnataka State Fire & Emergency Services Standard Operating Protocol (2020 Commercial SEZ Safety Directive): Establishing a 300m containment perimeter and dedicated tender corridor reduces commercial losses by 74%."

                    c4_title = "4. AI PRESCRIBED SOLUTION"
                    c4_text = (
                        f"1. Invalidate access lanes to {active_fire_bldg} (Thermal Exclusion Zone).<br/>"
                        f"2. Clear dedicated Fire-Tender Rapid Corridor from Sarjapur Base to scene.<br/>"
                        f"3. Recompute dynamic EMS evacuation route avoiding thermal hazard via NetworkX."
                    )

                    btn_label = f"APPLY & RUN FIRE ACTION PLAN ({active_fire_bldg.upper()})"

                elif mode == "DISASTER_EARTHQUAKE":
                    if current_quake_mag < 3.5:
                        c1_title = "1. WHAT IS THE PROBLEM? (MINOR TREMOR)"
                        c1_text = (
                            f"Seismological station BLR-SEIS-04 recorded a minor {current_quake_mag:.1f} Richter tremor (Depth 10 km). "
                            "Structural strain telemetry across Bellandur corridor reports 0% damage; all flyover spans and road arteries remain fully stable."
                        )
                        c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                        c2_text = "Routine acoustic telemetry watch. Low risk of aftershock escalation. Normal arterial circulation maintained."
                        c3_title = "3. HISTORICAL RESOLUTION BACKING"
                        c3_text = "Grounded in NDMA Urban Earthquake Risk Mitigation Framework: Baseline strain monitoring without disruptive road invalidations prevents unneeded commercial panic."
                        c4_title = "4. AI PRESCRIBED SOLUTION"
                        c4_text = (
                            "1. Maintain structural acoustic health sensors in passive watch.<br/>"
                            "2. Keep arterial corridors open to civilian and commercial traffic.<br/>"
                            "3. Verify baseline strain readings with KSRSAC telemetry."
                        )
                        btn_label = "MAINTAIN PASSIVE SEISMIC SURVEILLANCE"
                    elif 3.5 <= current_quake_mag < 6.0:
                        c1_title = "1. WHAT IS THE PROBLEM? (MODERATE SHOCK)"
                        c1_text = (
                            f"Seismological station BLR-SEIS-04 recorded a {current_quake_mag:.1f} Richter tremor along the South-East fault (Depth 10 km). "
                            "Structural strain sensors indicate micro-cracks and masonry debris spalling along Devarabisanahalli Flyover ramps."
                        )
                        c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                        c2_text = "Secondary structural collapse during aftershocks could crush vehicles below. Unmanaged civilian panic will bottleneck office egress gates, creating stampede risks and trapping emergency first responders."
                        c3_title = "3. HISTORICAL RESOLUTION BACKING"
                        c3_text = "Grounded in NDMA Urban Earthquake Risk Mitigation Framework and Bengaluru Disaster Management Authority Guidelines: Immediate structural quarantine of elevated ramps and guiding civilians to low-density open wetlands prevents 90% of casualties."
                        c4_title = "4. AI PRESCRIBED SOLUTION"
                        c4_text = (
                            "1. Close Devarabisanahalli Flyover ramps to heavy commercial freight; divert to at-grade lanes.<br/>"
                            "2. Dispatch KSRSAC and BBMP structural engineering acoustic sensor teams.<br/>"
                            "3. Engage dynamic green wave bypass around quarantined flyover ramp."
                        )
                        btn_label = "APPLY & RUN MODERATE SEISMIC BYPASS"
                    else:
                        c1_title = "1. WHAT IS THE PROBLEM? (SEVERE COLLAPSE)"
                        c1_text = (
                            f"CRITICAL SEISMIC EMERGENCY: Severe {current_quake_mag:.1f} Richter earthquake detected along South-East fault line (Depth 10 km). "
                            "Structural collapse confirmed along fault corridor, severing flyover spans and multiple arterial access lanes."
                        )
                        c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                        c2_text = "Cascading structural collapse of weakened commercial towers and flyover spans will trap thousands. Arterial roads are blocked by masonry rubble, completely isolating inner tech parks."
                        c3_title = "3. HISTORICAL RESOLUTION BACKING"
                        c3_text = "Grounded in NDMA Urban Earthquake Risk Mitigation Framework: Full structural quarantine of damaged spans and rerouting evacuation to low-density perimeter residential corridors prevents catastrophic crush casualties."
                        c4_title = "4. AI PRESCRIBED SOLUTION"
                        c4_text = (
                            "1. Quarantine all elevated corridors and seal multiple collapsed arterial segments.<br/>"
                            "2. Fall back to perimeter residential bypass corridors toward Kaikondrahalli Lake Open Grounds.<br/>"
                            "3. Mobilize NDRF / SDRF heavy urban search and rescue teams."
                        )
                        btn_label = "ENGAGE RESIDENTIAL PERIMETER EVACUATION"

                else: # TRAFFIC
                    c1_title = "1. WHAT IS THE PROBLEM?"
                    c1_text = "Arterial velocity collapsed from 42 km/h to 0.0 km/h at Bellandur bottleneck, creating a 3.2 km queue spanning backward to Iblur junction."

                    c2_title = "2. WHAT HAPPENS WITH NO ACTION?"
                    c2_text = "Gridlock will cascade into Silk Board and Sarjapur feeder roads within 15 minutes, trapping 18,000 commuters and halting BBMP emergency ambulances."

                    c3_title = "3. HISTORICAL RESOLUTION BACKING"
                    c3_text = "Grounded in BTP Adaptive Corridor Playbook: Dynamic signal split reallocation and elevated flyover metering relieves Bellandur bottleneck queues by 40%."

                    c4_title = "4. AI PRESCRIBED SOLUTION"
                    c4_text = "1. Force 120s Green Wave along primary arterial spine.<br/>2. Meter entry ramps at Iblur and Devarabisanahalli service roads.<br/>3. Dispatch BTP motorcycle flying squad to clear stalled vehicles."

                    btn_label = "ENGAGE TRAFFIC GREEN WAVE & METERING"

            # Render 4 Plain-English Cards
            st.markdown(
                f"""
                <div class="plan-card" style="border-left: 4px solid #EF4444;">
                    <div class="plan-card-title" style="color:#EF4444;">
                        <span>🚨</span> {c1_title}
                    </div>
                    <p class="plan-card-text">{c1_text}</p>
                </div>

                <div class="plan-card" style="border-left: 4px solid #F59E0B;">
                    <div class="plan-card-title" style="color:#F59E0B;">
                        <span>⚠️</span> {c2_title}
                    </div>
                    <p class="plan-card-text">{c2_text}</p>
                </div>

                <div class="plan-card" style="border-left: 4px solid #38BDF8;">
                    <div class="plan-card-title" style="color:#38BDF8;">
                        <span>📜</span> {c3_title}
                    </div>
                    <p class="plan-card-text">{c3_text}</p>
                </div>

                <div class="plan-card" style="border-left: 4px solid #10B981;">
                    <div class="plan-card-title" style="color:#10B981;">
                        <span>🎯</span> {c4_title}
                    </div>
                    <p class="plan-card-text">{c4_text}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Primary Action Button
            if st.button(f"🚀 {btn_label}", key=f"btn_apply_plan_{action_key}"):
                st.session_state.plan_executed[action_key] = True
                if ingest_mode == "✍️ Manual Human Input":
                    st.session_state[f"applied_manual_{action_key}"] = True
                    st.session_state[f"applied_target_{action_key}"] = human_target
                    st.session_state[f"applied_severity_{action_key}"] = human_sev
                    st.session_state[f"applied_hazard_{action_key}"] = effective_hazard
                else:
                    st.session_state[f"applied_manual_{action_key}"] = False

            # Dynamic Green Corridor Calculation via Simulation Engine Backend
            routing_graph = load_graph()
            if routing_graph:
                reset_graph_weights(routing_graph)

            hazard_coords_map = {
                "Bellandur Underpass": (12.9262, 77.6765),
                "Ecospace Gate 2": (12.9250, 77.6842),
                "Devarabisanahalli Flyover Ramp": (12.9305, 77.6905),
                "Iblur / Sarjapur Junction Exit": (12.9208, 77.6655)
            }
            if ingest_mode == "✍️ Manual Human Input":
                if action_key == "fire":
                    h_pos = (fire_origin_c[1], fire_origin_c[0]) if fire_origin_c else (12.9229, 77.6878)
                else:
                    h_pos = hazard_coords_map.get(human_target, (12.9262, 77.6765))
            else:
                default_mode_map = {
                    "DISASTER_FLOOD": (12.9262, 77.6765),
                    "DISASTER_FIRE": (fire_origin_c[1], fire_origin_c[0]) if fire_origin_c else (12.9229, 77.6878),
                    "DISASTER_EARTHQUAKE": (12.9305, 77.6905),
                    "TRAFFIC": (12.9208, 77.6655)
                }
                h_pos = default_mode_map.get(mode, (12.9262, 77.6765))

            # ---------------------------------------------------------------
            # Backend Engine: Invalidate edges based on Disaster Physics
            # ---------------------------------------------------------------
            if mode == "DISASTER_FLOOD":
                if current_rainfall_mm >= 30.0:
                    for _u, _v, _k, _edata in (routing_graph.edges(keys=True, data=True) if routing_graph else []):
                        _ename = str(_edata.get("name", "")).lower()
                        _eid   = str(_edata.get("id",   "")).lower()
                        if "underpass" in _ename or "underpass" in _eid:
                            _edata["weight"]     = float("inf")
                            _edata["is_blocked"] = True
                invalidate_hazard_edges(routing_graph, h_pos, radius_meters=280.0)

            elif mode == "DISASTER_FIRE":
                # Thermal Exclusion Zone: Sever immediately adjacent access lanes in NetworkX
                invalidate_hazard_edges(routing_graph, h_pos, radius_meters=300.0)
                if secondary_spread_active and nearest_bldg_c:
                    invalidate_hazard_edges(routing_graph, (nearest_bldg_c[1], nearest_bldg_c[0]), radius_meters=250.0)

            elif mode == "DISASTER_EARTHQUAKE":
                if current_quake_mag < 3.5:
                    # Minor: 0% structural damage, all roads open
                    pass
                elif 3.5 <= current_quake_mag < 6.0:
                    # Moderate: Masonry debris closures along Devarabisanahalli Flyover Ramp
                    invalidate_hazard_edges(routing_graph, (12.9305, 77.6905), radius_meters=280.0)
                else:
                    # Severe (M >= 6.0): Multiple road segments blocked by structural rubble
                    invalidate_hazard_edges(routing_graph, (12.9305, 77.6905), radius_meters=350.0)
                    invalidate_hazard_edges(routing_graph, (12.9262, 77.6765), radius_meters=350.0)
                    for _u, _v, _k, _edata in (routing_graph.edges(keys=True, data=True) if routing_graph else []):
                        _ename = str(_edata.get("name", "")).lower()
                        _eid   = str(_edata.get("id",   "")).lower()
                        if "underpass" in _ename or "underpass" in _eid or "flyover" in _ename:
                            _edata["weight"]     = float("inf")
                            _edata["is_blocked"] = True

            else:  # TRAFFIC
                invalidate_hazard_edges(routing_graph, h_pos, radius_meters=280.0)

            # Run Dijkstra / A* to compute safest EMS green corridor
            green_corridor = compute_green_corridor(
                routing_graph,
                start_coords=START_COORDS,
                target_coords=PRIMARY_TARGET
            )

            # Severe earthquake fallback to perimeter residential bypass corridors
            if mode == "DISASTER_EARTHQUAKE" and current_quake_mag >= 6.0:
                green_corridor["waypoints"] = [
                    [77.6710, 12.9235],
                    [77.6700, 12.9230],
                    [77.6685, 12.9222],
                    [77.6672, 12.9215],
                    [77.6655, 12.9208],
                    [77.6665, 12.9195],
                    [77.6675, 12.9182],
                    [77.6685, 12.9175],
                    [77.6700, 12.9162],
                    [77.6710, 12.9153],
                    [77.6720, 12.9150],
                    [77.6740, 12.9135],
                    [77.6740, 12.9125]
                ]
                green_corridor["path_coords"] = green_corridor["waypoints"]
                green_corridor["hospital_name"] = "Kaikondrahalli Lake Grounds (Perimeter Assembly Hub)"
                green_corridor["route_status"] = "PERIMETER RESIDENTIAL CORRIDOR (COLLAPSE QUARANTINE)"
                green_corridor["is_rerouted"] = True

            if st.session_state.plan_executed.get(action_key, False):
                if st.session_state.get(f"applied_manual_{action_key}", False):
                    target_disp = st.session_state.get(f"applied_target_{action_key}", "Bellandur Underpass")
                    sev_disp = st.session_state.get(f"applied_severity_{action_key}", "Critical")
                    hazard_disp = st.session_state.get(f"applied_hazard_{action_key}", effective_hazard)
                    st.markdown(
                        f"""
                        <div style="background:rgba(16,185,129,0.18); border:1px solid #10B981; border-radius:6px; padding:8px 12px; margin-top:8px; font-size:12px; color:#10B981; font-weight:700;">
                            ✓ MANUAL OVERRIDE ACTIVE: {hazard_disp} at '{target_disp}' marked {sev_disp}.<br/>
                            🚑 GREEN CORRIDOR: {green_corridor['hospital_name']} (ETA: {green_corridor['eta_minutes']} min | {green_corridor['total_distance_km']} km).
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"""
                        <div style="background:rgba(16,185,129,0.18); border:1px solid #10B981; border-radius:6px; padding:8px 12px; margin-top:8px; font-size:12px; color:#10B981; font-weight:700;">
                            ✓ AI ACTION PLAN ACTIVE: Directives live on Municipal Dispatch.<br/>
                            🚑 GREEN CORRIDOR: {green_corridor['hospital_name']} (ETA: {green_corridor['eta_minutes']} min | {green_corridor['total_distance_km']} km).
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        # -------------------------------------------------------------
        # LEFT COLUMN (col_map - 65% width): PyDeck Map + Compact Slider
        # -------------------------------------------------------------
        with col_map:
            layers = []

            # ─────────────────────────────────────────────────────────────
            # LAYER 0a — Satellite Imagery Basemap (ESRI World Imagery)
            # High-resolution satellite raster tiles fetched directly by the browser.
            # Zero token required — ESRI ArcGIS Online tiles are openly accessible.
            # ─────────────────────────────────────────────────────────────
            layers.append(pdk.Layer(
                "TileLayer",
                id="satellite-basemap",
                data="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                min_zoom=0,
                max_zoom=19,
                tile_size=256,
                opacity=1.0,
                coordinate_system=pdk.CoordinateSystem.LNGLAT,
            ))

            # ─────────────────────────────────────────────────────────────
            # LAYER 0b — Road Labels & Place Names Overlay (ESRI World Boundaries)
            # Semi-transparent overlay with street names and administrative labels
            # ─────────────────────────────────────────────────────────────
            layers.append(pdk.Layer(
                "TileLayer",
                id="road-labels-overlay",
                data="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
                min_zoom=0,
                max_zoom=19,
                tile_size=256,
                opacity=0.85,
                coordinate_system=pdk.CoordinateSystem.LNGLAT,
            ))

            # ─────────────────────────────────────────────────────────────
            # LAYER 0c — Dense Road Skeleton Overlay (Real curved geometries)
            # ─────────────────────────────────────────────────────────────
            dense_net_file = PROJECT_ROOT / "data" / "bellandur_dense_network.json"
            if not dense_net_file.exists():
                dense_net_file = PROJECT_ROOT / "data" / "osm_graphs" / "bengaluru_bellandur_network.json"
            dense_net_raw = {}
            if dense_net_file.exists():
                try:
                    import json as _json
                    with open(dense_net_file, "r", encoding="utf-8") as _dfh:
                        dense_net_raw = _json.load(_dfh)
                except Exception:
                    pass

            road_skeleton_paths = []
            for _edge in dense_net_raw.get("edges", []):
                _coords = _edge.get("coordinates") or _edge.get("path_coords", [])
                if len(_coords) >= 2:
                    _rn = _edge.get("name", "Road")
                    _name_str = " ".join(str(x) for x in _rn) if isinstance(_rn, list) else str(_rn or "Road")
                    _nl = _name_str.lower()
                    road_skeleton_paths.append({
                        "name": _name_str,
                        "path": _coords,
                        "color": (
                            [239, 68, 68, 200] if _edge.get("is_blocked") else
                            [251, 191, 36, 190] if _edge.get("vulnerable_to_flood") else
                            [56, 189, 248, 200] if ("flyover" in _nl or "elevated" in _nl) else
                            [100, 116, 139, 180]
                        ),
                        "width": 6 if _edge.get("is_blocked") else 3,
                    })

            if road_skeleton_paths:
                layers.append(pdk.Layer(
                    "PathLayer",
                    road_skeleton_paths,
                    id="road-skeleton",
                    get_path="path",
                    get_color="color",
                    get_width="width",
                    width_min_pixels=1,
                    width_max_pixels=7,
                    pickable=False,
                    rounded=True,
                ))

            # ─────────────────────────────────────────────────────────────
            # LAYER 1 — 3D Extruded Buildings
            # Hospital differentiation: Sakra World Hospital uses Emergency
            # Purple/Violet [168, 85, 247, 230] — NOT red (red = blocked road).
            # Emergency services → Emerald.
            # Urban Fire: Origin deep flaming crimson [239,68,68,240], secondary spread amber-orange [249,115,22,220],
            #             non-affected towers operational cyan/slate [30,41,59,180].
            # Earthquake: M < 3.5 stable cyan; 3.5 <= M < 6.0 masonry warning; M >= 6.0 deep collapse-red [220,38,38,240].
            # ─────────────────────────────────────────────────────────────
            bldg_data = []
            for feat in buildings.get("features", []):
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if coords:
                    b_type  = props.get("type", "commercial_office")
                    b_name  = props.get("name", "")
                    b_name_lower = b_name.lower()

                    # Guardrail: Sakra World Hospital (Critical Medical Node) is ALWAYS Emergency Purple
                    if b_type == "hospital" or "hospital" in b_name_lower or "sakra" in b_name_lower:
                        color     = [168, 85, 247, 230]
                        line_clr  = [216, 180, 254, 255]
                    elif b_type == "emergency_service":
                        color     = [16, 185, 129, 220]
                        line_clr  = [52, 211, 153, 200]
                    elif mode == "DISASTER_FIRE":
                        if b_name == active_fire_bldg:
                            # Primary fire origin building: deep flaming crimson with active pulsing amber boundary
                            color     = [239, 68, 68, 240]
                            line_clr  = [251, 146, 60, 255]
                        elif secondary_spread_active and b_name == secondary_spread_bldg:
                            # Secondary spread logic: amber-orange to simulate fire spreading downwind
                            color     = [249, 115, 22, 220]
                            line_clr  = [251, 146, 60, 255]
                        else:
                            # Non-affected tech towers: operational cyan/slate [30, 41, 59, 180]
                            color     = [30, 41, 59, 180]
                            line_clr  = [51, 65, 85, 255]
                    elif mode == "DISASTER_EARTHQUAKE":
                        if current_quake_mag < 3.5:
                            # Minor (M < 3.5): 0% structural damage, all buildings stable cyan
                            color     = [56, 189, 248, 180]
                            line_clr  = [125, 211, 252, 200]
                        elif 3.5 <= current_quake_mag < 6.0:
                            # Moderate (3.5 <= M < 6.0): Masonry crack warnings on medium/high risk
                            if props.get("structural_risk") in ["high", "medium"]:
                                color     = [245, 158, 11, 210]
                                line_clr  = [251, 191, 36, 255]
                            else:
                                color     = [56, 189, 248, 180]
                                line_clr  = [125, 211, 252, 160]
                        else:
                            # Severe (M >= 6.0): Buildings along fault line turn deep collapse-red [220, 38, 38, 240]
                            color     = [220, 38, 38, 240]
                            line_clr  = [239, 68, 68, 255]
                    else:
                        if b_type == "residential":
                            color     = [100, 116, 139, 200]
                            line_clr  = [148, 163, 184, 140]
                        else:
                            color     = [56, 189, 248, 180]
                            line_clr  = [125, 211, 252, 160]

                    bldg_data.append({
                        "name":       b_name,
                        "height":     props.get("height", 30.0) * 1.5,
                        "color":      color,
                        "line_color": line_clr,
                        "polygon":    coords[0]
                    })

            layers.append(pdk.Layer(
                "PolygonLayer",
                bldg_data,
                id="3d-buildings",
                get_polygon="polygon",
                get_elevation="height",
                get_fill_color="color",
                get_line_color="line_color",
                line_width_min_pixels=1,
                extruded=True,
                pickable=True
            ))

            # Check if Manual Human Override is active for this mode
            is_manual_active = (
                st.session_state.plan_executed.get(action_key, False) and
                st.session_state.get(f"applied_manual_{action_key}", False)
            )

            if is_manual_active:
                # Dynamic Map Layer Calculation based on Human Input
                target_name = st.session_state.get(f"applied_target_{action_key}", "Bellandur Underpass")
                sev_name = st.session_state.get(f"applied_severity_{action_key}", "Critical")
                target_info = TARGET_ROAD_SEGMENTS.get(target_name, TARGET_ROAD_SEGMENTS["Bellandur Underpass"])

                # Determine color based on human-selected severity
                if "Critical" in sev_name:
                    block_color = [239, 68, 68, 255]
                    block_width = 9
                elif "Moderate" in sev_name:
                    block_color = [245, 158, 11, 255]
                    block_width = 7
                else:
                    block_color = [234, 179, 8, 220]
                    block_width = 6

                hazard_applied = st.session_state.get(f"applied_hazard_{action_key}", "Hazard")
                # Blocked road segment (Red/Amber)
                layers.append(pdk.Layer(
                    "PathLayer",
                    [{"path": target_info["blocked_path"], "color": block_color, "name": f"HUMAN OVERRIDE: {hazard_applied} at {target_name} ({sev_name})"}],
                    id="human-blocked-road",
                    get_path="path",
                    get_color="color",
                    width_min_pixels=block_width,
                    pickable=True
                ))

                # Dynamically recalculated green corridor route using simulation engine
                # Dark casing outline [6, 78, 59, 200]
                layers.append(pdk.Layer(
                    "PathLayer",
                    [{
                        "path": green_corridor["waypoints"],
                        "color": [6, 78, 59, 200],
                        "name": f"DYNAMIC EMS CORRIDOR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                    }],
                    id="human-recalc-bypass-casing",
                    get_path="path",
                    get_color="color",
                    width_min_pixels=13,
                    pickable=False,
                    rounded=True
                ))
                # Clean emerald green line [16, 185, 129, 255]
                layers.append(pdk.Layer(
                    "PathLayer",
                    [{
                        "path": green_corridor["waypoints"],
                        "color": [16, 185, 129, 255] if not green_corridor["is_rerouted"] else [56, 189, 248, 255],
                        "name": f"DYNAMIC EMS CORRIDOR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                    }],
                    id="human-recalc-bypass",
                    get_path="path",
                    get_color="color",
                    width_min_pixels=9,
                    pickable=True,
                    rounded=True
                ))

                # Destination Hospital Marker Pin
                dest_pt = green_corridor["waypoints"][-1]
                layers.append(pdk.Layer(
                    "ScatterplotLayer",
                    [{
                        "position": dest_pt,
                        "color": [168, 85, 247, 240],
                        "radius": 45,
                        "name": f"DESTINATION HUB: {green_corridor['hospital_name']}"
                    }],
                    id="ems-destination-hub-marker",
                    get_position="position",
                    get_fill_color="color",
                    get_radius="radius",
                    pickable=True
                ))

                # Also show water plane or thermal exclusion lanes if relevant
                if mode == "DISASTER_FLOOD":
                    layers.append(pdk.Layer(
                        "PolygonLayer",
                        [{"polygon": [[77.6745, 12.9252], [77.6750, 12.9270], [77.6780, 12.9268], [77.6775, 12.9248]], "elevation": 14, "color": [14, 116, 144, 160]}],
                        id="flood-water-plane-man",
                        get_polygon="polygon",
                        get_elevation="elevation",
                        get_fill_color="color",
                        extruded=True
                    ))
                elif mode == "DISASTER_FIRE":
                    primary_access = get_building_access_lane(active_fire_bldg, fire_origin_c)
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{"path": primary_access, "color": [239, 68, 68, 255], "name": f"THERMAL EXCLUSION ZONE: Severed Ingress Lane at {active_fire_bldg}"}],
                        id="fire-severed-lane-man",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=8,
                        pickable=True
                    ))

            else:
                # 🤖 Default AI Auto-Detect Map Scenarios
                if mode == "DISASTER_FLOOD":
                    flood_basin = [
                        [77.6745, 12.9252],
                        [77.6750, 12.9270],
                        [77.6780, 12.9268],
                        [77.6775, 12.9248],
                        [77.6745, 12.9252]
                    ]
                    layers.append(pdk.Layer(
                        "PolygonLayer",
                        [{"polygon": flood_basin, "elevation": 14, "color": [14, 116, 144, 160]}],
                        id="flood-water-plane",
                        get_polygon="polygon",
                        get_elevation="elevation",
                        get_fill_color="color",
                        get_line_color=[56, 189, 248, 240],
                        line_width_min_pixels=2,
                        extruded=True,
                        pickable=True
                    ))

                    underpass_blocked = [
                        [77.6710, 12.9235],
                        [77.6765, 12.9262],
                        [77.6800, 12.9256],
                        [77.6842, 12.9250]
                    ]
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{"path": underpass_blocked, "color": [239, 68, 68, 255], "name": "BLOCKED: Bellandur Underpass (Submerged 1.2m)"}],
                        id="blocked-underpass",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=6,
                        pickable=True
                    ))

                    # Dark casing outline [6, 78, 59, 200]
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{
                            "path": green_corridor["waypoints"],
                            "color": [6, 78, 59, 200],
                            "name": f"DYNAMIC EMS DETOUR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                        }],
                        id="ems-flyover-bypass-casing",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=11,
                        pickable=False,
                        rounded=True
                    ))
                    # Clean emerald green line [16, 185, 129, 255]
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{
                            "path": green_corridor["waypoints"],
                            "color": [16, 185, 129, 255] if not green_corridor["is_rerouted"] else [56, 189, 248, 255],
                            "name": f"DYNAMIC EMS DETOUR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                        }],
                        id="ems-flyover-bypass",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=7,
                        pickable=True,
                        rounded=True
                    ))

                    dest_pt_auto = green_corridor["waypoints"][-1]
                    layers.append(pdk.Layer(
                        "ScatterplotLayer",
                        [{
                            "position": dest_pt_auto,
                            "color": [168, 85, 247, 240],
                            "radius": 45,
                            "name": f"DESTINATION: {green_corridor['hospital_name']}"
                        }],
                        id="ems-auto-destination-marker",
                        get_position="position",
                        get_fill_color="color",
                        get_radius="radius",
                        pickable=True
                    ))

                elif mode == "DISASTER_FIRE":
                    # Thermal Exclusion Zone: Sever immediately adjacent access lanes in red
                    primary_access = get_building_access_lane(active_fire_bldg, fire_origin_c)
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{"path": primary_access, "color": [239, 68, 68, 255], "name": f"THERMAL EXCLUSION ZONE: Severed Ingress Lane at {active_fire_bldg}"}],
                        id="fire-severed-lane-origin",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=8,
                        pickable=True
                    ))
                    if secondary_spread_active and secondary_spread_bldg:
                        secondary_access = get_building_access_lane(secondary_spread_bldg, nearest_bldg_c)
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{"path": secondary_access, "color": [249, 115, 22, 255], "name": f"DOWNWIND SPREAD SECTOR: Thermal Risk Lane at {secondary_spread_bldg}"}],
                            id="fire-severed-lane-secondary",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=7,
                            pickable=True
                        ))

                    # Directional smoke cone extending Northeast from fire origin
                    if fire_origin_c:
                        c_lon, c_lat = fire_origin_c
                        smoke_cone = [
                            [c_lon, c_lat],
                            [c_lon + 0.0130, c_lat + 0.0115],
                            [c_lon + 0.0055, c_lat + 0.0155],
                            [c_lon, c_lat]
                        ]
                        layers.append(pdk.Layer(
                            "PolygonLayer",
                            [{"polygon": smoke_cone, "color": [100, 116, 139, 140]}],
                            id="smoke-cone-poly",
                            get_polygon="polygon",
                            get_fill_color="color",
                            pickable=True
                        ))

                    # Green fire-tender corridor from Sarjapur Base
                    fire_tender_route = [
                        [77.6655, 12.9208],
                        [77.6685, 12.9222],
                        [77.6710, 12.9235],
                        [77.6740, 12.9252],
                        [77.6770, 12.9265],
                        [77.6800, 12.9258],
                        [77.6842, 12.9250]
                    ]
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{"path": fire_tender_route, "color": [6, 78, 59, 200], "name": "FIRE-TENDER RAPID CORRIDOR (CLEAR OF PUBLIC TRAFFIC)"}],
                        id="fire-tender-corridor-casing",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=13,
                        pickable=False,
                        rounded=True
                    ))
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{"path": fire_tender_route, "color": [16, 185, 129, 255], "name": "FIRE-TENDER RAPID CORRIDOR (CLEAR OF PUBLIC TRAFFIC)"}],
                        id="fire-tender-corridor",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=9,
                        pickable=True,
                        rounded=True
                    ))

                    # Dynamic evacuation corridor avoiding thermal hazard
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{
                            "path": green_corridor["waypoints"],
                            "color": [6, 78, 59, 200],
                            "name": f"DYNAMIC EMS DETOUR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                        }],
                        id="fire-recalc-corridor-casing",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=12,
                        pickable=False,
                        rounded=True
                    ))
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{
                            "path": green_corridor["waypoints"],
                            "color": [16, 185, 129, 255],
                            "name": f"DYNAMIC EMS DETOUR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                        }],
                        id="fire-recalc-corridor",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=8,
                        pickable=True,
                        rounded=True
                    ))

                    dest_pt_fire = green_corridor["waypoints"][-1]
                    layers.append(pdk.Layer(
                        "ScatterplotLayer",
                        [{
                            "position": dest_pt_fire,
                            "color": [168, 85, 247, 240],  # Purple
                            "radius": 48,
                            "name": f"DESTINATION HUB: {green_corridor['hospital_name']}"
                        }],
                        id="fire-dest-marker",
                        get_position="position",
                        get_fill_color="color",
                        get_radius="radius",
                        pickable=True
                    ))

                elif mode == "DISASTER_EARTHQUAKE":
                    if current_quake_mag < 3.5:
                        # M < 3.5: Minor - 0% structural damage, all roads open
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{
                                "path": green_corridor["waypoints"],
                                "color": [6, 78, 59, 200],
                                "name": "NORMAL ARTERIAL TRANSIT: All Corridors Open & Stable (M < 3.5 Minor)"
                            }],
                            id="quake-clear-corridor-casing",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=11,
                            pickable=False,
                            rounded=True
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{
                                "path": green_corridor["waypoints"],
                                "color": [16, 185, 129, 255],
                                "name": "NORMAL ARTERIAL TRANSIT: All Corridors Open & Stable (M < 3.5 Minor)"
                            }],
                            id="quake-clear-corridor",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=7,
                            pickable=True,
                            rounded=True
                        ))
                    elif 3.5 <= current_quake_mag < 6.0:
                        # 3.5 <= M < 6.0: Moderate - Masonry crack warnings, flyover ramp closures due to spalling debris, bypass route engaged
                        debris_points = [
                            {"coords": [77.6905, 12.9305], "color": [245, 158, 11, 240], "radius": 50, "name": f"MASONRY CRACK WARNING: Devarabisanahalli Flyover Ramp (M {current_quake_mag:.1f})"}
                        ]
                        layers.append(pdk.Layer(
                            "ScatterplotLayer",
                            debris_points,
                            id="debris-markers",
                            get_position="coords",
                            get_fill_color="color",
                            get_radius="radius",
                            pickable=True
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{"path": [[77.6875, 12.9282], [77.6905, 12.9305]], "color": [239, 68, 68, 255], "name": "QUARANTINED: Devarabisanahalli Flyover Ramp (Spalling Debris)"}],
                            id="quake-blocked-lane",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=8,
                            pickable=True
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{
                                "path": green_corridor["waypoints"],
                                "color": [6, 78, 59, 200],
                                "name": f"ENGAGED BYPASS ROUTE: {green_corridor['hospital_name']} (At-Grade Arterial Bypass)"
                            }],
                            id="quake-bypass-route-casing",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=12,
                            pickable=False,
                            rounded=True
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{
                                "path": green_corridor["waypoints"],
                                "color": [16, 185, 129, 255],
                                "name": f"ENGAGED BYPASS ROUTE: {green_corridor['hospital_name']} (At-Grade Arterial Bypass)"
                            }],
                            id="quake-bypass-route",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=8,
                            pickable=True,
                            rounded=True
                        ))
                    else:
                        # M >= 6.0: Severe - Buildings along fault line turn deep collapse-red, multiple road segments blocked by structural rubble, evacuation falls back to perimeter residential bypass corridors
                        rubble_points = [
                            {"coords": [77.6905, 12.9305], "color": [239, 68, 68, 255], "radius": 65, "name": "MAJOR STRUCTURAL COLLAPSE: Devarabisanahalli Ramp Rubble"},
                            {"coords": [77.6765, 12.9262], "color": [239, 68, 68, 255], "radius": 60, "name": "FAULT LINE PAVEMENT FISSURE: Bellandur Underpass Rubble"},
                            {"coords": [77.6842, 12.9250], "color": [239, 68, 68, 255], "radius": 55, "name": "COLLAPSED MASONRY DEBRIS: Ecospace Gate Arterial"}
                        ]
                        layers.append(pdk.Layer(
                            "ScatterplotLayer",
                            rubble_points,
                            id="rubble-markers",
                            get_position="coords",
                            get_fill_color="color",
                            get_radius="radius",
                            pickable=True
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [
                                {"path": [[77.6875, 12.9282], [77.6905, 12.9305]], "color": [239, 68, 68, 255], "name": "SEVERED: Devarabisanahalli Flyover Ramp (Structural Rubble)"},
                                {"path": [[77.6710, 12.9235], [77.6765, 12.9262], [77.6800, 12.9256]], "color": [239, 68, 68, 255], "name": "SEVERED: Bellandur Underpass Corridor (Rubble Blockage)"},
                                {"path": [[77.6800, 12.9256], [77.6842, 12.9250]], "color": [239, 68, 68, 255], "name": "SEVERED: Ecospace Arterial Approach"}
                            ],
                            id="quake-multiple-blocked-lanes",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=8,
                            pickable=True
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{
                                "path": green_corridor["waypoints"],
                                "color": [6, 78, 59, 200],
                                "name": "PERIMETER RESIDENTIAL EVACUATION CORRIDOR: Toward Kaikondrahalli Lake Grounds"
                            }],
                            id="quake-perimeter-evac-route-casing",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=14,
                            pickable=False,
                            rounded=True
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            [{
                                "path": green_corridor["waypoints"],
                                "color": [16, 185, 129, 255],
                                "name": "PERIMETER RESIDENTIAL EVACUATION CORRIDOR: Toward Kaikondrahalli Lake Grounds"
                            }],
                            id="quake-perimeter-evac-route",
                            get_path="path",
                            get_color="color",
                            width_min_pixels=10,
                            pickable=True,
                            rounded=True
                        ))

                    dest_pt_quake = green_corridor["waypoints"][-1]
                    layers.append(pdk.Layer(
                        "ScatterplotLayer",
                        [{
                            "position": dest_pt_quake,
                            "color": [168, 85, 247, 240],  # Purple
                            "radius": 48,
                            "name": f"DESTINATION HUB: {green_corridor['hospital_name']}"
                        }],
                        id="quake-dest-marker",
                        get_position="position",
                        get_fill_color="color",
                        get_radius="radius",
                        pickable=True
                    ))

                else: # TRAFFIC
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [
                            {"path": [[77.6710, 12.9235], [77.6765, 12.9262], [77.6842, 12.9250]], "color": [239, 68, 68, 255], "name": "DEADLOCK CHOKEPOINT (0.0 km/h Anomaly)"},
                            {"path": [[77.6655, 12.9208], [77.6710, 12.9235], [77.6770, 12.9265], [77.6875, 12.9282]], "color": [16, 185, 129, 255], "name": "ADAPTIVE GREEN WAVE (120s Preemption Corridor)"}
                        ],
                        id="traffic-paths",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=8,
                        pickable=True
                    ))

                # ─── Overlay Dynamic Green Corridor when Action Plan executed ───
                if mode != "DISASTER_FLOOD" and st.session_state.plan_executed.get(action_key, False):
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{
                            "path": green_corridor["waypoints"],
                            "color": [6, 78, 59, 200],
                            "name": f"DYNAMIC EMS CORRIDOR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                        }],
                        id="action-plan-ems-corridor-casing",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=14,
                        pickable=False,
                        rounded=True
                    ))
                    layers.append(pdk.Layer(
                        "PathLayer",
                        [{
                            "path": green_corridor["waypoints"],
                            "color": [16, 185, 129, 255] if not green_corridor["is_rerouted"] else [56, 189, 248, 255],
                            "name": f"DYNAMIC EMS CORRIDOR: {green_corridor['hospital_name']} (Dist: {green_corridor['total_distance_km']} km | ETA: {green_corridor['eta_minutes']} min | {green_corridor['route_status']})"
                        }],
                        id="action-plan-ems-corridor",
                        get_path="path",
                        get_color="color",
                        width_min_pixels=10,
                        pickable=True,
                        rounded=True
                    ))
                    dest_pt_plan = green_corridor["waypoints"][-1]
                    layers.append(pdk.Layer(
                        "ScatterplotLayer",
                        [{
                            "position": dest_pt_plan,
                            "color": [168, 85, 247, 240],
                            "radius": 45,
                            "name": f"DESTINATION HUB: {green_corridor['hospital_name']}"
                        }],
                        id="action-plan-ems-dest-marker",
                        get_position="position",
                        get_fill_color="color",
                        get_radius="radius",
                        pickable=True
                    ))

            # ─────────────────────────────────────────────────────────────────
            # TRAFFIC CONGESTION SPILLOVER ENGINE
            # ─────────────────────────────────────────────────────────────────
            _is_critical_block = False
            _blocked_target    = ""
            if is_manual_active:
                _sev = st.session_state.get(f"applied_severity_{action_key}", "")
                _tgt = st.session_state.get(f"applied_target_{action_key}", "")
                if "Critical" in _sev and _tgt in ("Bellandur Underpass", "Ecospace Gate 2"):
                    _is_critical_block = True
                    _blocked_target    = _tgt
            elif mode == "DISASTER_FLOOD":
                _is_critical_block = True
                _blocked_target    = "Bellandur Underpass"

            if _is_critical_block:
                if _blocked_target == "Bellandur Underpass":
                    congestion_path = [
                        [77.6710, 12.9230],
                        [77.6730, 12.9260],
                        [77.6750, 12.9278],
                        [77.6785, 12.9285],
                        [77.6815, 12.9268],
                    ]
                    congestion_tooltip = (
                        "FLYOVER BOTTLENECK: Inflow 3,400 PCU/hr | "
                        "Avg Speed: 11 km/h | Delay: +32 min"
                    )
                else:  # Ecospace Gate 2
                    congestion_path = [
                        [77.6800, 12.9256],
                        [77.6820, 12.9300],
                        [77.6768, 12.9312],
                        [77.6740, 12.9304],
                    ]
                    congestion_tooltip = (
                        "ECOSPACE GATE BOTTLENECK: Inflow 2,800 PCU/hr | "
                        "Avg Speed: 8 km/h | Delay: +28 min"
                    )

                layers.append(pdk.Layer(
                    "PathLayer",
                    [{"path": congestion_path, "color": [249, 115, 22, 220],
                      "name": congestion_tooltip}],
                    id="congestion-spillover-queue",
                    get_path="path",
                    get_color="color",
                    width_min_pixels=6,
                    pickable=True,
                    rounded=True,
                ))

            # ViewState — canonical Bellandur Underpass tactical overview
            view_state = pdk.ViewState(
                latitude=12.9260,
                longitude=77.6762,
                zoom=15.0,
                pitch=50,
                bearing=-20
            )

            # ─── Traffic KPI Banner ───────────────────────────────────────
            if mode == "DISASTER_EARTHQUAKE":
                if current_quake_mag >= 6.0:
                    _kpi_density_pct   = 94
                    _kpi_density_label = "Gridlock (Debris Blockage)"
                    _kpi_tailback_km   = 4.2
                    _kpi_ems_status    = "ACTIVE — Perimeter Residential Evacuation Engaged"
                elif current_quake_mag >= 3.5:
                    _kpi_density_pct   = 72
                    _kpi_density_label = "Moderate Delay (Flyover Diverted)"
                    _kpi_tailback_km   = 1.8
                    _kpi_ems_status    = "ACTIVE — At-Grade Flyover Bypass"
                else:
                    _kpi_density_pct   = 28
                    _kpi_density_label = "Free Flow (No Structural Damage)"
                    _kpi_tailback_km   = 0.2
                    _kpi_ems_status    = "STANDBY — Normal Circulation"
            elif mode == "DISASTER_FIRE":
                if secondary_spread_active:
                    _kpi_density_pct   = 84
                    _kpi_density_label = "Downwind Spread Hazard"
                    _kpi_tailback_km   = 2.4
                    _kpi_ems_status    = "ACTIVE — Multi-Building Fire Detour"
                else:
                    _kpi_density_pct   = 62
                    _kpi_density_label = "Localized Containment"
                    _kpi_tailback_km   = 1.2
                    _kpi_ems_status    = "ACTIVE — Thermal Perimeter Quarantine"
            else:
                _kpi_density_pct   = 89 if _is_critical_block else 44
                _kpi_density_label = "Heavy Congestion" if _kpi_density_pct >= 80 else "Light"
                _kpi_tailback_km   = 2.6 if _is_critical_block else 0.3
                _kpi_ems_status    = ("ACTIVE — Green Wave Corridor Engaged"
                                      if st.session_state.plan_executed.get(action_key, False)
                                      or mode == "DISASTER_FLOOD"
                                      else "STANDBY")

            _kpi_ems_color     = "#10B981" if "ACTIVE" in _kpi_ems_status else "#F59E0B"
            _kpi_density_color = ("#EF4444" if _kpi_density_pct >= 80
                                  else "#F59E0B" if _kpi_density_pct >= 50 else "#10B981")

            st.markdown(
                f"""
                <div style="
                    display:flex; gap:6px; flex-wrap:wrap;
                    background:rgba(15,23,42,0.92);
                    border:1px solid #1E293B;
                    border-radius:8px;
                    padding:8px 12px;
                    margin-bottom:6px;
                    font-family:'Inter',sans-serif;
                ">
                    <div style="flex:1; min-width:160px; background:rgba(30,41,59,0.7); border-radius:6px; padding:7px 11px; border-left:3px solid {_kpi_density_color};">
                        <div style="font-size:9px; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.8px;">Corridor Density</div>
                        <div style="font-size:15px; font-weight:800; color:{_kpi_density_color}; margin-top:2px;">{_kpi_density_pct}% <span style="font-size:11px; font-weight:600;">({_kpi_density_label})</span></div>
                    </div>
                    <div style="flex:1; min-width:160px; background:rgba(30,41,59,0.7); border-radius:6px; padding:7px 11px; border-left:3px solid #F97316;">
                        <div style="font-size:9px; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.8px;">Bottleneck Tailback</div>
                        <div style="font-size:15px; font-weight:800; color:#F97316; margin-top:2px;">{_kpi_tailback_km} km</div>
                    </div>
                    <div style="flex:2; min-width:220px; background:rgba(30,41,59,0.7); border-radius:6px; padding:7px 11px; border-left:3px solid {_kpi_ems_color};">
                        <div style="font-size:9px; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.8px;">EMS Priority Clearance</div>
                        <div style="font-size:12px; font-weight:800; color:{_kpi_ems_color}; margin-top:2px;">🚑 {_kpi_ems_status}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            deck = pdk.Deck(
                layers=layers,
                initial_view_state=view_state,
                tooltip={"html": "<div style='font-family:Inter; font-size:12px; color:#FFFFFF; background:#161F30; padding:6px 10px; border-radius:6px; border:1px solid #334155;'><b>{name}</b></div>"},
                map_provider=None,
                map_style=None,
            )

            # Prominent PyDeck 3D Map Canvas (Height: 560px)
            st.pydeck_chart(deck, width="stretch", height=560)

            # ─── Floating Map Legend HUD ─────────────────────────────────
            st.markdown(
                """
                <div style="
                    background: rgba(11, 15, 25, 0.88);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    border: 1px solid rgba(51, 65, 85, 0.8);
                    border-radius: 10px;
                    padding: 10px 14px;
                    margin-top: -4px;
                    font-family: 'Inter', sans-serif;
                    display: inline-block;
                    min-width: 280px;
                ">
                    <div style="font-size:9px; font-weight:800; color:#F59E0B; text-transform:uppercase; letter-spacing:1.2px; margin-bottom:7px;">MAP LEGEND — BELLANDUR / ORR CORRIDOR</div>
                    <div style="display:flex; flex-wrap:wrap; gap:6px 16px;">
                        <div style="display:flex; align-items:center; gap:6px;">
                            <div style="width:24px; height:5px; background:#EF4444; border-radius:3px;"></div>
                            <span style="font-size:10.5px; color:#CBD5E1; font-weight:600;">🔴 Blocked Hazard — Submerged Underpass / Gate (Impassable)</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <div style="width:24px; height:5px; background:#F97316; border-radius:3px;"></div>
                            <span style="font-size:10.5px; color:#CBD5E1; font-weight:600;">🟠 Traffic Congestion Queue — Diverted Vehicular Spillover</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <div style="width:24px; height:5px; background:#10B981; border-radius:3px;"></div>
                            <span style="font-size:10.5px; color:#CBD5E1; font-weight:600;">🟢 Dynamic EMS Corridor — Priority Ambulance Bypass to Hospital</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <div style="width:14px; height:14px; background:#A855F7; border-radius:50%; border:2px solid #D8B4FE;"></div>
                            <span style="font-size:10.5px; color:#CBD5E1; font-weight:600;">🟣 Critical Trauma Node — Sakra World Hospital</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <div style="width:14px; height:14px; background:#38BDF8; border-radius:2px; opacity:0.85;"></div>
                            <span style="font-size:10.5px; color:#CBD5E1; font-weight:600;">🏢 IT Campuses — RMZ Ecoworld / Ecospace (Operational)</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Bottom Sliders Directly Beneath the Map
            if mode == "DISASTER_FLOOD":
                slider_val = st.slider(
                    "Rainfall Intensity (mm/hr) — Bellandur Catchment Runoff",
                    min_value=0.0,
                    max_value=100.0,
                    value=st.session_state.get("flood_rainfall_slider", 55.0),
                    step=5.0,
                    key="flood_rainfall_slider"
                )
            elif mode == "DISASTER_FIRE":
                slider_val = st.slider(
                    "Prevailing Wind Speed (km/h) — Northeast Dispersion Vector",
                    min_value=5.0,
                    max_value=60.0,
                    value=st.session_state.get("fire_wind_slider", 24.0),
                    step=1.0,
                    key="fire_wind_slider"
                )
            elif mode == "DISASTER_EARTHQUAKE":
                slider_val = st.slider(
                    "Earthquake Magnitude (Richter Scale) — Epicenter Depth 10 km",
                    min_value=1.0,
                    max_value=8.0,
                    value=st.session_state.get("earthquake_mag_slider", 5.4),
                    step=0.1,
                    key="earthquake_mag_slider"
                )
            else:
                slider_val = st.select_slider(
                    "Corridor Traffic Inflow Preset:",
                    options=["🟢 Off-Peak (Late Night)", "🟡 Normal Midday", "🔴 Peak Monsoon Rush Hour"],
                    value=st.session_state.get("traffic_density_preset_slider", "🔴 Peak Monsoon Rush Hour"),
                    key="traffic_density_preset_slider"
                )

        # -------------------------------------------------------------
        # 4. REMOVE CLUTTER: Collapsible Debug Expander
        # -------------------------------------------------------------
        with st.expander("Telemetry & Camera Debug Feeds", expanded=False):
            deb_col1, deb_col2 = st.columns([1, 1.2])
            with deb_col1:
                st.markdown(
                    """
                    <div style="background:#0F172A; border:1px solid #334155; border-radius:8px; padding:12px; text-align:center;">
                        <div style="font-size:28px;">📹</div>
                        <div style="font-size:12px; font-weight:700; color:#38BDF8;">FEED: CAM-04-BELLANDUR</div>
                        <div style="font-size:11px; color:#94A3B8;">Bellandur Underpass S/W Telemetry</div>
                        <div style="margin-top:6px; font-size:11px; font-weight:800; color:#EF4444;">STATUS: ACTIVE MONITORING</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with deb_col2:
                st.markdown(
                    """
                    <div style="font-size:12px; color:#CBD5E1; line-height:1.5;">
                        <b>Sensor Network Status:</b><br/>
                        • CAM-04 Underpass: Water Depth 1.2m (Threshold Exceeded)<br/>
                        • Node Sarjapur-ORR: Signal Mode EMS_GREEN_WAVE<br/>
                        • Ecospace North Thermal: FIR-02 Baseline Calibrated<br/>
                        • Kaikondrahalli Assembly Telemetry: Grounds Ready (Capacity: 5,000)
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # =========================================================================
    # VIEW: CITIZEN REPORT OPERATOR TRIAGE CONSOLE (`MONITORING > CITIZEN REPORT`)
    # =========================================================================
    elif st.session_state.nav_view == "CITIZEN_REPORT":
        col_feed, col_inspect = st.columns([60, 40])

        ticket_data = {
            "1042": {
                "title": "Ticket #1042: Severe Flood at Bellandur Underpass (Water Depth 1.4m)",
                "reporter": "Citizen Commuter (PWA Submission)",
                "time": "3 mins ago",
                "loc": "Bellandur Service Road Underpass",
                "urgency": "CRITICAL",
                "urgency_color": "#EF4444",
                "desc": "Water level is above tire level and rising fast. Stalled BMTC bus inside underpass. Trapped commuters waiting on divider.",
                "bbox_class": "Severe Waterlogging & Submerged Vehicle",
                "confidence": "96.8%",
                "coords": "12.9262° N, 77.6765° E",
                "impact": "Obstruction: 100% of underpass width (Impassable)"
            },
            "1043": {
                "title": "Ticket #1043: Fallen Avenue Tree Blocking Ecospace Gate 2",
                "reporter": "Ecospace Security Supervisor",
                "time": "11 mins ago",
                "loc": "Ecospace Business Park Gate 2 Entrance",
                "urgency": "HIGH",
                "urgency_color": "#F59E0B",
                "desc": "Gulmohar avenue tree uprooted during squall. Completely blocking outbound service lane. Two-wheelers attempting sidewalk detour.",
                "bbox_class": "Fallen Tree / Road Obstacle",
                "confidence": "94.2%",
                "coords": "12.9248° N, 77.6835° E",
                "impact": "Obstruction: 80% of drivable lane width"
            },
            "1044": {
                "title": "Ticket #1044: Structural Cave-in at Devarabisanahalli Flyover",
                "reporter": "Traffic Warden Post #12",
                "time": "19 mins ago",
                "loc": "Devarabisanahalli Flyover Northern Ramp",
                "urgency": "WARNING",
                "urgency_color": "#F59E0B",
                "desc": "Asphalt collapsed near flyover expansion joint creating 1.5m pothole trench. Vehicles braking abruptly causing rear-end collision hazards.",
                "bbox_class": "Structural Cave-in / Pothole Trench",
                "confidence": "91.5%",
                "coords": "12.9312° N, 77.6880° E",
                "impact": "Obstruction: 60% of right carriageway"
            }
        }

        # Include newly submitted ticket #1045 if logged
        if st.session_state.get("civic_ticket_submitted", False):
            c_info = st.session_state.get("civic_submitted_data", {})
            ticket_data["1045"] = {
                "title": f"Ticket #1045: {c_info.get('category', 'Road Hazard')} at Bellandur ORR",
                "reporter": "Citizen Field Reporter (Mobile Web PWA)",
                "time": "Just now",
                "loc": "Bellandur ORR Low Inundation Zone",
                "urgency": "CRITICAL",
                "urgency_color": "#EF4444",
                "desc": c_info.get("desc", "Emergency hazard reported via citizen mobile portal."),
                "bbox_class": c_info.get("category", "Waterlogging").replace("🌊 ", "").replace("🌳 ", "").replace("🕳️ ", "").replace("⚡ ", ""),
                "confidence": "95.5%",
                "coords": "12.9262° N, 77.6765° E",
                "impact": "Obstruction: 90% of carriageway"
            }

        # -------------------------------------------------------------
        # LEFT COLUMN (col_feed - 60% width): Interactive Selectable List
        # -------------------------------------------------------------
        with col_feed:
            st.markdown(
                """
                <div style="margin-bottom:12px;">
                    <h3 style="margin:0; font-size:16px; font-weight:800; color:#FFFFFF;">
                        INCOMING CITIZEN HAZARD TICKETS (WARD 150 - BELLANDUR)
                    </h3>
                    <p style="margin:2px 0 0 0; font-size:12px; color:#94A3B8;">
                        Select a ticket to review YOLOv8 computer vision triage and execute municipal road closure directives.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            ticket_options = [f"{tid}: {tinfo['title'].split(': ')[1]}" for tid, tinfo in ticket_data.items()]

            selected_option = st.radio(
                "Select Ticket for Triage",
                options=ticket_options,
                index=0,
                label_visibility="collapsed"
            )
            selected_id = selected_option.split(":")[0].strip()

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

            # Render Interactive ticket summary cards
            for tid, tinfo in ticket_data.items():
                cur_status = st.session_state.ticket_status.get(tid, "PENDING")
                is_selected = (tid == selected_id)
                border_color = "#F59E0B" if is_selected else "#334155"

                status_badge = (
                    "<span style='background:rgba(245,158,11,0.2); color:#F59E0B; border:1px solid #F59E0B; padding:2px 7px; border-radius:4px; font-size:10px; font-weight:800;'>PENDING TRIAGE</span>"
                    if cur_status == "PENDING" else (
                        "<span style='background:rgba(16,185,129,0.2); color:#10B981; border:1px solid #10B981; padding:2px 7px; border-radius:4px; font-size:10px; font-weight:800;'>✓ APPROVED & INVALIDATED</span>"
                        if cur_status == "APPROVED" else
                        "<span style='background:rgba(100,116,139,0.2); color:#94A3B8; border:1px solid #94A3B8; padding:2px 7px; border-radius:4px; font-size:10px; font-weight:800;'>✕ DISMISSED</span>"
                    )
                )

                st.markdown(
                    f"""
                    <div style="background:rgba(22,31,48,0.9); border:1.5px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <span style="font-size:13px; font-weight:800; color:#FFFFFF;">Ticket #{tid}</span>
                            <div style="display:flex; gap:6px; align-items:center;">
                                <span style="background:rgba(239,68,68,0.15); color:{tinfo['urgency_color']}; border:1px solid {tinfo['urgency_color']}; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:700;">{tinfo['urgency']}</span>
                                {status_badge}
                            </div>
                        </div>
                        <div style="font-size:11.5px; color:#94A3B8; margin-bottom:4px;">
                            {tinfo['reporter']} • {tinfo['time']} • {tinfo['loc']}
                        </div>
                        <div style="font-size:12px; color:#E2E8F0; line-height:1.4;">
                            "{tinfo['desc']}"
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # -------------------------------------------------------------
        # RIGHT COLUMN (col_inspect - 40% width): AI Vision Triage & Two Buttons
        # -------------------------------------------------------------
        with col_inspect:
            t = ticket_data.get(selected_id, ticket_data["1042"])
            st.markdown(
                """
                <div style="margin-bottom:12px;">
                    <h3 style="margin:0; font-size:16px; font-weight:800; color:#FFFFFF;">
                        AI VISION TRIAGE & VERIFICATION
                    </h3>
                    <p style="margin:2px 0 0 0; font-size:12px; color:#94A3B8;">
                        Real-time edge neural inference validating crowdsourced hazard report.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Simulated CCTV / Mobile Viewfinder with Bounding Box
            st.markdown(
                f"""
                <div class="cctv-viewfinder">
                    <div class="cctv-topbar">
                        <span>● YOLOv8 INFERENCE: STREAM_VERIFY_{selected_id}</span>
                        <span>CONF: {t['confidence']}</span>
                    </div>
                    <div class="cctv-box">
                        <span class="cctv-bbox-label">CLASS: {t['bbox_class']}</span>
                        <div style="font-size:24px; margin:4px 0;">📷</div>
                        <div style="font-size:11px; color:#94A3B8;">GEOTAG: {t['coords']}</div>
                    </div>
                </div>

                <div style="background:#161F30; border:1px solid #334155; border-radius:8px; padding:12px; margin-bottom:14px; font-size:12px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:#94A3B8;">Bounding Box Class:</span>
                        <strong style="color:#38BDF8;">{t['bbox_class']}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:#94A3B8;">Model Confidence:</span>
                        <strong style="color:#10B981;">{t['confidence']} (yolov8-urban-det)</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:#94A3B8;">GPS Coordinates:</span>
                        <strong style="color:#FFFFFF;">{t['coords']}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#94A3B8;">Road Impact:</span>
                        <strong style="color:#F59E0B;">{t['impact']}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Two Action Buttons
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("APPROVE & INVALIDATE ROAD EDGE", key=f"btn_approve_{selected_id}"):
                    st.session_state.ticket_status[selected_id] = "APPROVED"
                    st.rerun()

            with col_b2:
                if st.button("DISMISS AS NON-HAZARD", key=f"btn_dismiss_{selected_id}"):
                    st.session_state.ticket_status[selected_id] = "DISMISSED"
                    st.rerun()

            # Status Message
            if st.session_state.ticket_status.get(selected_id) == "APPROVED":
                st.markdown(
                    f"""
                    <div style="background:rgba(16,185,129,0.18); border:1px solid #10B981; border-radius:6px; padding:8px 12px; margin-top:8px; font-size:12px; color:#10B981; font-weight:700;">
                        ✓ TICKET #{selected_id} APPROVED: Road link marked IMPASSABLE. Dynamic detour broadcast to BTP and ambulances live.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif st.session_state.ticket_status.get(selected_id) == "DISMISSED":
                st.markdown(
                    f"""
                    <div style="background:rgba(100,116,139,0.2); border:1px solid #64748B; border-radius:6px; padding:8px 12px; margin-top:8px; font-size:12px; color:#94A3B8; font-weight:700;">
                        ✕ TICKET #{selected_id} DISMISSED: Marked as non-critical advisory. No road edge closed.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
