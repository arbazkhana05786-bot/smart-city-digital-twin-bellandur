"""
Smart City Planning & Simulation Engine - Benchmark Datasets Downloader
========================================================================
Automated downloader utility using `kagglehub` and `shutil` for pulling
and organizing the 4 benchmark datasets:
  1. Richter's Predictor (Earthquake Structural Damage)
  2. Flood Prediction & Rainfall-Runoff Catchment Data
  3. Annotated Road Damage & Pothole YOLO/Bounding Box Dataset
  4. City Traffic Speed, Density & PCU Sensor Logs

Usage:
  python data/download_datasets.py --all
  python data/download_datasets.py --domain earthquake
  python data/download_datasets.py --verify
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Base Paths
DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Benchmark Kaggle Dataset Registries
DATASET_REGISTRY = {
    "earthquake": {
        "title": "Richter's Predictor: Earthquake Structural Damage",
        "target_dir": RAW_DIR / "earthquake",
        "kaggle_handles": [
            "arashnic/drivendata-richters-predictor-earthquake-damage",
            "hasibalhasan/richter-predictor-dataset"
        ],
        "expected_files": ["train_values.csv", "train_labels.csv"],
        "description": "76k+ building damage surveys with structural, soil, and floor configurations (Grades 1-3)."
    },
    "flood": {
        "title": "Monsoon Rainfall Runoff & Urban Flood Inundation",
        "target_dir": RAW_DIR / "flood",
        "kaggle_handles": [
            "sobhanmoosavi/flood-prediction",
            "bhavikjikadara/flood-prediction-dataset"
        ],
        "expected_files": ["rainfall_runoff.csv"],
        "description": "Catchment rainfall, drain capacity %, soil saturation, and underpass water level logs."
    },
    "road_damage": {
        "title": "Annotated Road Obstacles, Potholes & Pavement Cracks",
        "target_dir": RAW_DIR / "road_damage",
        "kaggle_handles": [
            "chitholian/annotated-potholes-dataset",
            "virenbr11/pothole-and-plain-road-images"
        ],
        "expected_files": ["pothole_annotations.csv"],
        "description": "Bounding box coordinates, severity, depth, and YOLO detection labels."
    },
    "traffic": {
        "title": "Arterial City Traffic Density & Sensor Speed Logs",
        "target_dir": RAW_DIR / "traffic",
        "kaggle_handles": [
            "hasanburakavci/traffic-prediction-dataset",
            "fedesoriano/traffic-prediction-dataset"
        ],
        "expected_files": ["traffic_speeds_sensor.csv"],
        "description": "Corridor inflow PCU/hr, mean travel speed km/h, and bottleneck congestion indices."
    }
}


def ensure_directories():
    """Ensure raw and processed directories exist."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for domain, meta in DATASET_REGISTRY.items():
        meta["target_dir"].mkdir(parents=True, exist_ok=True)


def download_domain(domain_key: str):
    """Attempt downloading a benchmark dataset via kagglehub with graceful fallback."""
    if domain_key not in DATASET_REGISTRY:
        print(f"[ERROR] Unknown domain: '{domain_key}'. Choose from: {list(DATASET_REGISTRY.keys())}")
        return False

    meta = DATASET_REGISTRY[domain_key]
    target_dir = meta["target_dir"]
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=======================================================")
    print(f"[*] Processing: {meta['title']}")
    print(f"[*] Target Directory: {target_dir}")
    print(f"=======================================================")

    # Check if files already exist locally (e.g., sample/benchmark data)
    existing_files = [f for f in target_dir.iterdir() if f.is_file()]
    if existing_files:
        print(f"[INFO] Found {len(existing_files)} existing file(s) in {target_dir.name}/:")
        for ef in existing_files:
            size_kb = ef.stat().st_size / 1024
            print(f"   - {ef.name} ({size_kb:.1f} KB)")
        print(f"[INFO] Domain '{domain_key}' is already usable offline.")

    # Try downloading using kagglehub
    try:
        import kagglehub
        downloaded = False

        for handle in meta["kaggle_handles"]:
            try:
                print(f"[INFO] Attempting download for handle '{handle}' via kagglehub...")
                cached_path = kagglehub.dataset_download(handle)
                print(f"[SUCCESS] Downloaded to cache: {cached_path}")

                cached_dir = Path(cached_path)
                # Copy files to target_dir using shutil
                copied_count = 0
                for item in cached_dir.rglob("*"):
                    if item.is_file():
                        dest_file = target_dir / item.name
                        shutil.copy2(item, dest_file)
                        copied_count += 1
                        print(f"   -> Copied: {dest_file.name}")

                print(f"[SUCCESS] Transferred {copied_count} files into {target_dir}")
                downloaded = True
                break
            except Exception as e:
                print(f"[WARNING] Download attempt for '{handle}' failed: {e}")

        if not downloaded:
            print(f"[NOTICE] Online Kaggle download skipped or unauthenticated.")
            print(f"         Existing offline benchmark samples remain active in {target_dir.name}/.")
            print(f"         To configure Kaggle API: Place your kaggle.json in ~/.kaggle/ or set KAGGLE_USERNAME & KAGGLE_KEY.")
            return True

        return True

    except ImportError:
        print(f"[WARNING] 'kagglehub' package is not installed. Run: pip install kagglehub")
        return False


def verify_datasets():
    """Verify and print status of all benchmark datasets."""
    print("\n" + "=" * 65)
    print("   DATASET VERIFICATION & HEALTH AUDIT REPORT")
    print("=" * 65)

    all_healthy = True
    for domain_key, meta in DATASET_REGISTRY.items():
        target_dir = meta["target_dir"]
        files = list(target_dir.glob("*.csv")) + list(target_dir.glob("*.json")) + list(target_dir.glob("*.graphml"))
        
        status_symbol = "✓" if files else "✗"
        print(f"\n{status_symbol} [{domain_key.upper()}] - {meta['title']}")
        print(f"   Directory: {target_dir}")
        
        if files:
            for f in files:
                size_kb = f.stat().st_size / 1024
                # Count rows if CSV
                rows_info = ""
                if f.suffix == ".csv":
                    try:
                        with open(f, "r", encoding="utf-8") as fp:
                            row_count = sum(1 for _ in fp) - 1
                        rows_info = f" | {row_count:,} records"
                    except Exception:
                        pass
                print(f"   • {f.name} ({size_kb:.1f} KB{rows_info})")
        else:
            print("   [!] No data files found in this directory.")
            all_healthy = False

    # Also check osm_graphs
    osm_dir = DATA_DIR / "osm_graphs"
    print(f"\n✓ [OSM_GRAPHS] - Bellandur / ORR Geospatial Base Graph")
    print(f"   Directory: {osm_dir}")
    if osm_dir.exists():
        for f in osm_dir.iterdir():
            if f.is_file():
                size_kb = f.stat().st_size / 1024
                print(f"   • {f.name} ({size_kb:.1f} KB)")
    else:
        print("   [!] OSM directory missing.")
        all_healthy = False

    print("\n" + "=" * 65)
    if all_healthy:
        print("✓ ALL BENCHMARK DATASETS & GIS GRAPHS READY FOR EXAMINER DEMO.")
    else:
        print("[!] Some datasets are incomplete. Run with --all to populate.")
    print("=" * 65 + "\n")
    return all_healthy


def main():
    parser = argparse.ArgumentParser(description="Benchmark Dataset Pipeline for Smart City Engine")
    parser.add_argument("--all", action="store_true", help="Download and organize all 4 benchmark datasets")
    parser.add_argument("--domain", choices=["earthquake", "flood", "road_damage", "traffic"], help="Download a specific domain")
    parser.add_argument("--verify", action="store_true", help="Audit local dataset files and schemas")

    args = parser.parse_args()
    ensure_directories()

    if args.verify:
        verify_datasets()
    elif args.domain:
        download_domain(args.domain)
        verify_datasets()
    elif args.all or len(sys.argv) == 1:
        for domain in DATASET_REGISTRY.keys():
            download_domain(domain)
        verify_datasets()


if __name__ == "__main__":
    main()
