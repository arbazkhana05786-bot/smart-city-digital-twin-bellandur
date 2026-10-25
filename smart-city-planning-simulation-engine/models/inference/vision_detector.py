"""
Vision Detector (Mocked Inference Engine) - Stage 1 Frontend
Simulates computer vision detection of flood inundation, road debris, and waterlogged chokepoints
along Bengaluru's Bellandur / Outer Ring Road corridor.
"""

from typing import Dict, Any, List
import random


class MockVisionDetector:
    """Mock vision detector simulating edge-AI camera stream inference."""

    def __init__(self, model_name: str = "YOLOv8-Bengaluru-UrbanHazards"):
        self.model_name = model_name
        self.classes = ["waterlogging", "submerged_vehicle", "fallen_tree", "road_fissure", "structural_smoke"]

    def detect_hazards(self, camera_id: str, simulated_rainfall_mm: float = 25.0) -> Dict[str, Any]:
        """
        Simulate vision analysis on a given CCTV / drone node based on current environmental rain.
        """
        # Threshold logic for mock detections
        is_flooded = simulated_rainfall_mm >= 45.0
        confidence = round(0.88 + (0.10 * (min(simulated_rainfall_mm, 100) / 100.0)), 3)

        detections: List[Dict[str, Any]] = []

        if is_flooded:
            water_depth_cm = round(15.0 + (simulated_rainfall_mm - 45.0) * 0.75, 1)
            detections.append({
                "label": "waterlogging_critical",
                "confidence": confidence,
                "bbox": [120, 85, 520, 390],
                "water_depth_est_cm": water_depth_cm,
                "severity": "CRITICAL" if water_depth_cm > 25.0 else "WARNING",
                "recommended_status": "ROAD_IMPASSABLE" if water_depth_cm > 20.0 else "SLOW_DOWN"
            })
            if simulated_rainfall_mm >= 75.0:
                detections.append({
                    "label": "submerged_vehicle",
                    "confidence": 0.91,
                    "bbox": [240, 210, 390, 340],
                    "severity": "HIGH",
                    "recommended_status": "DISPATCH_TOW_UNIT"
                })
        else:
            detections.append({
                "label": "normal_traffic_flow",
                "confidence": 0.96,
                "bbox": [50, 50, 600, 400],
                "severity": "NOMINAL",
                "recommended_status": "CLEAR"
            })

        return {
            "camera_id": camera_id,
            "status": "PROCESSED",
            "model_version": self.model_name,
            "detections_count": len(detections),
            "detections": detections,
            "is_road_compromised": is_flooded and any(d.get("water_depth_est_cm", 0) > 20 for d in detections)
        }


# Quick test invocation stub
if __name__ == "__main__":
    detector = MockVisionDetector()
    print("Normal test:", detector.detect_hazards("cam_bellandur_underpass", 15.0))
    print("Heavy rain test:", detector.detect_hazards("cam_bellandur_underpass", 70.0))
