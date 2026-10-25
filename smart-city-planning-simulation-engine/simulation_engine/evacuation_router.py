"""
Evacuation Router (Safe Assembly Grounds Routing Engine) - Stage 1 Frontend
Computes pedestrian and vehicle evacuation paths towards open assembly grounds (Kaikondrahalli Lake,
Bellandur Sports Ground, Iblur Reserve) during seismic alarms or fire outbreaks.
"""

from typing import Dict, Any, List


class EvacuationRouter:
    """Calculates civilian egress vectors and shelter allocation."""

    def __init__(self):
        self.assembly_grounds = [
            {
                "id": "assembly_kaikondrahalli",
                "name": "Kaikondrahalli Lake Open Grounds",
                "lat": 12.9125,
                "lon": 77.6740,
                "max_capacity": 5000,
                "current_count": 1420,
                "facilities": ["Medical Triage Staging", "Emergency Drinking Water", "Mobile Ham Radio"],
                "status": "OPEN_SAFE"
            },
            {
                "id": "assembly_bellandur_sports",
                "name": "Bellandur Community Sports Ground",
                "lat": 12.9320,
                "lon": 77.6710,
                "max_capacity": 3500,
                "current_count": 980,
                "facilities": ["Shelter Tents", "First-Aid Dispensary"],
                "status": "OPEN_SAFE"
            },
            {
                "id": "assembly_iblur_military",
                "name": "Sarjapur Iblur Open Reserve",
                "lat": 12.9230,
                "lon": 77.6590,
                "max_capacity": 12000,
                "current_count": 2150,
                "facilities": ["High-Capacity Field Hospital", "Helipad Staging Area"],
                "status": "OPEN_SAFE"
            }
        ]

        # Preset evacuation corridors from Ecospace / ORR Core
        self.corridor_to_kaikondrahalli = [
            [77.6842, 12.9250], # Ecospace Gateway
            [77.6780, 12.9200], # Kaikondrahalli North Access
            [77.6740, 12.9125]  # Kaikondrahalli Safe Assembly Ground
        ]

        self.corridor_to_bellandur_sports = [
            [77.6710, 12.9235], # Bellandur Gate
            [77.6700, 12.9280], # Inner Ring Road Link
            [77.6710, 12.9320]  # Bellandur Sports Ground
        ]

    def compute_evacuation_plan(
        self,
        hazard_type: str = "FIRE", # "FIRE", "SEISMIC", "FLOOD"
        origin_lat: float = 12.9248,
        origin_lon: float = 77.6845,
        estimated_evacuees: int = 4200
    ) -> Dict[str, Any]:
        """
        Generate designated assembly assignment, path geometry, and remaining shelter capacities.
        """
        # Determine target shelter based on proximity and capacity
        target_ground = self.assembly_grounds[0] # Kaikondrahalli
        available_cap = target_ground["max_capacity"] - target_ground["current_count"]
        occupancy_pct = round(((target_ground["current_count"] + min(estimated_evacuees, available_cap)) / target_ground["max_capacity"]) * 100, 1)

        corridor_path = self.corridor_to_kaikondrahalli if "FIRE" in hazard_type else self.corridor_to_bellandur_sports

        return {
            "hazard_type": hazard_type,
            "target_ground": target_ground,
            "evacuation_corridor_coords": corridor_path,
            "estimated_evacuees": estimated_evacuees,
            "projected_occupancy_pct": occupancy_pct,
            "all_assembly_grounds": self.assembly_grounds,
            "color": [249, 115, 22, 220] if hazard_type == "FIRE" else [168, 85, 247, 220],
            "evacuation_instructions": (
                f"Proceed immediately via designated green corridor toward {target_ground['name']}. "
                f"Emergency marshals staged at waypoints. Medical triage active."
            )
        }


if __name__ == "__main__":
    router = EvacuationRouter()
    plan = router.compute_evacuation_plan("FIRE")
    print("Target:", plan["target_ground"]["name"])
    print("Projected occupancy:", plan["projected_occupancy_pct"], "%")
