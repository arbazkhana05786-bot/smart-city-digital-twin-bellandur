import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from simulation_engine.graph_loader import GraphLoader
from simulation_engine.dynamic_penalizer import DynamicPenalizer
from simulation_engine.adaptive_signal_controller import AdaptiveSignalController
from simulation_engine.anomaly_speed_detector import AnomalySpeedDetector
from simulation_engine.ambulance_router import AmbulanceRouter
from simulation_engine.evacuation_router import EvacuationRouter
from models.inference.vision_detector import MockVisionDetector
from models.inference.disaster_predictor import MockDisasterPredictor
from models.inference.fire_spread_ca import MockFireSpreadCA

def test_all():
    loader = GraphLoader()
    net = loader.load_network()
    bldgs = loader.load_buildings()
    print("SUCCESS: Network nodes:", len(net["nodes"]), "edges:", len(net["edges"]))
    print("SUCCESS: Buildings features:", len(bldgs["features"]))

    penalizer = DynamicPenalizer()
    edges = penalizer.penalize_network(net["edges"], rainfall_mm=75.0)
    blocked = [e["id"] for e in edges if e["is_blocked"]]
    print("SUCCESS: Underpass flood test blocked edges:", blocked)

    amb = AmbulanceRouter()
    route = amb.compute_ems_route(underpass_blocked=True)
    print("SUCCESS: EMS detour computed:", route["route_name"], "distance:", route["distance_km"])

    fire = MockFireSpreadCA()
    res = fire.simulate_spread_polygon(fire_active=True, wind_speed_kmh=30.0)
    print("SUCCESS: Fire rings generated:", len(res["rings"]))

    sig = AdaptiveSignalController()
    states = sig.get_signal_states(ems_override_active=True)
    print("SUCCESS: Signal states:", len(states), "first mode:", states[0]["mode"])

    speed = AnomalySpeedDetector()
    spd_res = speed.evaluate_edge_speeds(net["edges"], simulated_drop_active=True)
    print("SUCCESS: Speed anomaly detected:", spd_res["anomaly_detected"])

    vision = MockVisionDetector()
    v_res = vision.detect_hazards("cam_bellandur_underpass", 75.0)
    print("SUCCESS: Vision detector hazard:", v_res["is_road_compromised"], "detections:", len(v_res["detections"]))

    disaster = MockDisasterPredictor()
    d_res = disaster.calculate_multihazard_risk(60.0, 25.0, 5.2)
    print("SUCCESS: Disaster composite score:", d_res["composite_risk_score"], "primary:", d_res["primary_threat"])

    evac = EvacuationRouter()
    e_res = evac.compute_evacuation_plan("FIRE")
    print("SUCCESS: Evac target:", e_res["target_ground"]["name"])

if __name__ == "__main__":
    test_all()
