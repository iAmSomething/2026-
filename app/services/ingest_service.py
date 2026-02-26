from dataclasses import dataclass

from app.models.schemas import IngestPayload, PollOptionInput
from app.services.cutoff_policy import (
    ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
    has_article_source,
    parse_datetime_like,
    published_at_cutoff_reason,
)
from app.services.errors import DuplicateConflictError
from app.services.fingerprint import build_poll_fingerprint
from app.services.normalization import normalize_percentage

PARTY_INFERENCE_REVIEW_THRESHOLD = 0.8


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

    confidence = payload.get("party_inference_confidence")
    if payload.get("party_inferred") and confidence is not None:
        try:
            payload["needs_manual_review"] = float(confidence) < PARTY_INFERENCE_REVIEW_THRESHOLD
        except (TypeError, ValueError):
            payload["needs_manual_review"] = False
    else:
        payload["needs_manual_review"] = bool(payload.get("needs_manual_review", False))
    return payload


def ingest_payload(payload: IngestPayload, repo) -> IngestResult:
    run_id = repo.create_ingestion_run(payload.run_type, payload.extractor_version, payload.llm_model)
    processed_count = 0
    error_count = 0
    date_inference_failed_count = 0
    date_inference_estimated_count = 0

    for record in payload.records:
        try:
            article_source = has_article_source(
                source_channel=record.observation.source_channel,
                source_channels=record.observation.source_channels,
            )
            if article_source:
                cutoff_reason = published_at_cutoff_reason(record.article.published_at)
                if cutoff_reason != "PASS":
                    error_count += 1
                    parsed_published_at = parse_datetime_like(record.article.published_at)
                    try:
                        repo.insert_review_queue(
                            entity_type="ingest_record",
                            entity_id=record.observation.observation_key,
                            issue_type="ingestion_error",
                            review_note=(
                                "ARTICLE_PUBLISHED_AT_CUTOFF_BLOCK "
                                f"reason={cutoff_reason} "
                                f"published_at={parsed_published_at.isoformat(timespec='seconds') if parsed_published_at else None} "
                                f"cutoff={ARTICLE_PUBLISHED_AT_CUTOFF_ISO}"
                            ),
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    continue

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
            observation_payload = record.observation.model_dump()
            if not observation_payload.get("poll_fingerprint"):
                observation_payload["poll_fingerprint"] = build_poll_fingerprint(observation_payload)

            inference_mode = observation_payload.get("date_inference_mode")
            inference_confidence = observation_payload.get("date_inference_confidence")
            inference_uncertain = False
            if inference_mode == "estimated_timestamp":
                date_inference_estimated_count += 1
                inference_uncertain = True
            if inference_mode in {"strict_fail_blocked", "failed"}:
                date_inference_failed_count += 1
                inference_uncertain = True
            if inference_confidence is not None and float(inference_confidence) < 0.8:
                inference_uncertain = True

            observation_id = repo.upsert_poll_observation(
                observation_payload,
                article_id=article_id,
                ingestion_run_id=run_id,
            )

            party_inference_low_confidence: list[tuple[str, float]] = []
            for option in record.options:
                normalized_option = _normalize_option(option)
                repo.upsert_poll_option(observation_id, normalized_option)

                confidence = normalized_option.get("party_inference_confidence")
                if not normalized_option.get("party_inferred") or confidence is None:
                    continue
                try:
                    confidence_value = float(confidence)
                except (TypeError, ValueError):
                    continue
                if confidence_value < PARTY_INFERENCE_REVIEW_THRESHOLD:
                    party_inference_low_confidence.append(
                        (normalized_option.get("option_name", "unknown"), confidence_value)
                    )

            if inference_uncertain:
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="extract_error",
                        review_note=(
                            "date inference uncertainty: "
                            f"mode={inference_mode}, confidence={inference_confidence}"
                        ),
                    )
                except Exception:  # noqa: BLE001
                    pass
            if party_inference_low_confidence:
                detail = ", ".join(f"{name}:{confidence:.2f}" for name, confidence in party_inference_low_confidence)
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="party_inference_low_confidence",
                        review_note=f"party inference confidence below {PARTY_INFERENCE_REVIEW_THRESHOLD}: {detail}",
                    )
                except Exception:  # noqa: BLE001
                    pass

            processed_count += 1
        except Exception as exc:  # noqa: BLE001
            error_count += 1
            rollback = getattr(repo, "rollback", None)
            if callable(rollback):
                rollback()
            issue_type = "ingestion_error"
            if isinstance(exc, DuplicateConflictError):
                issue_type = "DUPLICATE_CONFLICT"
            try:
                repo.insert_review_queue(
                    entity_type="ingest_record",
                    entity_id=record.observation.observation_key,
                    issue_type=issue_type,
                    review_note=str(exc),
                )
            except Exception:  # noqa: BLE001
                # Keep batch loop alive even when review_queue insert fails.
                pass

    status = "success" if error_count == 0 else "partial_success"
    repo.finish_ingestion_run(run_id, status, processed_count, error_count)
    update_counters = getattr(repo, "update_ingestion_policy_counters", None)
    if callable(update_counters):
        update_counters(
            run_id,
            date_inference_failed_count=date_inference_failed_count,
            date_inference_estimated_count=date_inference_estimated_count,
        )
    return IngestResult(run_id=run_id, processed_count=processed_count, error_count=error_count, status=status)
