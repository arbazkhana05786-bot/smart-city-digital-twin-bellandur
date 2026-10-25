import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation_engine.graph_loader import load_graph, get_nearest_node
from simulation_engine.dynamic_penalizer import invalidate_hazard_edges, reset_graph_weights
from simulation_engine.ambulance_router import (
    compute_green_corridor,
    START_COORDS,
    PRIMARY_TARGET,
    SECONDARY_FALLBACK
)

print("=== 1. TEST GRAPH LOADER ===")
G = load_graph()
print(f"Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
near_start = get_nearest_node(G, START_COORDS[0], START_COORDS[1])
near_primary = get_nearest_node(G, PRIMARY_TARGET[0], PRIMARY_TARGET[1])
near_secondary = get_nearest_node(G, SECONDARY_FALLBACK[0], SECONDARY_FALLBACK[1])
print(f"Nearest Start: {near_start}, Primary: {near_primary}, Secondary: {near_secondary}")

print("\n=== 2. TEST DYNAMIC PENALIZER & AMBULANCE ROUTER (NORMAL) ===")
res_normal = compute_green_corridor(G, START_COORDS, PRIMARY_TARGET)
print(f"Normal Path: {res_normal['hospital_name']}")
print(f"Distance: {res_normal['total_distance_km']} km | ETA: {res_normal['eta_minutes']} min | Waypoints: {len(res_normal['waypoints'])}")
assert not res_normal["is_rerouted"], "Should not be rerouted"

print("\n=== 3. TEST HAZARD INVALIDATION & AUTOMATED FALLBACK REROUTE ===")
invalidated = invalidate_hazard_edges(G, PRIMARY_TARGET, radius_meters=350.0)
print(f"Invalidated edges count: {len(invalidated)}")
res_detour = compute_green_corridor(G, START_COORDS, PRIMARY_TARGET)
print(f"Detour Destination: {res_detour['hospital_name']}")
print(f"Distance: {res_detour['total_distance_km']} km | ETA: {res_detour['eta_minutes']} min | Rerouted: {res_detour['is_rerouted']}")
assert res_detour["is_rerouted"], "Should be rerouted to secondary hospital"

print("\n=== 4. TEST WEIGHT RESET ===")
reset_graph_weights(G)
res_reset = compute_green_corridor(G, START_COORDS, PRIMARY_TARGET)
print(f"After reset: {res_reset['hospital_name']} (Rerouted: {res_reset['is_rerouted']})")
assert not res_reset["is_rerouted"], "Should be back to primary after reset"

print("\n[SUCCESS] ALL BACKEND PHASE 1 ROUTING TESTS PASSED!")
