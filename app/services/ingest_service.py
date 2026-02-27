from dataclasses import dataclass
import re
from typing import Any

from app.config import get_settings
from app.models.schemas import IngestPayload, PollOptionInput
from app.services.cutoff_policy import (
    ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
    SURVEY_END_DATE_CUTOFF,
    has_article_source,
    parse_datetime_like,
    published_at_cutoff_reason,
    survey_end_date_cutoff_reason,
)
from app.services.candidate_token_policy import is_noise_candidate_token
from app.services.data_go_candidate import DataGoCandidateConfig, DataGoCandidateService
from app.services.errors import DuplicateConflictError
from app.services.fingerprint import build_poll_fingerprint
from app.services.ingest_input_normalization import normalize_option_type
from app.services.normalization import normalize_percentage

PARTY_INFERENCE_REVIEW_THRESHOLD = 0.8
SCENARIO_NAME_RE = re.compile(r"[가-힣]{2,6}")
SCENARIO_H2H_PAIR_RE = re.compile(
    r"([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?\s*[-~]\s*([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?"
)
SCENARIO_MULTI_SINGLE_RE = re.compile(r"다자대결[^가-힣0-9%]*([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?")
DEFAULT_SG_TYPECODES = ("3", "4", "5")
OFFICE_TYPE_TO_SG_TYPECODES = {
    "광역자치단체장": ("3", "4"),
    "기초자치단체장": ("4", "3", "5"),
}
CANDIDATE_PROFILE_FIELDS = (
    "party_name",
    "gender",
    "birth_date",
    "job",
    "career_summary",
    "election_history",
)
CANDIDATE_PROFILE_REQUIRED_FOR_REVIEW = (
    "party_name",
    "career_summary",
    "election_history",
)


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
    return is_noise_candidate_token(option_name)


def _candidate_verify_matched_key(
    *,
    source: str,
    normalized_name: str,
    candidate_id: str | None,
) -> str:
    if candidate_id:
        return f"{source}:{candidate_id}"
    if normalized_name:
        return f"{source}:{normalized_name}"
    return source


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
    candidate_id_map: dict[str, str],
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> str | None:
    option_type = option_payload.get("option_type")
    if option_type not in {"candidate", "candidate_matchup"}:
        option_payload["candidate_verified"] = True
        option_payload["candidate_verify_source"] = "manual"
        option_payload["candidate_verify_confidence"] = 1.0
        option_payload["candidate_verify_matched_key"] = None
        return None

    option_name = str(option_payload.get("option_name") or "").strip()
    normalized_name = _normalize_candidate_token(option_name)
    party_name = candidate_party_map.get(normalized_name)
    matched_candidate_id = candidate_id_map.get(normalized_name)

    if _looks_like_noise_candidate(option_name):
        option_payload["candidate_verified"] = False
        option_payload["candidate_verify_source"] = "manual"
        option_payload["candidate_verify_confidence"] = 0.0
        option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
            source="noise",
            normalized_name=normalized_name,
            candidate_id=matched_candidate_id,
        )
        option_payload["needs_manual_review"] = True
        return "CANDIDATE_TOKEN_NOISE"

    for sg_typecode in _office_type_sg_types(record.observation.office_type):
        service = _build_or_get_candidate_service(
            record=record,
            sg_typecode=sg_typecode,
            service_cache=service_cache,
        )
        if service is None:
            continue
        verified, confidence = service.verify_candidate(candidate_name=option_name, party_name=party_name)
        if verified:
            option_payload["candidate_verified"] = True
            option_payload["candidate_verify_source"] = "data_go"
            option_payload["candidate_verify_confidence"] = round(float(confidence), 3)
            option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
                source="data_go",
                normalized_name=normalized_name,
                candidate_id=matched_candidate_id,
            )
            return None

    if normalized_name in candidate_name_set:
        option_payload["candidate_verified"] = True
        option_payload["candidate_verify_source"] = "article_context"
        option_payload["candidate_verify_confidence"] = 0.68
        option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
            source="article_context",
            normalized_name=normalized_name,
            candidate_id=matched_candidate_id,
        )
        return None

    option_payload["candidate_verified"] = False
    option_payload["candidate_verify_source"] = "manual"
    option_payload["candidate_verify_confidence"] = 0.2
    option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
        source="manual",
        normalized_name=normalized_name,
        candidate_id=matched_candidate_id,
    )
    option_payload["needs_manual_review"] = True
    return "CANDIDATE_NOT_VERIFIED"


def _candidate_profile_field_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _candidate_profile_score(candidate_payload: dict[str, Any]) -> int:
    score = 0
    for field in CANDIDATE_PROFILE_FIELDS:
        if not _candidate_profile_field_missing(candidate_payload.get(field)):
            score += 1
    return score


def _normalize_candidate_profile_fields(candidate_payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate_payload)
    for field in CANDIDATE_PROFILE_FIELDS:
        normalized.setdefault(field, None)
    return normalized


def _build_or_get_candidate_service(
    *,
    record,
    sg_typecode: str,
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> DataGoCandidateService | None:
    sd_name, sgg_name = _resolve_region_names(record)
    cache_key = (
        _infer_election_id(record.observation.matchup_id),
        sd_name,
        sgg_name,
        sg_typecode,
    )
    if cache_key not in service_cache:
        service_cache[cache_key] = _build_candidate_service(record=record, sg_typecode=sg_typecode)
    return service_cache[cache_key]


def _enrich_candidate_profile(
    *,
    candidate_payload: dict[str, Any],
    record,
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> tuple[dict[str, Any], str | None]:
    enriched = _normalize_candidate_profile_fields(candidate_payload)
    candidate_name = str(enriched.get("name_ko") or "").strip()
    if _looks_like_noise_candidate(candidate_name):
        return enriched, "CANDIDATE_PROFILE_NAME_INVALID"

    best = dict(enriched)
    best_score = _candidate_profile_score(best)
    for sg_typecode in _office_type_sg_types(record.observation.office_type):
        service = _build_or_get_candidate_service(
            record=record,
            sg_typecode=sg_typecode,
            service_cache=service_cache,
        )
        if service is None:
            continue
        candidate_try = _normalize_candidate_profile_fields(service.enrich_candidate(enriched))
        score = _candidate_profile_score(candidate_try)
        if score > best_score:
            best = candidate_try
            best_score = score

    required_missing = [
        field
        for field in CANDIDATE_PROFILE_REQUIRED_FOR_REVIEW
        if _candidate_profile_field_missing(best.get(field))
    ]
    if required_missing:
        return best, "CANDIDATE_PROFILE_INCOMPLETE:" + ",".join(required_missing)
    return best, None


def _normalize_option(option: PollOptionInput) -> tuple[dict, str | None]:
    payload = option.model_dump()
    scenario_key = payload.get("scenario_key")
    if isinstance(scenario_key, str):
        scenario_key = scenario_key.strip()
    payload["scenario_key"] = scenario_key or "default"

    candidate_id = payload.get("candidate_id")
    if isinstance(candidate_id, str):
        candidate_id = candidate_id.strip() or None
    payload["candidate_id"] = candidate_id

    party_name = payload.get("party_name")
    if isinstance(party_name, str):
        party_name = party_name.strip() or None
    payload["party_name"] = party_name

    scenario_title = payload.get("scenario_title")
    if isinstance(scenario_title, str):
        scenario_title = scenario_title.strip() or None
    payload["scenario_title"] = scenario_title

    candidate_verify_matched_key = payload.get("candidate_verify_matched_key")
    if isinstance(candidate_verify_matched_key, str):
        candidate_verify_matched_key = candidate_verify_matched_key.strip() or None
    payload["candidate_verify_matched_key"] = candidate_verify_matched_key

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


def _scenario_name_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = SCENARIO_NAME_RE.search(text)
    return match.group(0) if match else text


def _scenario_value(option: dict[str, Any]) -> float:
    value_mid = option.get("value_mid")
    if value_mid is None:
        return float("-inf")
    try:
        return float(value_mid)
    except (TypeError, ValueError):
        return float("-inf")


def _extract_h2h_pairs(survey_name: str) -> list[tuple[str, float, str, float]]:
    pairs: list[tuple[str, float, str, float]] = []
    seen: set[tuple[str, float, str, float]] = set()
    for match in SCENARIO_H2H_PAIR_RE.finditer(survey_name):
        left_name = _scenario_name_token(match.group(1))
        right_name = _scenario_name_token(match.group(3))
        if not left_name or not right_name or left_name == right_name:
            continue
        try:
            left_value = float(match.group(2))
            right_value = float(match.group(4))
        except (TypeError, ValueError):
            continue
        key = (left_name, left_value, right_name, right_value)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    return pairs


def _extract_multi_anchor(survey_name: str) -> tuple[str, float] | None:
    match = SCENARIO_MULTI_SINGLE_RE.search(survey_name)
    if not match:
        return None
    name = _scenario_name_token(match.group(1))
    if not name:
        return None
    try:
        value = float(match.group(2))
    except (TypeError, ValueError):
        return None
    return name, value


def _match_candidate_index(
    *,
    options: list[dict[str, Any]],
    candidate_indexes: list[int],
    names_by_index: dict[int, str],
    name: str,
    value: float,
    exclude: set[int],
) -> int | None:
    candidates = [i for i in candidate_indexes if i not in exclude and names_by_index.get(i) == name]
    if not candidates:
        return None
    exact = [i for i in candidates if abs(_scenario_value(options[i]) - value) <= 0.15]
    if not exact:
        return None
    exact.sort(key=lambda i: abs(_scenario_value(options[i]) - value))
    return exact[0]


def _clone_candidate_option(
    *,
    options: list[dict[str, Any]],
    candidate_indexes: list[int],
    names_by_index: dict[int, str],
    name: str,
    value: float,
) -> int | None:
    template_indexes = [i for i in candidate_indexes if names_by_index.get(i) == name]
    if not template_indexes:
        return None
    template_indexes.sort(key=lambda i: abs(_scenario_value(options[i]) - value))
    row = dict(options[template_indexes[0]])
    row["option_name"] = name
    row["value_mid"] = value
    row["value_raw"] = f"{value:.1f}%"
    row["scenario_key"] = "default"
    row["scenario_type"] = None
    row["scenario_title"] = None
    options.append(row)
    return len(options) - 1


def _scenario_key_is_default(value: Any) -> bool:
    key = str(value or "").strip()
    return key in {"", "default"}


def _repair_candidate_matchup_scenarios(
    *,
    survey_name: str | None,
    options: list[dict[str, Any]],
) -> bool:
    text = str(survey_name or "")
    if "다자대결" not in text and "양자대결" not in text:
        return False

    candidate_indexes = [i for i, row in enumerate(options) if row.get("option_type") == "candidate_matchup"]
    if len(candidate_indexes) < 3:
        return False

    names_by_index = {i: _scenario_name_token(options[i].get("option_name")) for i in candidate_indexes}
    counts: dict[str, int] = {}
    for idx in candidate_indexes:
        name = names_by_index[idx]
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1

    default_candidate_indexes = [i for i in candidate_indexes if _scenario_key_is_default(options[i].get("scenario_key"))]
    explicit_candidate_indexes = [i for i in candidate_indexes if i not in default_candidate_indexes]

    # Respect explicit scenario annotations from extractor when they are complete.
    if explicit_candidate_indexes and not default_candidate_indexes:
        return False

    # Canonicalization for partially split payloads:
    # if explicit scenario rows exist together with default rows, move default rows into multi
    # and remove default candidate rows to avoid mixed/default leakage.
    if explicit_candidate_indexes and default_candidate_indexes:
        multi_key = ""
        multi_title = "다자대결"
        for idx in explicit_candidate_indexes:
            row = options[idx]
            key = str(row.get("scenario_key") or "").strip()
            scenario_type = str(row.get("scenario_type") or "").strip()
            if scenario_type == "multi_candidate" or key.startswith("multi-"):
                multi_key = key or multi_key
                title = str(row.get("scenario_title") or "").strip()
                if title:
                    multi_title = title
                break

        if not multi_key:
            anchor_name = ""
            for idx in explicit_candidate_indexes:
                key = str(options[idx].get("scenario_key") or "").strip()
                if key.startswith("h2h-"):
                    parts = [part for part in key.split("-")[1:] if part]
                    if parts:
                        anchor_name = parts[0]
                        break
            if not anchor_name:
                for idx in explicit_candidate_indexes:
                    if names_by_index.get(idx):
                        anchor_name = names_by_index[idx]
                        break
            if not anchor_name:
                for idx in default_candidate_indexes:
                    if names_by_index.get(idx):
                        anchor_name = names_by_index[idx]
                        break
            multi_key = f"multi-{anchor_name or '후보'}"

        default_name_to_row: dict[str, dict[str, Any]] = {}
        for idx in default_candidate_indexes:
            row = dict(options[idx])
            name = names_by_index.get(idx) or _scenario_name_token(row.get("option_name"))
            if not name:
                continue
            row["option_name"] = name
            existing = default_name_to_row.get(name)
            if existing is None or _scenario_value(row) > _scenario_value(existing):
                default_name_to_row[name] = row

        default_index_set = set(default_candidate_indexes)
        options[:] = [row for i, row in enumerate(options) if i not in default_index_set]

        existing_multi_names: set[str] = set()
        for row in options:
            if row.get("option_type") != "candidate_matchup":
                continue
            key = str(row.get("scenario_key") or "").strip()
            if key != multi_key:
                continue
            row["scenario_type"] = "multi_candidate"
            row["scenario_title"] = multi_title
            name = _scenario_name_token(row.get("option_name"))
            if not name:
                continue
            row["option_name"] = name
            existing_multi_names.add(name)

        changed = bool(default_index_set)
        for name, template_row in default_name_to_row.items():
            if name in existing_multi_names:
                continue
            new_row = dict(template_row)
            new_row["option_name"] = name
            new_row["scenario_key"] = multi_key
            new_row["scenario_type"] = "multi_candidate"
            new_row["scenario_title"] = multi_title
            options.append(new_row)
            existing_multi_names.add(name)
            changed = True

        return changed

    # Enhanced split: when survey text includes multiple explicit h2h pairs + multi,
    # materialize separate scenario groups (h2h/h2h/multi) even if source options are under default.
    h2h_pairs = _extract_h2h_pairs(text)
    if "다자대결" in text and len(h2h_pairs) >= 2:
        assigned = False
        used_indexes: set[int] = set()
        anchor_for_multi: str | None = None
        candidate_indexes_all = list(candidate_indexes)
        names_all = dict(names_by_index)

        for left_name, left_value, right_name, right_value in h2h_pairs:
            left_idx = _match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=left_name,
                value=left_value,
                exclude=used_indexes,
            )
            if left_idx is None:
                left_idx = _clone_candidate_option(
                    options=options,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=left_name,
                    value=left_value,
                )
                if left_idx is not None:
                    candidate_indexes_all.append(left_idx)
                    names_all[left_idx] = left_name

            right_idx = _match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=right_name,
                value=right_value,
                exclude=used_indexes,
            )
            if right_idx is None:
                right_idx = _clone_candidate_option(
                    options=options,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=right_name,
                    value=right_value,
                )
                if right_idx is not None:
                    candidate_indexes_all.append(right_idx)
                    names_all[right_idx] = right_name

            if left_idx is None or right_idx is None or left_idx == right_idx:
                continue

            scenario_key = f"h2h-{left_name}-{right_name}"
            scenario_title = f"{left_name} vs {right_name}"
            for idx, option_name, option_value in (
                (left_idx, left_name, left_value),
                (right_idx, right_name, right_value),
            ):
                row = options[idx]
                row["option_name"] = option_name
                row["value_mid"] = option_value
                row["value_raw"] = f"{option_value:.1f}%"
                row["scenario_key"] = scenario_key
                row["scenario_type"] = "head_to_head"
                row["scenario_title"] = scenario_title
                used_indexes.add(idx)
            if anchor_for_multi is None:
                anchor_for_multi = left_name
            assigned = True

        multi_indexes = [i for i in candidate_indexes_all if i not in used_indexes and names_all.get(i)]
        multi_anchor = _extract_multi_anchor(text)
        if multi_anchor is not None:
            multi_name, multi_value = multi_anchor
            multi_idx = _match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=multi_name,
                value=multi_value,
                exclude=used_indexes,
            )
            if multi_idx is None:
                multi_idx = _clone_candidate_option(
                    options=options,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=multi_name,
                    value=multi_value,
                )
                if multi_idx is not None:
                    candidate_indexes_all.append(multi_idx)
                    names_all[multi_idx] = multi_name
            if multi_idx is not None and multi_idx not in multi_indexes:
                multi_indexes.append(multi_idx)
                row = options[multi_idx]
                row["option_name"] = multi_name
                row["value_mid"] = multi_value
                row["value_raw"] = f"{multi_value:.1f}%"

        if assigned and multi_indexes:
            multi_key = f"multi-{anchor_for_multi or names_all.get(multi_indexes[0]) or '후보'}"
            for idx in multi_indexes:
                row = options[idx]
                row["scenario_key"] = multi_key
                row["scenario_type"] = "multi_candidate"
                row["scenario_title"] = "다자대결"
            return True

    duplicate_names = [name for name, cnt in counts.items() if cnt >= 2]
    if not duplicate_names:
        return False

    duplicate_names.sort(
        key=lambda name: max(_scenario_value(options[i]) for i in candidate_indexes if names_by_index[i] == name),
        reverse=True,
    )
    anchor_name = duplicate_names[0]
    anchor_indexes = [i for i in candidate_indexes if names_by_index[i] == anchor_name]
    anchor_indexes.sort(key=lambda i: _scenario_value(options[i]), reverse=True)
    anchor_h2h_idx = anchor_indexes[0]
    anchor_multi_idx = anchor_indexes[-1]

    partner_candidates = [i for i in candidate_indexes if names_by_index[i] != anchor_name]
    if not partner_candidates:
        return False
    partner_candidates.sort(key=lambda i: _scenario_value(options[i]), reverse=True)
    partner_h2h_idx = partner_candidates[0]
    partner_name = names_by_index[partner_h2h_idx] or "후보"

    h2h_key = f"h2h-{anchor_name}-{partner_name}"
    h2h_title = f"{anchor_name} vs {partner_name}"
    multi_key = f"multi-{anchor_name}"
    multi_title = "다자대결"

    for idx in (anchor_h2h_idx, partner_h2h_idx):
        row = options[idx]
        row["scenario_key"] = h2h_key
        row["scenario_type"] = "head_to_head"
        row["scenario_title"] = h2h_title

    for idx in candidate_indexes:
        if idx in {anchor_h2h_idx, partner_h2h_idx}:
            continue
        row = options[idx]
        row["scenario_key"] = multi_key
        row["scenario_type"] = "multi_candidate"
        row["scenario_title"] = multi_title

    if anchor_multi_idx not in {anchor_h2h_idx, partner_h2h_idx}:
        row = options[anchor_multi_idx]
        row["scenario_key"] = multi_key
        row["scenario_type"] = "multi_candidate"
        row["scenario_title"] = multi_title

    return True


def ingest_payload(payload: IngestPayload, repo) -> IngestResult:
    run_id = repo.create_ingestion_run(payload.run_type, payload.extractor_version, payload.llm_model)
    processed_count = 0
    error_count = 0
    date_inference_failed_count = 0
    date_inference_estimated_count = 0
    candidate_service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None] = {}
    candidate_profile_review_marked: set[str] = set()

    for record in payload.records:
        try:
            survey_end_cutoff_reason = survey_end_date_cutoff_reason(record.observation.survey_end_date)
            if survey_end_cutoff_reason != "PASS":
                error_count += 1
                try:
                    repo.insert_review_queue(
                        entity_type="ingest_record",
                        entity_id=record.observation.observation_key,
                        issue_type="ingestion_error",
                        review_note=(
                            "STALE_CYCLE_BLOCK "
                            f"reason={survey_end_cutoff_reason} "
                            f"survey_end_date={record.observation.survey_end_date} "
                            f"cutoff={SURVEY_END_DATE_CUTOFF.isoformat()}"
                        ),
                    )
                except Exception:  # noqa: BLE001
                    pass
                continue

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

            candidate_rows: list[dict[str, Any]] = []
            for candidate in record.candidates:
                candidate_payload = candidate.model_dump()
                enriched_candidate, profile_review_reason = _enrich_candidate_profile(
                    candidate_payload=candidate_payload,
                    record=record,
                    service_cache=candidate_service_cache,
                )
                repo.upsert_candidate(enriched_candidate)
                candidate_rows.append(enriched_candidate)
                candidate_id = str(enriched_candidate.get("candidate_id") or "").strip()
                if profile_review_reason and candidate_id and candidate_id not in candidate_profile_review_marked:
                    try:
                        repo.insert_review_queue(
                            entity_type="candidate",
                            entity_id=candidate_id,
                            issue_type="mapping_error",
                            review_note=f"candidate profile manual review required: {profile_review_reason}",
                        )
                        candidate_profile_review_marked.add(candidate_id)
                    except Exception:  # noqa: BLE001
                        pass

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
                _normalize_candidate_token(candidate.get("name_ko"))
                for candidate in candidate_rows
                if _normalize_candidate_token(candidate.get("name_ko"))
            }
            candidate_party_map = {
                _normalize_candidate_token(candidate.get("name_ko")): candidate.get("party_name")
                for candidate in candidate_rows
                if _normalize_candidate_token(candidate.get("name_ko"))
            }
            candidate_id_map = {
                _normalize_candidate_token(candidate.get("name_ko")): str(candidate.get("candidate_id") or "").strip()
                for candidate in candidate_rows
                if _normalize_candidate_token(candidate.get("name_ko")) and str(candidate.get("candidate_id") or "").strip()
            }

            party_inference_low_confidence: list[tuple[str, float]] = []
            option_type_manual_review: list[tuple[str, str]] = []
            candidate_verify_manual_review: list[tuple[str, str]] = []
            normalized_options: list[dict[str, Any]] = []
            classification_reason_by_id: dict[int, str | None] = {}
            for option in record.options:
                normalized_option, classification_reason = _normalize_option(option)
                normalized_options.append(normalized_option)
                classification_reason_by_id[id(normalized_option)] = classification_reason
            _repair_candidate_matchup_scenarios(
                survey_name=record.observation.survey_name,
                options=normalized_options,
            )

            for normalized_option in normalized_options:
                classification_reason = classification_reason_by_id.get(id(normalized_option))
                candidate_verify_reason = _apply_candidate_verification(
                    option_payload=normalized_option,
                    record=record,
                    candidate_name_set=candidate_name_set,
                    candidate_party_map=candidate_party_map,
                    candidate_id_map=candidate_id_map,
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
