"""
Anomaly Speed Detector - Stage 1 Frontend
Simulates sudden vehicle speed drops (e.g. 40 km/h down to 0 km/h standstill) on critical road segments,
identifying gridlock and prompting automated detour recommendations.
"""

from typing import Dict, Any, List


class AnomalySpeedDetector:
    """Detects rapid deceleration anomalies across simulated probe telemetry points."""

    def __init__(self):
        self.nominal_speed_kmh = 40.0
        self.anomaly_threshold_drop_pct = 65.0

    def evaluate_edge_speeds(
        self,
        edges: List[Dict[str, Any]],
        simulated_drop_active: bool = False,
        target_edge_id: str = "edge_iblur_to_bellandur_underpass",
        custom_anomaly_speed_kmh: float = 0.0
    ) -> Dict[str, Any]:
        """
        Evaluate edges for sudden localized speed collapse.
        """
        detected_anomalies = []

        for edge in edges:
            eid = edge.get("id", "")
            base_speed = edge.get("base_speed_kmh", self.nominal_speed_kmh)

            if simulated_drop_active and (eid == target_edge_id or "underpass" in eid):
                current_speed = custom_anomaly_speed_kmh
            else:
                current_speed = edge.get("effective_speed_kmh", edge.get("current_speed_kmh", base_speed))

            drop_pct = ((base_speed - current_speed) / base_speed) * 100.0 if base_speed > 0 else 0

            if drop_pct >= self.anomaly_threshold_drop_pct or current_speed <= 5.0:
                detected_anomalies.append({
                    "edge_id": eid,
                    "edge_name": edge.get("name", eid),
                    "base_speed_kmh": base_speed,
                    "current_speed_kmh": round(current_speed, 1),
                    "drop_percentage": round(drop_pct, 1),
                    "anomaly_type": "SUDDEN_GRIDLOCK_COLLAPSE",
                    "severity": "CRITICAL" if current_speed <= 2.0 else "WARNING",
                    "timestamp": "2026-10-16 10:42:15 IST",
                    "suggested_action": "DIVERT_TRAFFIC_TO_SARJAPUR_BYPASS"
                })

        return {
            "anomaly_detected": len(detected_anomalies) > 0,
            "anomaly_count": len(detected_anomalies),
            "anomalies": detected_anomalies,
            "system_recommendation": (
                f"ALERT: Sudden drop from {self.nominal_speed_kmh:.0f}km/h to {custom_anomaly_speed_kmh:.0f}km/h on {target_edge_id}. Bypass routing triggered."
                if detected_anomalies else "Traffic velocity nominal across monitored corridors."
            )
        }


if __name__ == "__main__":
    detector = AnomalySpeedDetector()
    test_edges = [{"id": "edge_iblur_to_bellandur_underpass", "base_speed_kmh": 40.0, "name": "Bellandur Underpass"}]
    print("Normal:", detector.evaluate_edge_speeds(test_edges, False))
    print("Anomaly 0km/h:", detector.evaluate_edge_speeds(test_edges, True, custom_anomaly_speed_kmh=0.0))
