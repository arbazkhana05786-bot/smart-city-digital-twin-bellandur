"""
Adaptive Signal Controller (Traffic Timing & EMS Green Wave Engine) - Stage 1 Frontend
Mocks density-based signal timing and provides immediate forced Red / EMS priority overrides
for emergency response along the Bellandur / ORR arterial corridor.
"""

from typing import Dict, Any, List


class AdaptiveSignalController:
    """Simulates intelligent traffic signal controllers with emergency preemption."""

    def __init__(self):
        # Default intersection definitions
        self.signal_nodes = [
            {"id": "sig_iblur", "name": "Iblur Sarjapur-ORR Junction", "lat": 12.9208, "lon": 77.6655, "density_pcu": 1850},
            {"id": "sig_bellandur_gate", "name": "Bellandur Gate Signal", "lat": 12.9235, "lon": 77.6710, "density_pcu": 1420},
            {"id": "sig_ecospace_front", "name": "Ecospace Tech Park Signal", "lat": 12.9250, "lon": 77.6842, "density_pcu": 2100},
            {"id": "sig_sakra", "name": "Sakra Hospital Priority Node", "lat": 12.9282, "lon": 77.6875, "density_pcu": 1100},
            {"id": "sig_kadubeesanahalli", "name": "Kadubeesanahalli Junction Signal", "lat": 12.9355, "lon": 77.6955, "density_pcu": 1650}
        ]

    def get_signal_states(
        self,
        ems_override_active: bool = False,
        flood_active: bool = False,
        fire_active: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Compute active signal lamp colors and override statuses for all signalized nodes.
        """
        states = []

        for node in self.signal_nodes:
            nid = node["id"]
            density = node["density_pcu"]

            # Calculate normal green duration based on PCU density (30s to 75s)
            normal_green = min(75, max(30, int(density / 30)))
            normal_red = 90 - normal_green

            state = {
                "signal_id": nid,
                "name": node["name"],
                "lat": node["lat"],
                "lon": node["lon"],
                "mode": "ADAPTIVE_AUTOMATIC",
                "current_lamp": "GREEN",
                "green_duration_sec": normal_green,
                "red_duration_sec": normal_red,
                "remaining_sec": 24,
                "ems_preemption": False,
                "color_rgb": [34, 197, 94] # Bright green
            }

            # 1. EMS Priority Override Wave (Green Corridor)
            if ems_override_active:
                state["mode"] = "EMS_GREEN_WAVE_OVERRIDE"
                state["current_lamp"] = "FORCED_EMS_GREEN"
                state["green_duration_sec"] = 120
                state["red_duration_sec"] = 0
                state["remaining_sec"] = 115
                state["ems_preemption"] = True
                state["color_rgb"] = [16, 185, 129] # Neon Emerald Green

            # 2. Flood Containment (Forced Red at Bellandur Underpass access)
            elif flood_active and nid in ["sig_bellandur_gate"]:
                state["mode"] = "HAZARD_CONTAINMENT_FORCED_RED"
                state["current_lamp"] = "FORCED_RED"
                state["green_duration_sec"] = 0
                state["red_duration_sec"] = 180
                state["remaining_sec"] = 180
                state["color_rgb"] = [239, 68, 68] # Bright Red

            # 3. Fire Containment (Forced Red at Ecospace entrance)
            elif fire_active and nid in ["sig_ecospace_front"]:
                state["mode"] = "FIRE_PERIMETER_FORCED_RED"
                state["current_lamp"] = "FORCED_RED"
                state["green_duration_sec"] = 0
                state["red_duration_sec"] = 180
                state["remaining_sec"] = 180
                state["color_rgb"] = [239, 68, 68] # Bright Red

            states.append(state)

        return states


if __name__ == "__main__":
    controller = AdaptiveSignalController()
    print("Normal signals:", controller.get_signal_states(False, False, False)[0])
    print("EMS wave:", controller.get_signal_states(True, False, False)[0])
