from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import run_schema


if __name__ == "__main__":
    run_schema(ROOT / "db" / "schema.sql")
    print("schema applied")
