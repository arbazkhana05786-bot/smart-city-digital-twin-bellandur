# Smart City Planning and Simulation Engine (Bengaluru Base)
## Stage 1: Frontend Only & Visual Interactive Simulation Hub

A digital-twin and incident simulation frontend focused on the critical Outer Ring Road (ORR) — Bellandur — Ecospace — Sakra World Hospital traffic and disaster corridor in Bengaluru, Karnataka.

> ⚠️ **STAGING NOTE**: Built under strict Stage 1 Frontend constraints. No backend database or live ML server training dependencies are required. All spatial geometries, network graphs, cellular automata propagation rings, and edge-AI camera vision validations are driven by realistic, local mock data structures.

---

## 🏛️ Architecture & Directory Overview

```
smart-city-planning-simulation-engine/
├── config/
│   ├── disaster_rules.yaml           # Thresholds, risk rules, flood elevation cutoffs
│   └── settings.yaml                 # Base coordinates (Bellandur/ORR), map styles, simulation defaults
├── data/
│   ├── osm_graphs/
│   │   ├── bengaluru_bellandur_network.json   # 14 nodes & 13 edges across ORR, Sarjapur & Panathur
│   │   └── bengaluru_buildings.geojson        # 3D building polygons with heights (Ecospace, Sakra, etc.)
│   └── uploads/                               # Stubs for static drone/surveillance imagery
├── models/
│   ├── saved_weights/                         # Weight stub files (yolov8_weights_stub.txt)
│   └── inference/
│       ├── vision_detector.py                 # Mock vision detector (flood depth, debris detection)
│       ├── disaster_predictor.py              # Mock risk scorer & damage radius generator
│       └── fire_spread_ca.py                  # Cellular automata fire boundary polygon generator
├── simulation_engine/
│   ├── graph_loader.py                        # Parses network JSON and 3D buildings GeoJSON
│   ├── dynamic_penalizer.py                   # Computes dynamic edge travel penalties & blockages
│   ├── adaptive_signal_controller.py          # Mocks signal states with green EMS wave & forced red
│   ├── anomaly_speed_detector.py              # Detects sudden traffic speed drops (40 -> 0 km/h)
│   ├── ambulance_router.py                    # Computes primary vs detour bypass routes around hazards
│   └── evacuation_router.py                   # Computes safe egress paths toward designated assembly grounds
├── citizen_service/
│   └── app/                                   # Citizen Mobile Web PWA Form (HTML, CSS, JS)
│       ├── index.html                         # Mobile layout with 3-tap action rule & BBMP links
│       ├── style.css                          # Slate dark mode (#0F172A) touch styling
│       └── app.js                             # Auto-geolocation, mock Edge-AI vision, local storage feed
├── dashboard/
│   ├── app.py                                 # Streamlit visual command center orchestrator
│   └── components/
│       ├── map_renderer.py                    # PyDeck 3D visualization (buildings, flood water, routes)
│       ├── control_panel.py                   # Control sliders (rain severity, wind, seismic, anomalies)
│       ├── action_card.py                     # Human-centered Action Cards ("What happened / Recs")
│       └── citizen_feed.py                    # Mock ticket visual stream cards
├── requirements.txt                           # Dependencies
└── README.md                                  # Execution and verification guide
```

---

## 🚀 Quickstart & Execution

### 1. Install Dependencies
```bash
cd smart-city-planning-simulation-engine
pip install -r requirements.txt
```

### 2. Launch the Streamlit Visual Command Hub (Port 8501)
```bash
streamlit run dashboard/app.py --server.port 8501
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### 3. Launch the Citizen Mobile Web PWA (Port 8502)
You can serve the citizen mobile app using Python's built-in HTTP server:
```bash
cd citizen_service/app
python -m http.server 8502
```
Open [http://localhost:8502](http://localhost:8502) in your browser or mobile viewport emulator.

---

## ⚡ Staging Scenarios & Interactive Verification

### Scenario 1: Rain Severity & Flood Inundation
- **Action**: Move the "Rainfall Severity" slider beyond **45 mm/hr** (or click "🌊 Monsoon Flood" preset).
- **Visual Override**:
  1. Rising translucent blue flood water plane emerges over Bellandur basin.
  2. "Bellandur ORR Underpass" road link switches to bright **Emergency Red** (`is_blocked = True`).
  3. Route polyline dynamically switches to **Emerald Green Detour** (via elevated flyover / Sarjapur arterial).
  4. Human-Centered Action Card alerts: *"Bellandur ORR Underpass Submerged"* with binary *"[Approve Diversion via Sarjapur Flyover (+2.1 min)]"*.
  5. Edge-AI Vision camera CAM-04 inspector reports detected waterlogging (35cm depth, 94.8% confidence).

### Scenario 2: Ecospace Fire Outbreak & Cellular Automata
- **Action**: Toggle "Ignite Simulated Fire Origin (Ecospace)" (or click "🔥 Ecospace Fire" preset).
- **Visual Override**:
  1. Concentric orange/amber cellular automata propagation boundary rings render on the 3D map.
  2. Adjust Wind Velocity and Wind Direction sliders to see propagation vector elongate downwind.
  3. Action Card triggers: *"Execute immediate phase-1 evacuation toward Kaikondrahalli Lake Safe Assembly Grounds"*.

### Scenario 3: Seismic Tremor & Assembly Grounds
- **Action**: Adjust Earthquake Magnitude slider to **5.8 Richter** (or click "💥 Richter 5.8 Shock" preset).
- **Visual Override**:
  1. Map camera view jitters with structural vibration perspective.
  2. Vulnerable building polygons highlight with structural risk indicators.
  3. Designated open-air assembly grounds (Kaikondrahalli Lake Ground, Bellandur Sports Ground) display real-time shelter capacity metrics.

### Scenario 4: Active 40 km/h to 0 km/h Speed Collapse Anomaly
- **Action**: Toggle "Inject 40km/h ➔ 0km/h Gridlock Drop" (or click "🛑 0km/h Gridlock" preset).
- **Visual Override**:
  1. Road link velocity immediately drops to 0 km/h.
  2. Anomaly detector flags sudden gridlock collapse.
  3. Top metric displays `-100% Collapse`.
  4. Action Card prompts: *"[Approve Variable Message Sign Divert at Iblur Flyover]"*.

### Scenario 5: Citizen Mobile PWA (3-Tap Emergency Reporting)
- **Action**: Navigate to `http://localhost:8502`.
- **Flow**:
  1. **Tap 1**: Tap camera icon to trigger instant photo capture (or mock Edge-AI auto verification).
  2. **Tap 2**: Tap emoji category chip (e.g. 💧 Waterlogging, 🛑 Road Block, 🚗 Deadlock).
  3. **Tap 3**: Tap RED *"SUBMIT EMERGENCY ALERT"* button.
  4. System immediately displays generated ticket (e.g. `BLR-HAZ-8921`), syncs to local storage, and presents administrative grievance handoff card linking to BBMP Sahaaya 2.0 / Swachhata-MoHUA.
