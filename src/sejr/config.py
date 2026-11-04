from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
JEV_CACHE_DIR = ROOT / "data" / "cache" / "jev"
DB_PATH = ROOT / "data" / "sejr.duckdb"
SITE_DATA_DIR = ROOT / "site" / "data"

SNAPSHOT_DAYS = 7
FIRST_MONTH = "2011-04"

# Pinned so a series never mixes model versions. Changing it means reclassifying all history.
JEV_MODEL = "jev-1.13.0"
