"""
Fire Spread Cellular Automata (Mocked Propagation Geometry) - Stage 1 Frontend
Generates synthetic propagation polygons for industrial / wildland urban interface fire incidents
around Bellandur / Ecospace corridor based on wind velocity and simulated time.
"""

import math
from typing import Dict, Any, List


class MockFireSpreadCA:
    """Mock cellular automata fire propagation model producing boundary polygons."""

    def __init__(self, default_origin: tuple = (12.9248, 77.6845)):
        self.default_lat, self.default_lon = default_origin

    def simulate_spread_polygon(
        self,
        origin_lat: float = None,
        origin_lon: float = None,
        wind_speed_kmh: float = 20.0,
        wind_direction_deg: float = 45.0, # Wind blowing toward Northeast (45 deg)
        time_elapsed_min: int = 30,
        fire_active: bool = False
    ) -> Dict[str, Any]:
        """
        Generate mock polygonal propagation perimeter skewed along the wind vector.
        """
        if not fire_active:
            return {
                "fire_active": False,
                "perimeter_polygons": [],
                "affected_area_sqm": 0,
                "threat_level": "NONE",
                "evacuation_recommended": False
            }

        lat = origin_lat if origin_lat is not None else self.default_lat
        lon = origin_lon if origin_lon is not None else self.default_lon

        # Convert wind angle to radians
        rad = math.radians(wind_direction_deg)
        # Expansion distance in degrees (~111km per deg lat, ~108km per deg lon at Bengaluru)
        base_radius_m = max(80.0, time_elapsed_min * 12.0)
        wind_elongation = 1.0 + (wind_speed_kmh / 30.0)

        # Generate 2 concentric polygon rings (core flame zone and outer heat/smoke boundary)
        rings = []
        for scale, ring_name, alpha in [(0.5, "core_burn_zone", 220), (1.0, "outer_smoke_boundary", 140)]:
            coords = []
            for deg in range(0, 360, 20):
                angle = math.radians(deg)
                # Wind bias: extend more in direction of wind
                wind_bias = 1.0 + 0.6 * math.cos(angle - rad) * wind_elongation
                effective_radius_m = base_radius_m * scale * wind_bias

                # Approx degree offset
                d_lat = (effective_radius_m * math.cos(angle)) / 111320.0
                d_lon = (effective_radius_m * math.sin(angle)) / (111320.0 * math.cos(math.radians(lat)))
                coords.append([round(lon + d_lon, 6), round(lat + d_lat, 6)])

            # Close polygon
            coords.append(coords[0])
            rings.append({
                "ring_name": ring_name,
                "polygon": coords,
                "color": [249, 115, 22, alpha] if scale == 1.0 else [220, 38, 38, alpha]
            })

        affected_area_sqm = round(math.pi * (base_radius_m ** 2) * wind_elongation, 1)

        return {
            "fire_active": True,
            "origin": [lon, lat],
            "rings": rings,
            "affected_area_sqm": affected_area_sqm,
            "threat_level": "CRITICAL" if wind_speed_kmh > 25 else "HIGH",
            "evacuation_recommended": True,
            "threatened_facilities": [
                "Ecospace Campus Block 1A & 1B",
                "ORR East Peripheral Service Lane",
                "Bellandur Central Commercial Complex"
            ]
        }


if __name__ == "__main__":
    ca = MockFireSpreadCA()
    res = ca.simulate_spread_polygon(fire_active=True, wind_speed_kmh=35.0, wind_direction_deg=60.0)
    print("Fire rings generated:", len(res["rings"]))
    print("Ring 0 length:", len(res["rings"][0]["polygon"]))
