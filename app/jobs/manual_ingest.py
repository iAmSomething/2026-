import argparse
import json

from app.db import get_connection
from app.models.schemas import IngestPayload
from app.services.ingest_service import ingest_payload
from app.services.repository import PostgresRepository


def main():
    parser = argparse.ArgumentParser(description="Manual ingest runner for MVP")
    parser.add_argument("--input", required=True, help="Path to ingestion payload json file")
    args = parser.parse_args()

    payload_data = json.loads(open(args.input, encoding="utf-8").read())
    payload = IngestPayload.model_validate(payload_data)

    with get_connection() as conn:
        repo = PostgresRepository(conn)
        result = ingest_payload(payload, repo)

    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "processed_count": result.processed_count,
                "error_count": result.error_count,
                "status": result.status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
