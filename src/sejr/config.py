from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
JEV_CACHE_DIR = ROOT / "data" / "cache" / "jev"
DB_PATH = ROOT / "data" / "sejr.duckdb"
SITE_DATA_DIR = ROOT / "site" / "data"

SNAPSHOT_DAYS = 7
FIRST_MONTH = "2011-04"

# Pinned so a series never mixes model versions. Changing it means reclassifying all history.
JEV_MODEL = "jev-1.14.0"
# Input tokens only; output tokens are free (docs.typesafe.ai/models, Jev 1.13 and 1.14).
JEV_USD_PER_MTOK = 0.042
