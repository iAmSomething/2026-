from dataclasses import dataclass

from app.models.schemas import IngestPayload, PollOptionInput
from app.services.normalization import normalize_percentage


@dataclass
class IngestResult:
    run_id: int
    processed_count: int
    error_count: int
    status: str


def _infer_election_id(matchup_id: str) -> str:
    if "|" in matchup_id:
        return matchup_id.split("|", 1)[0]
    if ":" in matchup_id:
        return matchup_id.split(":", 1)[0]
    return "unknown"


def _normalize_option(option: PollOptionInput) -> dict:
    payload = option.model_dump()
    if payload["value_min"] is None and payload["value_max"] is None and payload["value_mid"] is None:
        normalized = normalize_percentage(payload.get("value_raw"))
        payload["value_min"] = normalized.value_min
        payload["value_max"] = normalized.value_max
        payload["value_mid"] = normalized.value_mid
        payload["is_missing"] = normalized.is_missing
    return payload


def ingest_payload(payload: IngestPayload, repo) -> IngestResult:
    run_id = repo.create_ingestion_run(payload.run_type, payload.extractor_version, payload.llm_model)
    processed_count = 0
    error_count = 0

    for record in payload.records:
        try:
            if record.region:
                repo.upsert_region(record.region.model_dump())

            repo.upsert_matchup(
                {
                    "matchup_id": record.observation.matchup_id,
                    "election_id": _infer_election_id(record.observation.matchup_id),
                    "office_type": record.observation.office_type,
                    "region_code": record.observation.region_code,
                    "title": record.observation.survey_name,
                    "is_active": True,
                }
            )

            for candidate in record.candidates:
                repo.upsert_candidate(candidate.model_dump())

            article_id = repo.upsert_article(record.article.model_dump())
            observation_id = repo.upsert_poll_observation(
                record.observation.model_dump(),
                article_id=article_id,
                ingestion_run_id=run_id,
            )

            for option in record.options:
                repo.upsert_poll_option(observation_id, _normalize_option(option))

            processed_count += 1
        except Exception as exc:  # noqa: BLE001
            error_count += 1
            rollback = getattr(repo, "rollback", None)
            if callable(rollback):
                rollback()
            try:
                repo.insert_review_queue(
                    entity_type="ingest_record",
                    entity_id=record.observation.observation_key,
                    issue_type="ingestion_error",
                    review_note=str(exc),
                )
            except Exception:  # noqa: BLE001
                # Keep batch loop alive even when review_queue insert fails.
                pass

    status = "success" if error_count == 0 else "partial_success"
    repo.finish_ingestion_run(run_id, status, processed_count, error_count)
    return IngestResult(run_id=run_id, processed_count=processed_count, error_count=error_count, status=status)
