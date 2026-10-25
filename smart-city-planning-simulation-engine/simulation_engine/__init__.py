"""
Simulation Engine Package
=========================
Core spatial graph, dynamic impedance penalization, and emergency corridor routing.
"""

from .graph_loader import GraphLoader, load_graph, get_nearest_node
from .dynamic_penalizer import (
    DynamicPenalizer, invalidate_hazard_edges, reset_graph_weights,
    BELLANDUR_FLOOD_POLYGON, FLOOD_POLYGON, point_in_polygon
)
from .ambulance_router import (
    AmbulanceRouter,
    compute_green_corridor,
    START_COORDS,
    PRIMARY_TARGET,
    SECONDARY_FALLBACK,
    GEAR_SCHOOL_NORTH_BYPASS,
    SARJAPUR_SOUTH_BYPASS
)
from .adaptive_signal_controller import AdaptiveSignalController
from .anomaly_speed_detector import AnomalySpeedDetector
from .evacuation_router import EvacuationRouter

__all__ = [
    "GraphLoader",
    "load_graph",
    "get_nearest_node",
    "DynamicPenalizer",
    "invalidate_hazard_edges",
    "reset_graph_weights",
    "BELLANDUR_FLOOD_POLYGON",
    "FLOOD_POLYGON",
    "point_in_polygon",
    "AmbulanceRouter",
    "compute_green_corridor",
    "START_COORDS",
    "PRIMARY_TARGET",
    "SECONDARY_FALLBACK",
    "GEAR_SCHOOL_NORTH_BYPASS",
    "SARJAPUR_SOUTH_BYPASS",
    "AdaptiveSignalController",
    "AnomalySpeedDetector",
    "EvacuationRouter"
]
