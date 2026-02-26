from dataclasses import dataclass
import re
from typing import Any

from app.config import get_settings
from app.models.schemas import IngestPayload, PollOptionInput
from app.services.cutoff_policy import (
    ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
    has_article_source,
    parse_datetime_like,
    published_at_cutoff_reason,
)
from app.services.data_go_candidate import DataGoCandidateConfig, DataGoCandidateService
from app.services.errors import DuplicateConflictError
from app.services.fingerprint import build_poll_fingerprint
from app.services.ingest_input_normalization import normalize_option_type
from app.services.normalization import normalize_percentage

PARTY_INFERENCE_REVIEW_THRESHOLD = 0.8
CANDIDATE_NOISE_TOKENS = {
    "오차는",
    "응답률은",
    "지지율은",
    "오차범위",
    "표본오차",
    "응답률",
    "조사기관",
    "여론조사",
    "지지율",
}
DEFAULT_SG_TYPECODES = ("3", "4", "5")
OFFICE_TYPE_TO_SG_TYPECODES = {
    "광역자치단체장": ("3", "4"),
    "기초자치단체장": ("4", "3", "5"),
}


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


def _office_type_sg_types(office_type: str | None) -> tuple[str, ...]:
    return OFFICE_TYPE_TO_SG_TYPECODES.get(office_type or "", DEFAULT_SG_TYPECODES)


def _normalize_candidate_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    return text


def _looks_like_noise_candidate(option_name: str) -> bool:
    token = _normalize_candidate_token(option_name)
    if not token:
        return True
    if token in CANDIDATE_NOISE_TOKENS:
        return True
    if any(part in token for part in CANDIDATE_NOISE_TOKENS):
        return True
    if any(ch.isdigit() for ch in token):
        return True
    if "%" in token:
        return True
    if len(token) < 2:
        return True
    return False


def _resolve_region_names(record) -> tuple[str | None, str | None]:
    region = getattr(record, "region", None)
    if region is None:
        return None, None
    sd_name = getattr(region, "sido_name", None)
    sgg_name = getattr(region, "sigungu_name", None)
    if sgg_name == "전체":
        sgg_name = None
    return sd_name, sgg_name


def _build_candidate_service(
    *,
    record,
    sg_typecode: str,
) -> DataGoCandidateService | None:
    try:
        settings = get_settings()
    except Exception:  # noqa: BLE001
        return None

    election_id = _infer_election_id(record.observation.matchup_id)
    sd_name, sgg_name = _resolve_region_names(record)
    cfg = DataGoCandidateConfig(
        endpoint_url=settings.data_go_candidate_endpoint_url,
        service_key=settings.data_go_kr_key,
        sg_id=election_id if election_id != "unknown" else settings.data_go_candidate_sg_id,
        sg_typecode=sg_typecode,
        sd_name=sd_name or settings.data_go_candidate_sd_name,
        sgg_name=sgg_name or settings.data_go_candidate_sgg_name,
        timeout_sec=settings.data_go_candidate_timeout_sec,
        max_retries=settings.data_go_candidate_max_retries,
        cache_ttl_sec=settings.data_go_candidate_cache_ttl_sec,
        requests_per_sec=settings.data_go_candidate_requests_per_sec,
        num_of_rows=settings.data_go_candidate_num_of_rows,
    )
    service = DataGoCandidateService(cfg)
    if not service.is_configured():
        return None
    return service


def _apply_candidate_verification(
    *,
    option_payload: dict[str, Any],
    record,
    candidate_name_set: set[str],
    candidate_party_map: dict[str, str | None],
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> str | None:
    option_type = option_payload.get("option_type")
    if option_type not in {"candidate", "candidate_matchup"}:
        option_payload["candidate_verified"] = True
        option_payload["candidate_verify_source"] = "manual"
        option_payload["candidate_verify_confidence"] = 1.0
        return None

    option_name = str(option_payload.get("option_name") or "").strip()
    normalized_name = _normalize_candidate_token(option_name)
    party_name = candidate_party_map.get(normalized_name)

    if _looks_like_noise_candidate(option_name):
        option_payload["candidate_verified"] = False
        option_payload["candidate_verify_source"] = "manual"
        option_payload["candidate_verify_confidence"] = 0.0
        option_payload["needs_manual_review"] = True
        return "CANDIDATE_TOKEN_NOISE"

    sd_name, sgg_name = _resolve_region_names(record)
    for sg_typecode in _office_type_sg_types(record.observation.office_type):
        cache_key = (
            _infer_election_id(record.observation.matchup_id),
            sd_name,
            sgg_name,
            sg_typecode,
        )
        service = service_cache.get(cache_key)
        if cache_key not in service_cache:
            service = _build_candidate_service(record=record, sg_typecode=sg_typecode)
            service_cache[cache_key] = service
        if service is None:
            continue
        verified, confidence = service.verify_candidate(candidate_name=option_name, party_name=party_name)
        if verified:
            option_payload["candidate_verified"] = True
            option_payload["candidate_verify_source"] = "data_go"
            option_payload["candidate_verify_confidence"] = round(float(confidence), 3)
            return None

    if normalized_name in candidate_name_set:
        option_payload["candidate_verified"] = True
        option_payload["candidate_verify_source"] = "article_context"
        option_payload["candidate_verify_confidence"] = 0.68
        return None

    option_payload["candidate_verified"] = False
    option_payload["candidate_verify_source"] = "manual"
    option_payload["candidate_verify_confidence"] = 0.2
    option_payload["needs_manual_review"] = True
    return "CANDIDATE_NOT_VERIFIED"


def _normalize_option(option: PollOptionInput) -> tuple[dict, str | None]:
    payload = option.model_dump()
    normalized_option_type, classification_needs_review, classification_reason = normalize_option_type(
        payload.get("option_type"),
        payload.get("option_name"),
    )
    payload["option_type"] = normalized_option_type

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

    if classification_needs_review:
        payload["needs_manual_review"] = True
    return payload, classification_reason


def ingest_payload(payload: IngestPayload, repo) -> IngestResult:
    run_id = repo.create_ingestion_run(payload.run_type, payload.extractor_version, payload.llm_model)
    processed_count = 0
    error_count = 0
    date_inference_failed_count = 0
    date_inference_estimated_count = 0
    candidate_service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None] = {}

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

            candidate_name_set = {
                _normalize_candidate_token(candidate.name_ko)
                for candidate in record.candidates
                if _normalize_candidate_token(candidate.name_ko)
            }
            candidate_party_map = {
                _normalize_candidate_token(candidate.name_ko): candidate.party_name
                for candidate in record.candidates
                if _normalize_candidate_token(candidate.name_ko)
            }

            party_inference_low_confidence: list[tuple[str, float]] = []
            option_type_manual_review: list[tuple[str, str]] = []
            candidate_verify_manual_review: list[tuple[str, str]] = []
            for option in record.options:
                normalized_option, classification_reason = _normalize_option(option)
                candidate_verify_reason = _apply_candidate_verification(
                    option_payload=normalized_option,
                    record=record,
                    candidate_name_set=candidate_name_set,
                    candidate_party_map=candidate_party_map,
                    service_cache=candidate_service_cache,
                )
                repo.upsert_poll_option(observation_id, normalized_option)
                if classification_reason:
                    option_type_manual_review.append(
                        (normalized_option.get("option_name", "unknown"), classification_reason)
                    )
                if candidate_verify_reason:
                    candidate_verify_manual_review.append(
                        (normalized_option.get("option_name", "unknown"), candidate_verify_reason)
                    )

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
            if option_type_manual_review:
                detail = ", ".join(f"{name}:{reason}" for name, reason in option_type_manual_review)
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="mapping_error",
                        review_note=f"option_type manual review required: {detail}",
                    )
                except Exception:  # noqa: BLE001
                    pass
            if candidate_verify_manual_review:
                detail = ", ".join(f"{name}:{reason}" for name, reason in candidate_verify_manual_review)
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="mapping_error",
                        review_note=f"candidate verification manual review required: {detail}",
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
