"""
Disaster Predictor (Mocked Risk Calculation Engine) - Stage 1 Frontend
Evaluates environmental indicators (Rainfall, Wind, Seismic tremor) to calculate composite
disaster severity metrics, flood probability, and infrastructure vulnerability.
"""

from typing import Dict, Any


class MockDisasterPredictor:
    """Mock risk calculation engine for multihazard threat assessment."""

    def __init__(self):
        self.elevation_baseline_m = 882.0

    def calculate_multihazard_risk(
        self,
        rainfall_mm: float,
        wind_speed_kmh: float,
        seismic_magnitude: float
    ) -> Dict[str, Any]:
        """
        Calculate composite risk indices based on interactive slider inputs.
        """
        # 1. Flood Risk Index (0 - 100)
        # Bellandur depression vulnerability curve
        flood_risk = min(100.0, round((rainfall_mm / 120.0) * 100.0, 1))

        # 2. Fire Spread Risk Index (0 - 100)
        # Wind amplification factor
        fire_risk = min(100.0, round((wind_speed_kmh / 60.0) * 85.0 + 15.0, 1))

        # 3. Seismic Structural Risk Index (0 - 100)
        if seismic_magnitude <= 2.0:
            seismic_risk = 5.0
        elif seismic_magnitude <= 4.0:
            seismic_risk = round(15.0 + (seismic_magnitude - 2.0) * 15.0, 1)
        elif seismic_magnitude <= 6.0:
            seismic_risk = round(45.0 + (seismic_magnitude - 4.0) * 25.0, 1)
        else:
            seismic_risk = min(100.0, round(95.0 + (seismic_magnitude - 6.0) * 5.0, 1))

        # Overall composite risk status
        primary_threat = "NORMAL"
        composite_score = max(flood_risk, fire_risk * 0.7, seismic_risk)

        if seismic_magnitude >= 5.0:
            primary_threat = "SEISMIC_STRUCTURAL_ALARM"
        elif rainfall_mm >= 50.0:
            primary_threat = "FLASH_FLOOD_INUNDATION"
        elif wind_speed_kmh >= 45.0:
            primary_threat = "HIGH_WIND_DEBRIS_SPREAD"

        # Water level projection for Bellandur underpass
        underpass_water_rise_m = round(max(0.0, (rainfall_mm - 30.0) * 0.032), 2)

        return {
            "composite_risk_score": round(composite_score, 1),
            "threat_level": "CRITICAL" if composite_score > 70 else ("WARNING" if composite_score > 40 else "NOMINAL"),
            "primary_threat": primary_threat,
            "flood": {
                "risk_score": flood_risk,
                "inundation_water_depth_m": underpass_water_rise_m,
                "bellandur_underpass_blocked": rainfall_mm >= 45.0,
                "submerged_nodes": ["node_bellandur_underpass"] if rainfall_mm >= 45.0 else []
            },
            "fire": {
                "risk_score": fire_risk,
                "spread_velocity_m_per_min": round(wind_speed_kmh * 0.45, 1)
            },
            "seismic": {
                "risk_score": seismic_risk,
                "structural_alarm": seismic_magnitude >= 5.0,
                "jitter_intensity": round(seismic_magnitude * 1.5, 2)
            }
        }


if __name__ == "__main__":
    predictor = MockDisasterPredictor()
    print("Sim 1:", predictor.calculate_multihazard_risk(65.0, 20.0, 0.0))
    print("Sim 2:", predictor.calculate_multihazard_risk(10.0, 15.0, 5.8))
