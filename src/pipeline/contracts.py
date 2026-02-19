from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any

from app.services.normalization import NormalizedValue, normalize_percentage

from .standards import ISSUE_TAXONOMY, OFFICE_TYPE_STANDARD


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: str) -> str:
    normalized = "|".join(part.strip().lower() for part in parts if part is not None)
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def build_matchup_id(election_id: str, office_type: str, region_code: str) -> str:
    return f"{election_id}|{office_type}|{region_code}"


def build_candidate_id(candidate_name: str) -> str:
    key = "".join(candidate_name.strip().lower().split())
    return f"cand:{key}"


ARTICLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "id",
        "url",
        "title",
        "publisher",
        "collected_at",
        "raw_hash",
        "raw_text",
    ],
    "properties": {
        "id": {"type": "string"},
        "url": {"type": "string"},
        "title": {"type": "string"},
        "publisher": {"type": "string"},
        "published_at": {"type": ["string", "null"], "format": "date-time"},
        "snippet": {"type": "string"},
        "collected_at": {"type": "string", "format": "date-time"},
        "raw_hash": {"type": "string"},
        "raw_text": {"type": "string"},
    },
    "additionalProperties": False,
}


POLL_OBSERVATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "id",
        "article_id",
        "region_code",
        "office_type",
        "matchup_id",
        "margin_of_error",
    ],
    "properties": {
        "id": {"type": "string"},
        "article_id": {"type": "string"},
        "survey_name": {"type": ["string", "null"]},
        "pollster": {"type": ["string", "null"]},
        "survey_start_date": {"type": ["string", "null"], "format": "date"},
        "survey_end_date": {"type": ["string", "null"], "format": "date"},
        "sample_size": {"type": ["integer", "null"]},
        "response_rate": {"type": ["number", "null"]},
        "margin_of_error": {"type": ["number", "null"]},
        "sponsor": {"type": ["string", "null"]},
        "method": {"type": ["string", "null"]},
        "region_code": {"type": "string"},
        "office_type": {"type": "string", "enum": list(OFFICE_TYPE_STANDARD)},
        "matchup_id": {"type": "string"},
        "audience_scope": {"type": ["string", "null"], "enum": ["national", "regional", "local", None]},
        "audience_region_code": {"type": ["string", "null"]},
        "sampling_population_text": {"type": ["string", "null"]},
        "legal_completeness_score": {"type": ["number", "null"]},
        "legal_filled_count": {"type": ["integer", "null"]},
        "legal_required_count": {"type": ["integer", "null"]},
        "date_resolution": {"type": ["string", "null"]},
        "poll_fingerprint": {"type": ["string", "null"]},
        "source_channel": {"type": ["string", "null"], "enum": ["article", "nesdc", None]},
        "verified": {"type": "boolean"},
        "source_grade": {"type": ["string", "null"]},
        "ingestion_run_id": {"type": ["string", "null"]},
        "evidence_text": {"type": ["string", "null"]},
        "source_url": {"type": "string"},
    },
    "additionalProperties": False,
}


POLL_OPTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "id",
        "observation_id",
        "option_type",
        "option_name",
        "candidate_id",
        "value_raw",
        "value_min",
        "value_max",
        "value_mid",
        "is_missing",
        "margin_of_error",
    ],
    "properties": {
        "id": {"type": "string"},
        "observation_id": {"type": "string"},
        "option_type": {"type": "string"},
        "option_name": {"type": "string"},
        "candidate_id": {"type": "string"},
        "value_raw": {"type": "string"},
        "value_min": {"type": ["number", "null"]},
        "value_max": {"type": ["number", "null"]},
        "value_mid": {"type": ["number", "null"]},
        "is_missing": {"type": "boolean"},
        "margin_of_error": {"type": ["number", "null"]},
        "evidence_text": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}


REVIEW_QUEUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "id",
        "entity_type",
        "entity_id",
        "issue_type",
        "status",
        "stage",
        "error_code",
        "error_message",
        "created_at",
    ],
    "properties": {
        "id": {"type": "string"},
        "entity_type": {"type": "string"},
        "entity_id": {"type": "string"},
        "issue_type": {"type": "string", "enum": list(ISSUE_TAXONOMY)},
        "status": {"type": "string", "enum": ["pending", "approved", "rejected"]},
        "stage": {"type": "string"},
        "error_code": {"type": "string"},
        "error_message": {"type": "string"},
        "source_url": {"type": ["string", "null"]},
        "payload": {"type": "object"},
        "created_at": {"type": "string", "format": "date-time"},
    },
    "additionalProperties": False,
}


INPUT_CONTRACT_SCHEMAS = {
    "article": ARTICLE_SCHEMA,
    "poll_observation": POLL_OBSERVATION_SCHEMA,
    "poll_option": POLL_OPTION_SCHEMA,
}


@dataclass
class Article:
    id: str
    url: str
    title: str
    publisher: str
    published_at: str | None
    snippet: str
    collected_at: str
    raw_hash: str
    raw_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PollObservation:
    id: str
    article_id: str
    survey_name: str | None
    pollster: str | None
    survey_start_date: str | None
    survey_end_date: str | None
    sample_size: int | None
    response_rate: float | None
    margin_of_error: float | None
    sponsor: str | None
    method: str | None
    region_code: str
    office_type: str
    matchup_id: str
    verified: bool
    source_grade: str | None
    ingestion_run_id: str | None
    evidence_text: str | None
    source_url: str
    audience_scope: str | None = None
    audience_region_code: str | None = None
    sampling_population_text: str | None = None
    legal_completeness_score: float | None = None
    legal_filled_count: int | None = None
    legal_required_count: int | None = None
    date_resolution: str | None = None
    poll_fingerprint: str | None = None
    source_channel: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PollOption:
    id: str
    observation_id: str
    option_type: str
    option_name: str
    candidate_id: str
    value_raw: str
    value_min: float | None
    value_max: float | None
    value_mid: float | None
    is_missing: bool
    margin_of_error: float | None
    evidence_text: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewQueueItem:
    id: str
    entity_type: str
    entity_id: str
    issue_type: str
    stage: str
    error_code: str
    error_message: str
    source_url: str | None
    payload: dict[str, Any]
    status: str = "pending"
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "issue_type": self.issue_type,
            "stage": self.stage,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "source_url": self.source_url,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at,
        }


def normalize_value(raw: str | None) -> NormalizedValue:
    return normalize_percentage(raw)


def new_review_queue_item(
    *,
    entity_type: str,
    entity_id: str,
    issue_type: str,
    stage: str,
    error_code: str,
    error_message: str,
    source_url: str | None = None,
    payload: dict[str, Any] | None = None,
) -> ReviewQueueItem:
    if issue_type not in ISSUE_TAXONOMY:
        raise ValueError(f"issue_type must be one of {ISSUE_TAXONOMY}, got {issue_type}")
    created_at = utc_now_iso()
    return ReviewQueueItem(
        id=stable_id("rvq", entity_type, entity_id, issue_type, created_at),
        entity_type=entity_type,
        entity_id=entity_id,
        issue_type=issue_type,
        stage=stage,
        error_code=error_code,
        error_message=error_message,
        source_url=source_url,
        payload=payload or {},
        created_at=created_at,
    )
