from pathlib import Path

from app.db import run_schema


if __name__ == "__main__":
    run_schema(Path("db/schema.sql"))
    print("schema applied")
