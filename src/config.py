import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API & Timeframe Settings
API_KEY = os.getenv("ENTSOE_API_KEY", "").strip()
ZONES = ["DE_LU", "FR", "NO_2"]
START_YEAR = 2019
END_YEAR = 2026
TZ = "Europe/Berlin"

# Directory Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
FIGURES_DIR = ROOT_DIR / "figures"

for folder in [RAW_DIR, PROCESSED_DIR, FIGURES_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Thresholds for Consultancy & Trading Framing
NEGATIVE_PRICE_THRESHOLD = 0.0
SPIKE_PRICE_THRESHOLD = 150.0