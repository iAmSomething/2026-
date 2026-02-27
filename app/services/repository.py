import copy
import json
import re
import time
from datetime import date
from threading import Lock
from typing import Any

from app.config import get_settings
from app.services.candidate_token_policy import is_noise_candidate_token
from app.services.errors import DuplicateConflictError
from app.services.fingerprint import merge_observation_by_priority

def _is_noise_candidate_option(option_name: str | None, candidate_id: str | None) -> bool:
    _ = candidate_id
    return is_noise_candidate_token(option_name)


def _is_low_quality_manual_candidate_option(row: dict) -> bool:
    verify_source = str(row.get("candidate_verify_source") or "").strip().lower()
    if verify_source != "manual":
        return False

    candidate_id = str(row.get("candidate_id") or "").strip()
    if not candidate_id.startswith("cand:"):
        return False

    option_name = str(row.get("option_name") or "").strip()
    if not option_name:
        return True

    party_name = str(row.get("party_name") or "").strip()
    if party_name and party_name != "미확정(검수대기)":
        return False

    matched_key = str(row.get("candidate_verify_matched_key") or "").strip()
    candidate_name_hint = candidate_id.split(":", 1)[1].strip() if ":" in candidate_id else candidate_id
    if matched_key and matched_key not in {option_name, candidate_name_hint}:
        return False

    confidence_value = row.get("candidate_verify_confidence")
    try:
        confidence = float(confidence_value)
    except (TypeError, ValueError):
        confidence = 1.0
    return confidence >= 0.95


_API_READ_CACHE: dict[str, tuple[float, Any]] = {}
_API_READ_CACHE_LOCK = Lock()


def clear_api_read_cache() -> None:
    with _API_READ_CACHE_LOCK:
        _API_READ_CACHE.clear()


def _api_read_cache_ttl_sec() -> float:
    try:
        ttl = float(get_settings().api_read_cache_ttl_sec)
    except Exception:  # noqa: BLE001
        return 0.0
    return max(ttl, 0.0)


def _api_read_cache_get(cache_key: str) -> Any | None:
    ttl = _api_read_cache_ttl_sec()
    if ttl <= 0:
        return None
    now = time.monotonic()
    with _API_READ_CACHE_LOCK:
        item = _API_READ_CACHE.get(cache_key)
        if item is None:
            return None
        expire_at, payload = item
        if expire_at <= now:
            _API_READ_CACHE.pop(cache_key, None)
            return None
        return copy.deepcopy(payload)


def _api_read_cache_set(cache_key: str, payload: Any) -> None:
    ttl = _api_read_cache_ttl_sec()
    if ttl <= 0:
        return
    with _API_READ_CACHE_LOCK:
        _API_READ_CACHE[cache_key] = (time.monotonic() + ttl, copy.deepcopy(payload))


def _api_read_cache_key(*parts: object) -> str:
    normalized: list[str] = []
    for part in parts:
        if isinstance(part, date):
            normalized.append(part.isoformat())
        else:
            normalized.append(str(part))
    return "|".join(normalized)


class PostgresRepository:
    def __init__(self, conn):
        self.conn = conn

    def rollback(self) -> None:
        self.conn.rollback()

    def _invalidate_api_read_cache(self) -> None:
        clear_api_read_cache()

    def create_ingestion_run(self, run_type: str, extractor_version: str, llm_model: str | None) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_runs (run_type, status, extractor_version, llm_model)
                VALUES (%s, 'running', %s, %s)
                RETURNING id
                """,
                (run_type, extractor_version, llm_model),
            )
            run_id = cur.fetchone()["id"]
        self.conn.commit()
        self._invalidate_api_read_cache()
        return run_id

    def finish_ingestion_run(self, run_id: int, status: str, processed_count: int, error_count: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_runs
                SET status=%s, processed_count=%s, error_count=%s, ended_at=NOW()
                WHERE id=%s
                """,
                (status, processed_count, error_count, run_id),
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def update_ingestion_policy_counters(
        self,
        run_id: int,
        *,
        date_inference_failed_count: int = 0,
        date_inference_estimated_count: int = 0,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_runs
                SET date_inference_failed_count=%s,
                    date_inference_estimated_count=%s
                WHERE id=%s
                """,
                (date_inference_failed_count, date_inference_estimated_count, run_id),
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def upsert_region(self, region: dict) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO regions (region_code, sido_name, sigungu_name, admin_level, parent_region_code)
                VALUES (%(region_code)s, %(sido_name)s, %(sigungu_name)s, %(admin_level)s, %(parent_region_code)s)
                ON CONFLICT (region_code) DO UPDATE
                SET sido_name=EXCLUDED.sido_name,
                    sigungu_name=EXCLUDED.sigungu_name,
                    admin_level=EXCLUDED.admin_level,
                    parent_region_code=EXCLUDED.parent_region_code,
                    updated_at=NOW()
                """,
                region,
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def upsert_candidate(self, candidate: dict) -> None:
        payload = dict(candidate)
        payload.setdefault("party_inferred", False)
        payload.setdefault("party_inference_source", None)
        payload.setdefault("party_inference_confidence", None)
        payload.setdefault("source_channel", "article")
        if payload.get("source_channels") in (None, []):
            payload["source_channels"] = [payload["source_channel"]]
        payload.setdefault("official_release_at", None)
        payload.setdefault("article_published_at", None)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidates (
                    candidate_id, name_ko, party_name,
                    party_inferred, party_inference_source, party_inference_confidence,
                    source_channel, source_channels, official_release_at, article_published_at,
                    gender, birth_date, job, profile_updated_at
                )
                VALUES (
                    %(candidate_id)s, %(name_ko)s, %(party_name)s,
                    %(party_inferred)s, %(party_inference_source)s, %(party_inference_confidence)s,
                    %(source_channel)s, %(source_channels)s, %(official_release_at)s, %(article_published_at)s,
                    %(gender)s, %(birth_date)s, %(job)s, NOW()
                )
                ON CONFLICT (candidate_id) DO UPDATE
                SET name_ko=EXCLUDED.name_ko,
                    party_name=EXCLUDED.party_name,
                    party_inferred=EXCLUDED.party_inferred,
                    party_inference_source=EXCLUDED.party_inference_source,
                    party_inference_confidence=EXCLUDED.party_inference_confidence,
                    source_channel=CASE
                        WHEN candidates.source_channel = 'nesdc' OR EXCLUDED.source_channel = 'nesdc'
                            THEN 'nesdc'
                        ELSE EXCLUDED.source_channel
                    END,
                    source_channels=CASE
                        WHEN candidates.source_channels IS NULL THEN EXCLUDED.source_channels
                        WHEN EXCLUDED.source_channels IS NULL THEN candidates.source_channels
                        ELSE ARRAY(
                            SELECT DISTINCT unnest(candidates.source_channels || EXCLUDED.source_channels)
                        )
                    END,
                    official_release_at=COALESCE(candidates.official_release_at, EXCLUDED.official_release_at),
                    article_published_at=COALESCE(EXCLUDED.article_published_at, candidates.article_published_at),
                    gender=EXCLUDED.gender,
                    birth_date=EXCLUDED.birth_date,
                    job=EXCLUDED.job,
                    profile_updated_at=NOW()
                """,
                payload,
            )
            cur.execute(
                """
                INSERT INTO candidate_profiles (candidate_id, career_summary, election_history, source_type, source_url)
                VALUES (%(candidate_id)s, %(career_summary)s, %(election_history)s, 'manual', NULL)
                ON CONFLICT (candidate_id) DO UPDATE
                SET career_summary=EXCLUDED.career_summary,
                    election_history=EXCLUDED.election_history,
                    updated_at=NOW()
                """,
                payload,
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def upsert_article(self, article: dict) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO articles (url, title, publisher, published_at, raw_text, raw_hash)
                VALUES (%(url)s, %(title)s, %(publisher)s, %(published_at)s, %(raw_text)s, %(raw_hash)s)
                ON CONFLICT (url) DO UPDATE
                SET title=EXCLUDED.title,
                    publisher=EXCLUDED.publisher,
                    published_at=EXCLUDED.published_at,
                    raw_text=EXCLUDED.raw_text,
                    raw_hash=EXCLUDED.raw_hash,
                    updated_at=NOW()
                RETURNING id
                """,
                article,
            )
            article_id = cur.fetchone()["id"]
        self.conn.commit()
        self._invalidate_api_read_cache()
        return article_id

    def _find_observation_by_fingerprint(self, poll_fingerprint: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, observation_key, article_id, survey_name, pollster, sponsor,
                    survey_start_date, survey_end_date, confidence_level, sample_size, response_rate,
                    margin_of_error, method, region_code, office_type, matchup_id,
                    audience_scope, audience_region_code, sampling_population_text,
                    legal_completeness_score, legal_filled_count, legal_required_count,
                    date_resolution, date_inference_mode, date_inference_confidence, official_release_at,
                    poll_fingerprint, source_channel, source_channels,
                    verified, source_grade, ingestion_run_id
                FROM poll_observations
                WHERE poll_fingerprint = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (poll_fingerprint,),
            )
            return cur.fetchone()

    def _prepare_observation_payload(self, observation: dict, article_id: int, ingestion_run_id: int) -> dict:
        payload = dict(observation)
        payload["article_id"] = article_id
        payload["ingestion_run_id"] = ingestion_run_id
        payload.setdefault("audience_scope", None)
        payload.setdefault("audience_region_code", None)
        payload.setdefault("sampling_population_text", None)
        payload.setdefault("confidence_level", None)
        payload.setdefault("legal_completeness_score", None)
        payload.setdefault("legal_filled_count", None)
        payload.setdefault("legal_required_count", None)
        payload.setdefault("date_resolution", None)
        payload.setdefault("date_inference_mode", None)
        payload.setdefault("date_inference_confidence", None)
        payload.setdefault("official_release_at", None)
        payload.setdefault("poll_fingerprint", None)
        payload.setdefault("source_channel", "article")
        if payload.get("source_channels") in (None, []):
            payload["source_channels"] = [payload["source_channel"]]
        payload.setdefault("sponsor", None)
        payload.setdefault("method", None)
        return payload

    def upsert_poll_observation(self, observation: dict, article_id: int, ingestion_run_id: int) -> int:
        payload = self._prepare_observation_payload(observation, article_id, ingestion_run_id)
        if payload["poll_fingerprint"]:
            existing = self._find_observation_by_fingerprint(payload["poll_fingerprint"])
            if existing:
                payload = merge_observation_by_priority(existing=existing, incoming=payload)
                if not payload.get("observation_key"):
                    raise DuplicateConflictError("DUPLICATE_CONFLICT missing observation_key after merge")

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poll_observations (
                    observation_key, article_id, survey_name, pollster,
                    survey_start_date, survey_end_date, confidence_level, sample_size,
                    response_rate, margin_of_error, sponsor, method, region_code,
                    office_type, matchup_id, audience_scope, audience_region_code,
                    sampling_population_text, legal_completeness_score,
                    legal_filled_count, legal_required_count, date_resolution,
                    date_inference_mode, date_inference_confidence, official_release_at,
                    poll_fingerprint, source_channel, source_channels,
                    verified, source_grade,
                    ingestion_run_id
                )
                VALUES (
                    %(observation_key)s, %(article_id)s, %(survey_name)s, %(pollster)s,
                    %(survey_start_date)s, %(survey_end_date)s, %(confidence_level)s, %(sample_size)s,
                    %(response_rate)s, %(margin_of_error)s, %(sponsor)s, %(method)s, %(region_code)s,
                    %(office_type)s, %(matchup_id)s, %(audience_scope)s, %(audience_region_code)s,
                    %(sampling_population_text)s, %(legal_completeness_score)s,
                    %(legal_filled_count)s, %(legal_required_count)s, %(date_resolution)s,
                    %(date_inference_mode)s, %(date_inference_confidence)s, %(official_release_at)s,
                    %(poll_fingerprint)s, %(source_channel)s, %(source_channels)s,
                    %(verified)s, %(source_grade)s,
                    %(ingestion_run_id)s
                )
                ON CONFLICT (observation_key) DO UPDATE
                SET article_id=EXCLUDED.article_id,
                    survey_name=EXCLUDED.survey_name,
                    pollster=EXCLUDED.pollster,
                    survey_start_date=EXCLUDED.survey_start_date,
                    survey_end_date=EXCLUDED.survey_end_date,
                    confidence_level=EXCLUDED.confidence_level,
                    sample_size=EXCLUDED.sample_size,
                    response_rate=EXCLUDED.response_rate,
                    margin_of_error=EXCLUDED.margin_of_error,
                    sponsor=EXCLUDED.sponsor,
                    method=EXCLUDED.method,
                    region_code=EXCLUDED.region_code,
                    office_type=EXCLUDED.office_type,
                    matchup_id=EXCLUDED.matchup_id,
                    audience_scope=EXCLUDED.audience_scope,
                    audience_region_code=EXCLUDED.audience_region_code,
                    sampling_population_text=EXCLUDED.sampling_population_text,
                    legal_completeness_score=EXCLUDED.legal_completeness_score,
                    legal_filled_count=EXCLUDED.legal_filled_count,
                    legal_required_count=EXCLUDED.legal_required_count,
                    date_resolution=EXCLUDED.date_resolution,
                    date_inference_mode=EXCLUDED.date_inference_mode,
                    date_inference_confidence=EXCLUDED.date_inference_confidence,
                    official_release_at=COALESCE(poll_observations.official_release_at, EXCLUDED.official_release_at),
                    poll_fingerprint=COALESCE(poll_observations.poll_fingerprint, EXCLUDED.poll_fingerprint),
                    source_channel=CASE
                        WHEN poll_observations.source_channel = 'nesdc' OR EXCLUDED.source_channel = 'nesdc'
                            THEN 'nesdc'
                        ELSE EXCLUDED.source_channel
                    END,
                    source_channels=CASE
                        WHEN poll_observations.source_channels IS NULL THEN EXCLUDED.source_channels
                        WHEN EXCLUDED.source_channels IS NULL THEN poll_observations.source_channels
                        ELSE ARRAY(
                            SELECT DISTINCT unnest(
                                poll_observations.source_channels || EXCLUDED.source_channels
                            )
                        )
                    END,
                    verified=EXCLUDED.verified,
                    source_grade=EXCLUDED.source_grade,
                    ingestion_run_id=EXCLUDED.ingestion_run_id,
                    updated_at=NOW()
                RETURNING id
                """,
                payload,
            )
            observation_id = cur.fetchone()["id"]
        self.conn.commit()
        self._invalidate_api_read_cache()
        return observation_id

    def upsert_matchup(self, matchup: dict) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO matchups (matchup_id, election_id, office_type, region_code, title, is_active)
                VALUES (
                    %(matchup_id)s, %(election_id)s, %(office_type)s,
                    %(region_code)s, %(title)s, %(is_active)s
                )
                ON CONFLICT (matchup_id) DO UPDATE
                SET election_id=EXCLUDED.election_id,
                    office_type=EXCLUDED.office_type,
                    region_code=EXCLUDED.region_code,
                    title=EXCLUDED.title,
                    is_active=EXCLUDED.is_active,
                    updated_at=NOW()
                """,
                matchup,
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def upsert_poll_option(self, observation_id: int, option: dict) -> None:
        payload = dict(option)
        payload["observation_id"] = observation_id
        candidate_id = payload.get("candidate_id")
        if isinstance(candidate_id, str):
            candidate_id = candidate_id.strip() or None
        payload["candidate_id"] = candidate_id

        party_name = payload.get("party_name")
        if isinstance(party_name, str):
            party_name = party_name.strip() or None
        payload["party_name"] = party_name

        scenario_key = payload.get("scenario_key")
        if isinstance(scenario_key, str):
            scenario_key = scenario_key.strip()
        payload["scenario_key"] = scenario_key or "default"
        payload.setdefault("scenario_type", None)
        payload.setdefault("scenario_title", None)
        payload.setdefault("party_inferred", False)
        payload.setdefault("party_inference_source", None)
        payload.setdefault("party_inference_confidence", None)
        payload.setdefault("party_inference_evidence", None)
        if isinstance(payload.get("party_inference_evidence"), str):
            payload["party_inference_evidence"] = payload["party_inference_evidence"].strip() or None
        payload.setdefault("candidate_verified", True)
        payload.setdefault("candidate_verify_source", "manual")
        payload.setdefault("candidate_verify_confidence", None)
        payload.setdefault("candidate_verify_matched_key", None)
        if payload.get("candidate_verify_confidence") is None:
            payload["candidate_verify_confidence"] = 1.0 if payload.get("candidate_verified") else 0.0
        if isinstance(payload.get("candidate_verify_matched_key"), str):
            payload["candidate_verify_matched_key"] = payload["candidate_verify_matched_key"].strip() or None
        payload.setdefault("needs_manual_review", False)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poll_options (
                    observation_id, option_type, option_name,
                    candidate_id, party_name, scenario_key, scenario_type, scenario_title,
                    value_raw, value_min, value_max, value_mid, is_missing,
                    party_inferred, party_inference_source, party_inference_confidence, party_inference_evidence,
                    candidate_verified, candidate_verify_source, candidate_verify_confidence, candidate_verify_matched_key,
                    needs_manual_review
                )
                VALUES (
                    %(observation_id)s, %(option_type)s, %(option_name)s,
                    %(candidate_id)s, %(party_name)s, %(scenario_key)s, %(scenario_type)s, %(scenario_title)s,
                    %(value_raw)s, %(value_min)s, %(value_max)s, %(value_mid)s, %(is_missing)s,
                    %(party_inferred)s, %(party_inference_source)s, %(party_inference_confidence)s, %(party_inference_evidence)s,
                    %(candidate_verified)s, %(candidate_verify_source)s, %(candidate_verify_confidence)s, %(candidate_verify_matched_key)s,
                    %(needs_manual_review)s
                )
                ON CONFLICT (observation_id, option_type, option_name, scenario_key) DO UPDATE
                SET candidate_id=COALESCE(EXCLUDED.candidate_id, poll_options.candidate_id),
                    party_name=COALESCE(EXCLUDED.party_name, poll_options.party_name),
                    scenario_type=COALESCE(EXCLUDED.scenario_type, poll_options.scenario_type),
                    scenario_title=COALESCE(EXCLUDED.scenario_title, poll_options.scenario_title),
                    value_raw=EXCLUDED.value_raw,
                    value_min=EXCLUDED.value_min,
                    value_max=EXCLUDED.value_max,
                    value_mid=EXCLUDED.value_mid,
                    is_missing=EXCLUDED.is_missing,
                    party_inferred=EXCLUDED.party_inferred,
                    party_inference_source=EXCLUDED.party_inference_source,
                    party_inference_confidence=EXCLUDED.party_inference_confidence,
                    party_inference_evidence=COALESCE(EXCLUDED.party_inference_evidence, poll_options.party_inference_evidence),
                    candidate_verified=EXCLUDED.candidate_verified,
                    candidate_verify_source=COALESCE(EXCLUDED.candidate_verify_source, poll_options.candidate_verify_source, 'manual'),
                    candidate_verify_confidence=COALESCE(EXCLUDED.candidate_verify_confidence, poll_options.candidate_verify_confidence),
                    candidate_verify_matched_key=COALESCE(
                        EXCLUDED.candidate_verify_matched_key,
                        poll_options.candidate_verify_matched_key,
                        EXCLUDED.candidate_id,
                        EXCLUDED.option_name
                    ),
                    needs_manual_review=EXCLUDED.needs_manual_review,
                    updated_at=NOW()
                """,
                payload,
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def delete_candidate_default_poll_options(self, observation_id: int) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM poll_options
                WHERE observation_id = %s
                  AND option_type = 'candidate_matchup'
                  AND scenario_key = 'default'
                """,
                (observation_id,),
            )
            deleted = int(cur.rowcount or 0)
        self.conn.commit()
        self._invalidate_api_read_cache()
        return deleted

    def fetch_candidate_default_poll_options(self, observation_id: int) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    option_name,
                    value_raw,
                    value_min,
                    value_max,
                    value_mid,
                    is_missing
                FROM poll_options
                WHERE observation_id = %s
                  AND option_type = 'candidate_matchup'
                  AND scenario_key = 'default'
                ORDER BY option_name
                """,
                (observation_id,),
            )
            rows = cur.fetchall() or []
        return [dict(row) for row in rows]

    def insert_review_queue(self, entity_type: str, entity_id: str, issue_type: str, review_note: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO review_queue (entity_type, entity_id, issue_type, status, review_note)
                VALUES (%s, %s, %s, 'pending', %s)
                """,
                (entity_type, entity_id, issue_type, review_note),
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def ensure_review_queue_pending(self, entity_type: str, entity_id: str, issue_type: str, review_note: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM review_queue
                WHERE entity_type = %s
                  AND entity_id = %s
                  AND issue_type = %s
                  AND status IN ('pending', 'in_progress')
                LIMIT 1
                """,
                (entity_type, entity_id, issue_type),
            )
            if cur.fetchone():
                return False
            cur.execute(
                """
                INSERT INTO review_queue (entity_type, entity_id, issue_type, status, review_note)
                VALUES (%s, %s, %s, 'pending', %s)
                """,
                (entity_type, entity_id, issue_type, review_note),
            )
        self.conn.commit()
        self._invalidate_api_read_cache()
        return True

    def count_review_queue(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*)::int AS count FROM review_queue")
            row = cur.fetchone() or {}
        return int(row.get("count", 0) or 0)

    def fetch_dashboard_summary(self, as_of: date | None):
        cache_key = _api_read_cache_key("dashboard_summary", as_of or "none")
        cached = _api_read_cache_get(cache_key)
        if cached is not None:
            return cached

        params = []
        as_of_filter = ""
        if as_of is not None:
            as_of_filter = "AND o.survey_end_date <= %s"
            params.append(as_of)
        query = f"""
            WITH ranked_latest AS (
                SELECT
                    po.option_type,
                    po.option_name,
                    o.id AS observation_id,
                    o.audience_scope,
                    ROW_NUMBER() OVER (
                        PARTITION BY po.option_type, po.option_name, o.audience_scope
                        ORDER BY
                            CASE
                                WHEN (
                                    o.source_channel = 'nesdc'
                                    OR 'nesdc' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                                ) THEN 1
                                ELSE 0
                            END DESC,
                            CASE UPPER(COALESCE(o.source_grade, ''))
                                WHEN 'S' THEN 5
                                WHEN 'A' THEN 4
                                WHEN 'B' THEN 3
                                WHEN 'C' THEN 2
                                WHEN 'D' THEN 1
                                ELSE 0
                            END DESC,
                            COALESCE(o.official_release_at, a.published_at) DESC NULLS LAST,
                            o.updated_at DESC NULLS LAST,
                            o.id DESC
                    ) AS rn
                FROM poll_options po
                JOIN poll_observations o ON o.id = po.observation_id
                LEFT JOIN articles a ON a.id = o.article_id
                WHERE po.option_type IN (
                    'party_support',
                    'president_job_approval',
                    'election_frame',
                    'presidential_approval'
                )
                  AND o.verified = TRUE
                  {as_of_filter}
            )
            SELECT
                po.option_type,
                po.option_name,
                po.value_mid,
                o.pollster,
                o.survey_end_date,
                o.source_grade,
                o.audience_scope,
                o.audience_region_code,
                o.updated_at AS observation_updated_at,
                o.official_release_at,
                a.published_at AS article_published_at,
                o.source_channel,
                COALESCE(o.source_channels, CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END) AS source_channels,
                o.legal_completeness_score,
                o.legal_filled_count,
                o.legal_required_count,
                o.verified
            FROM poll_options po
            JOIN poll_observations o ON o.id = po.observation_id
            LEFT JOIN articles a ON a.id = o.article_id
            JOIN ranked_latest rl
              ON rl.option_type = po.option_type
             AND rl.option_name = po.option_name
             AND rl.observation_id = o.id
             AND rl.audience_scope IS NOT DISTINCT FROM o.audience_scope
            WHERE po.option_type IN (
                'party_support',
                'president_job_approval',
                'election_frame',
                'presidential_approval'
            )
              AND rl.rn = 1
            ORDER BY po.option_type, po.option_name
        """

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = [dict(row) for row in (cur.fetchall() or [])]

        _api_read_cache_set(cache_key, rows)
        return rows

    def fetch_trends(
        self,
        *,
        metric: str,
        scope: str,
        region_code: str | None,
        days: int,
    ) -> list[dict]:
        cache_key = _api_read_cache_key("trends", metric, scope, region_code or "none", days)
        cached = _api_read_cache_get(cache_key)
        if cached is not None:
            return cached

        params: list[object] = [metric, scope, days]
        region_filter = ""
        if scope in {"regional", "local"} and region_code:
            region_filter = "AND COALESCE(o.audience_region_code, o.region_code) = %s"
            params.append(region_code)

        query = f"""
            SELECT
                po.option_name,
                po.value_mid,
                o.pollster,
                o.survey_end_date,
                o.source_grade,
                o.audience_scope,
                o.audience_region_code,
                o.updated_at AS observation_updated_at,
                o.official_release_at,
                a.published_at AS article_published_at,
                o.source_channel,
                COALESCE(
                    o.source_channels,
                    CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END
                ) AS source_channels
            FROM poll_options po
            JOIN poll_observations o ON o.id = po.observation_id
            LEFT JOIN articles a ON a.id = o.article_id
            WHERE po.option_type = %s
              AND o.verified = TRUE
              AND o.audience_scope = %s
              AND o.survey_end_date IS NOT NULL
              AND o.survey_end_date >= CURRENT_DATE - (%s::int - 1)
              {region_filter}
            ORDER BY o.survey_end_date ASC, po.option_name, o.id DESC
        """

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = [dict(row) for row in (cur.fetchall() or [])]

        _api_read_cache_set(cache_key, rows)
        return rows

    def fetch_dashboard_map_latest(self, as_of: date | None, limit: int = 100):
        cache_key = _api_read_cache_key("dashboard_map_latest", as_of or "none", limit)
        cached = _api_read_cache_get(cache_key)
        if cached is not None:
            return cached

        params = []
        as_of_filter = ""
        if as_of is not None:
            as_of_filter = "AND o.survey_end_date <= %s"
            params.append(as_of)
        params.append(limit)

        query = f"""
            WITH ranked AS (
                SELECT
                    o.region_code,
                    o.office_type,
                    o.matchup_id,
                    po.option_name,
                    po.value_mid,
                    o.survey_end_date,
                    o.audience_scope,
                    o.audience_region_code,
                    o.updated_at AS observation_updated_at,
                    o.official_release_at,
                    a.published_at AS article_published_at,
                    a.title AS article_title,
                    o.source_grade,
                    o.legal_completeness_score,
                    o.legal_filled_count,
                    o.legal_required_count,
                    o.source_channel,
                    COALESCE(
                        o.source_channels,
                        CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END
                    ) AS source_channels,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.region_code, o.office_type, o.audience_scope
                        ORDER BY
                            o.survey_end_date DESC NULLS LAST,
                            CASE
                                WHEN (
                                    o.source_channel = 'nesdc'
                                    OR 'nesdc' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                                ) AND (
                                    o.source_channel = 'article'
                                    OR 'article' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                                ) THEN 3
                                WHEN (
                                    o.source_channel = 'nesdc'
                                    OR 'nesdc' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                                ) THEN 2
                                WHEN (
                                    o.source_channel = 'article'
                                    OR 'article' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))
                                ) THEN 1
                                ELSE 0
                            END DESC,
                            COALESCE(o.legal_completeness_score, 0.0) DESC,
                            COALESCE(o.official_release_at, a.published_at, o.updated_at) DESC NULLS LAST,
                            o.id DESC,
                            po.value_mid DESC NULLS LAST,
                            po.option_name
                    ) AS rn
                FROM poll_observations o
                JOIN poll_options po ON po.observation_id = o.id
                LEFT JOIN articles a ON a.id = o.article_id
                WHERE o.verified = TRUE
                  AND po.option_type = 'candidate_matchup'
                  AND COALESCE(po.candidate_verified, TRUE) = TRUE
                  AND po.value_mid IS NOT NULL
                  {as_of_filter}
            ),
            scoped_rank AS (
                SELECT
                    r.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.region_code, r.office_type
                        ORDER BY
                            CASE r.audience_scope
                                WHEN 'regional' THEN 3
                                WHEN 'local' THEN 2
                                WHEN 'national' THEN 1
                                ELSE 0
                            END DESC,
                            r.survey_end_date DESC NULLS LAST,
                            COALESCE(r.official_release_at, r.article_published_at, r.observation_updated_at) DESC NULLS LAST,
                            r.value_mid DESC NULLS LAST,
                            r.option_name
                    ) AS scope_rn
                FROM ranked r
                WHERE r.rn = 1
            )
            SELECT
                r.region_code,
                r.office_type,
                COALESCE(m.title, r.matchup_id) AS title,
                COALESCE(m.title, r.matchup_id) AS canonical_title,
                NULLIF(BTRIM(r.article_title), '') AS article_title,
                r.value_mid,
                r.survey_end_date,
                r.option_name,
                r.audience_scope,
                r.audience_region_code,
                r.observation_updated_at,
                r.official_release_at,
                r.article_published_at,
                r.source_grade,
                r.legal_completeness_score,
                r.legal_filled_count,
                r.legal_required_count,
                r.source_channel,
                r.source_channels
            FROM scoped_rank r
            LEFT JOIN matchups m ON m.matchup_id = r.matchup_id
            WHERE r.scope_rn = 1
            ORDER BY r.region_code, r.office_type
            LIMIT %s
        """

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = [dict(row) for row in (cur.fetchall() or [])]

        _api_read_cache_set(cache_key, rows)
        return rows

    def fetch_dashboard_big_matches(self, as_of: date | None, limit: int = 3):
        cache_key = _api_read_cache_key("dashboard_big_matches", as_of or "none", limit)
        cached = _api_read_cache_get(cache_key)
        if cached is not None:
            return cached

        params = []
        as_of_filter = ""
        if as_of is not None:
            as_of_filter = "AND o.survey_end_date <= %s"
            params.append(as_of)
        params.append(limit)

        query = f"""
            WITH latest_obs AS (
                SELECT
                    o.id,
                    o.matchup_id,
                    o.survey_end_date,
                    o.audience_scope,
                    o.audience_region_code,
                    o.updated_at AS observation_updated_at,
                    o.official_release_at,
                    o.article_id,
                    o.source_channel,
                    COALESCE(
                        o.source_channels,
                        CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END
                    ) AS source_channels,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.matchup_id
                        ORDER BY o.survey_end_date DESC NULLS LAST, o.id DESC
                    ) AS rn
                FROM poll_observations o
                WHERE o.verified = TRUE
                  {as_of_filter}
            ),
            ranked_options AS (
                SELECT
                    lo.id AS observation_id,
                    lo.matchup_id,
                    lo.survey_end_date,
                    po.value_mid,
                    DENSE_RANK() OVER (
                        PARTITION BY lo.id
                        ORDER BY po.value_mid DESC NULLS LAST
                    ) AS option_rank
                FROM latest_obs lo
                JOIN poll_options po ON po.observation_id = lo.id
                WHERE lo.rn = 1
                  AND po.option_type = 'candidate_matchup'
                  AND COALESCE(po.candidate_verified, TRUE) = TRUE
                  AND po.value_mid IS NOT NULL
            ),
            scored AS (
                SELECT
                    observation_id,
                    matchup_id,
                    survey_end_date,
                    MAX(value_mid) FILTER (WHERE option_rank = 1) AS value_mid,
                    MAX(value_mid) FILTER (WHERE option_rank = 1)
                      - MAX(value_mid) FILTER (WHERE option_rank = 2) AS spread
                FROM ranked_options
                GROUP BY observation_id, matchup_id, survey_end_date
            )
            SELECT
                s.matchup_id,
                COALESCE(m.title, s.matchup_id) AS title,
                COALESCE(m.title, s.matchup_id) AS canonical_title,
                NULLIF(BTRIM(a.title), '') AS article_title,
                s.survey_end_date,
                s.value_mid,
                s.spread,
                lo.audience_scope,
                lo.audience_region_code,
                lo.observation_updated_at,
                lo.official_release_at,
                a.published_at AS article_published_at,
                lo.source_channel,
                lo.source_channels
            FROM scored s
            JOIN latest_obs lo ON lo.id = s.observation_id
            LEFT JOIN matchups m ON m.matchup_id = s.matchup_id
            LEFT JOIN articles a ON a.id = lo.article_id
            ORDER BY s.spread ASC NULLS LAST, s.survey_end_date DESC NULLS LAST, s.matchup_id
            LIMIT %s
        """

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = [dict(row) for row in (cur.fetchall() or [])]

        _api_read_cache_set(cache_key, rows)
        return rows

    def fetch_dashboard_quality(self):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                WITH base AS (
                    SELECT
                        EXTRACT(
                            EPOCH FROM (
                                NOW() - COALESCE(o.official_release_at, a.published_at, o.updated_at)
                            )
                        ) / 3600.0 AS freshness_hours,
                        CASE
                            WHEN o.source_channel = 'article'
                              OR COALESCE('article' = ANY(o.source_channels), FALSE)
                            THEN TRUE
                            ELSE FALSE
                        END AS has_article,
                        CASE
                            WHEN o.source_channel = 'nesdc'
                              OR COALESCE('nesdc' = ANY(o.source_channels), FALSE)
                            THEN TRUE
                            ELSE FALSE
                        END AS has_nesdc
                    FROM poll_observations o
                    LEFT JOIN articles a ON a.id = o.article_id
                    WHERE o.verified = TRUE
                ),
                aggregate AS (
                    SELECT
                        COUNT(*)::int AS total_count,
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY freshness_hours) AS freshness_p50_hours,
                        percentile_cont(0.9) WITHIN GROUP (ORDER BY freshness_hours) AS freshness_p90_hours,
                        COUNT(*) FILTER (WHERE freshness_hours > 24)::int AS stale_over_24h_count,
                        COUNT(*) FILTER (WHERE freshness_hours > 48)::int AS stale_over_48h_count,
                        COUNT(*) FILTER (WHERE has_article)::int AS article_count,
                        COUNT(*) FILTER (WHERE has_nesdc)::int AS nesdc_count
                    FROM base
                ),
                review AS (
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'pending')::int AS pending_count,
                        COUNT(*) FILTER (WHERE status = 'in_progress')::int AS in_progress_count,
                        COUNT(*) FILTER (
                            WHERE status = 'pending'
                              AND created_at < NOW() - INTERVAL '24 hours'
                        )::int AS pending_over_24h_count
                    FROM review_queue
                )
                SELECT
                    a.total_count,
                    a.freshness_p50_hours,
                    a.freshness_p90_hours,
                    a.stale_over_24h_count,
                    a.stale_over_48h_count,
                    a.article_count,
                    a.nesdc_count,
                    r.pending_count,
                    r.in_progress_count,
                    r.pending_over_24h_count
                FROM aggregate a
                CROSS JOIN review r
                """
            )
            row = cur.fetchone() or {}

        total_count = row.get("total_count", 0) or 0
        article_count = row.get("article_count", 0) or 0
        nesdc_count = row.get("nesdc_count", 0) or 0
        stale_over_24h_count = row.get("stale_over_24h_count", 0) or 0
        stale_over_48h_count = row.get("stale_over_48h_count", 0) or 0
        pending_count = row.get("pending_count", 0) or 0
        in_progress_count = row.get("in_progress_count", 0) or 0
        pending_over_24h_count = row.get("pending_over_24h_count", 0) or 0
        needs_manual_review_count = pending_count + in_progress_count

        if total_count > 0:
            official_confirmed_ratio = round(nesdc_count / total_count, 4)
            article_ratio = round(article_count / total_count, 4)
            nesdc_ratio = round(nesdc_count / total_count, 4)
            stale_over_24h_ratio = round(stale_over_24h_count / total_count, 4)
            stale_over_48h_ratio = round(stale_over_48h_count / total_count, 4)
        else:
            official_confirmed_ratio = 0.0
            article_ratio = 0.0
            nesdc_ratio = 0.0
            stale_over_24h_ratio = 0.0
            stale_over_48h_ratio = 0.0

        freshness_p50 = row.get("freshness_p50_hours")
        freshness_p90 = row.get("freshness_p90_hours")
        freshness_p90_value = round(float(freshness_p90), 2) if freshness_p90 is not None else None

        if freshness_p90_value is None:
            freshness_status = "warn"
        elif freshness_p90_value > 72 or stale_over_48h_ratio >= 0.3:
            freshness_status = "critical"
        elif freshness_p90_value > 48 or stale_over_24h_ratio >= 0.3:
            freshness_status = "warn"
        else:
            freshness_status = "healthy"

        if official_confirmed_ratio < 0.4:
            official_status = "critical"
        elif official_confirmed_ratio < 0.7:
            official_status = "warn"
        else:
            official_status = "healthy"

        if pending_over_24h_count >= 20 or needs_manual_review_count >= 50:
            review_status = "critical"
        elif pending_over_24h_count >= 5 or needs_manual_review_count >= 10:
            review_status = "warn"
        else:
            review_status = "healthy"

        if "critical" in {freshness_status, official_status, review_status}:
            quality_status = "critical"
        elif "warn" in {freshness_status, official_status, review_status}:
            quality_status = "warn"
        else:
            quality_status = "healthy"

        return {
            "quality_status": quality_status,
            "freshness_p50_hours": round(float(freshness_p50), 2) if freshness_p50 is not None else None,
            "freshness_p90_hours": freshness_p90_value,
            "official_confirmed_ratio": official_confirmed_ratio,
            "needs_manual_review_count": needs_manual_review_count,
            "source_channel_mix": {
                "article_ratio": article_ratio,
                "nesdc_ratio": nesdc_ratio,
            },
            "freshness": {
                "p50_hours": round(float(freshness_p50), 2) if freshness_p50 is not None else None,
                "p90_hours": freshness_p90_value,
                "over_24h_ratio": stale_over_24h_ratio,
                "over_48h_ratio": stale_over_48h_ratio,
                "status": freshness_status,
            },
            "official_confirmation": {
                "confirmed_ratio": official_confirmed_ratio,
                "unconfirmed_count": max(total_count - nesdc_count, 0),
                "status": official_status,
            },
            "review_queue": {
                "pending_count": pending_count,
                "in_progress_count": in_progress_count,
                "pending_over_24h_count": pending_over_24h_count,
            },
        }

    def search_regions(self, query: str, limit: int = 20, has_data: bool | None = None):
        normalized_query = " ".join(query.split()).strip()
        q = f"%{normalized_query}%" if normalized_query else None
        compact_q = f"%{normalized_query.replace(' ', '')}%" if normalized_query else None

        where_clauses: list[str] = []
        params: list[object] = []
        if normalized_query:
            where_clauses.append(
                """
                (
                    (sido_name || ' ' || sigungu_name) ILIKE %s
                    OR sido_name ILIKE %s
                    OR sigungu_name ILIKE %s
                    OR REPLACE((sido_name || sigungu_name), ' ', '') ILIKE %s
                    OR REPLACE(sido_name, ' ', '') ILIKE %s
                    OR REPLACE(sigungu_name, ' ', '') ILIKE %s
                )
                """
            )
            params.extend([q, q, q, compact_q, compact_q, compact_q])

        if has_data is not None:
            where_clauses.append("COALESCE(o.observation_count, 0)::int > 0 = %s")
            params.append(has_data)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                WITH official_regions AS (
                    SELECT DISTINCT region_code
                    FROM elections
                    WHERE is_active = TRUE
                )
                SELECT
                    r.region_code,
                    r.sido_name,
                    r.sigungu_name,
                    r.admin_level,
                    COALESCE(o.observation_count, 0)::int > 0 AS has_data,
                    COALESCE(m.matchup_count, 0)::int AS matchup_count
                FROM regions r
                JOIN official_regions e ON e.region_code = r.region_code
                LEFT JOIN (
                    SELECT region_code, COUNT(*)::int AS matchup_count
                    FROM matchups
                    GROUP BY region_code
                ) m ON m.region_code = r.region_code
                LEFT JOIN (
                    SELECT region_code, COUNT(*)::int AS observation_count
                    FROM poll_observations
                    GROUP BY region_code
                ) o ON o.region_code = r.region_code
                {where_sql}
                ORDER BY
                    CASE r.admin_level
                        WHEN 'sido' THEN 0
                        WHEN 'sigungu' THEN 1
                        ELSE 2
                    END,
                    r.sido_name,
                    r.sigungu_name
                LIMIT %s
                """,
                tuple(params + [limit]),
            )
            return cur.fetchall()

    def search_regions_by_code(self, region_code: str, limit: int = 20, has_data: bool | None = None):
        normalized_region_code = " ".join(region_code.split()).strip()
        if not normalized_region_code:
            return []

        where_sql = "WHERE r.region_code = %s"
        params: list[object] = [normalized_region_code]
        if has_data is not None:
            where_sql += " AND COALESCE(o.observation_count, 0)::int > 0 = %s"
            params.append(has_data)

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                WITH official_regions AS (
                    SELECT DISTINCT region_code
                    FROM elections
                    WHERE is_active = TRUE
                )
                SELECT
                    r.region_code,
                    r.sido_name,
                    r.sigungu_name,
                    r.admin_level,
                    COALESCE(o.observation_count, 0)::int > 0 AS has_data,
                    COALESCE(m.matchup_count, 0)::int AS matchup_count
                FROM regions r
                JOIN official_regions e ON e.region_code = r.region_code
                LEFT JOIN (
                    SELECT region_code, COUNT(*)::int AS matchup_count
                    FROM matchups
                    GROUP BY region_code
                ) m ON m.region_code = r.region_code
                LEFT JOIN (
                    SELECT region_code, COUNT(*)::int AS observation_count
                    FROM poll_observations
                    GROUP BY region_code
                ) o ON o.region_code = r.region_code
                {where_sql}
                ORDER BY
                    CASE r.admin_level
                        WHEN 'sido' THEN 0
                        WHEN 'sigungu' THEN 1
                        ELSE 2
                    END,
                    r.sido_name,
                    r.sigungu_name
                LIMIT %s
                """,
                tuple(params + [limit]),
            )
            return cur.fetchall()

    def fetch_region_elections(
        self,
        region_code: str,
        topology: str = "official",
        version_id: str | None = None,
    ):
        def normalize_text(value: str | None) -> str:
            if not isinstance(value, str):
                return ""
            return value.strip()

        def strip_region_suffix(name: str) -> str:
            for suffix in ("특별자치도", "특별자치시", "특별시", "광역시", "자치시", "도", "시"):
                if name.endswith(suffix):
                    return name[: -len(suffix)] or name
            return name

        def compact_region_name(name: str) -> str:
            replacements = {
                "전라남": "전남",
                "전라북": "전북",
                "충청남": "충남",
                "충청북": "충북",
                "경상남": "경남",
                "경상북": "경북",
            }
            return replacements.get(name, name)

        def derive_placeholder_title(region: dict, office_type: str) -> str:
            sido_name = normalize_text(region.get("sido_name"))
            sigungu_name = normalize_text(region.get("sigungu_name"))
            base_sido = strip_region_suffix(sido_name)

            if office_type == "광역자치단체장":
                if sido_name.endswith(("특별시", "광역시", "특별자치시", "자치시")):
                    return f"{base_sido}시장"
                if sido_name.endswith(("도", "특별자치도")):
                    return f"{base_sido}도지사"
                return f"{base_sido}광역자치단체장"

            if office_type == "광역의회":
                if sido_name.endswith(("특별시", "광역시", "특별자치시", "자치시")):
                    return f"{base_sido}시의회"
                if sido_name.endswith(("도", "특별자치도")):
                    return f"{base_sido}도의회"
                return f"{base_sido}광역의회"

            if office_type == "교육감":
                return f"{base_sido}교육감"

            target = sigungu_name if sigungu_name and sigungu_name != "전체" else base_sido
            if office_type == "기초자치단체장":
                if target.endswith("구"):
                    return f"{target}청장"
                if target.endswith("군"):
                    return f"{target}수"
                if target.endswith("시"):
                    return f"{target}장"
                return f"{target}기초자치단체장"

            if office_type == "기초의회":
                return f"{target}의회"

            if office_type == "재보궐":
                return f"{target}재보궐"

            return f"{target} {office_type}".strip()

        def infer_election_id(matchup_rows: list[dict], poll_meta_rows: list[dict]) -> str:
            for row in matchup_rows:
                matchup_id = row.get("matchup_id")
                if isinstance(matchup_id, str) and "|" in matchup_id:
                    return matchup_id.split("|", 1)[0]
            for row in poll_meta_rows:
                matchup_id = row.get("latest_matchup_id")
                if isinstance(matchup_id, str) and "|" in matchup_id:
                    return matchup_id.split("|", 1)[0]
            return "20260603"

        def status_label(has_poll_data: bool, has_candidate_data: bool) -> str:
            if not has_poll_data:
                return "조사 데이터 없음"
            if not has_candidate_data:
                return "후보 정보 준비중"
            return "데이터 준비 완료"

        def build_scenario_parent_region(
            parent_region_code: str,
            topology_version_id: str,
            cur,
        ) -> dict | None:
            cur.execute(
                """
                SELECT r.sido_name, r.sigungu_name
                FROM region_topology_edges e
                JOIN regions r ON r.region_code = e.child_region_code
                WHERE e.version_id = %s
                  AND e.parent_region_code = %s
                ORDER BY e.child_region_code
                """,
                (topology_version_id, parent_region_code),
            )
            children = cur.fetchall() or []
            if not children:
                return None

            bases: list[str] = []
            for child in children:
                name = compact_region_name(strip_region_suffix(normalize_text(child.get("sido_name"))))
                if name and name not in bases:
                    bases.append(name)
            label = "·".join(bases) if bases else parent_region_code
            return {
                "region_code": parent_region_code,
                "sido_name": f"{label} 통합특별시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }

        def apply_official_region_overrides(region: dict) -> dict:
            region_out = dict(region)
            code = normalize_text(region_out.get("region_code"))
            if re.fullmatch(r"\d{2}-000", code):
                region_out["admin_level"] = "sido"
                if normalize_text(region_out.get("sigungu_name")) in {"", "전체"}:
                    region_out["sigungu_name"] = "전체"

            if code == "29-000":
                # 운영 회귀 보호: 29-000은 공식 토폴로지에서 세종으로 고정한다.
                region_out["sido_name"] = "세종특별자치시"
                region_out["sigungu_name"] = "전체"
                region_out["admin_level"] = "sido"
            return region_out

        def apply_official_title_overrides(region: dict, office_type: str, title: str | None) -> str:
            normalized_title = normalize_text(title)
            code = normalize_text(region.get("region_code"))

            # 운영 회귀 보호: 29-000은 세종 라벨이 아닌 타 시도 라벨을 허용하지 않는다.
            # 레거시/오염 타이틀이 들어오면 코드 기준 placeholder로 강제 복원한다.
            if code == "29-000" and "세종" not in normalized_title:
                return derive_placeholder_title(region, office_type)

            if normalized_title:
                return normalized_title
            return derive_placeholder_title(region, office_type)

        office_order = ["광역자치단체장", "광역의회", "교육감", "기초자치단체장", "기초의회", "재보궐"]
        topology_mode = "scenario" if topology == "scenario" else "official"

        with self.conn.cursor() as cur:
            topology_version = None
            if version_id:
                cur.execute(
                    """
                    SELECT version_id, mode, status
                    FROM region_topology_versions
                    WHERE version_id = %s
                      AND mode = %s
                    LIMIT 1
                    """,
                    (version_id, topology_mode),
                )
                topology_version = cur.fetchone()
            else:
                cur.execute(
                    """
                    SELECT version_id, mode, status
                    FROM region_topology_versions
                    WHERE mode = %s
                    ORDER BY
                        CASE status
                            WHEN 'effective' THEN 0
                            WHEN 'announced' THEN 1
                            ELSE 2
                        END,
                        effective_from DESC NULLS LAST,
                        version_id DESC
                    LIMIT 1
                    """,
                    (topology_mode,),
                )
                topology_version = cur.fetchone()

            if topology_mode == "official":
                topology_version_id = (topology_version or {}).get("version_id", "official-v1")
                effective_region_code = region_code
            else:
                topology_version_id = (topology_version or {}).get("version_id", "scenario-unversioned")
                effective_region_code = region_code
                cur.execute(
                    """
                    SELECT parent_region_code
                    FROM region_topology_edges
                    WHERE version_id = %s
                      AND child_region_code = %s
                    ORDER BY parent_region_code
                    LIMIT 1
                    """,
                    (topology_version_id, region_code),
                )
                parent = cur.fetchone()
                if parent and parent.get("parent_region_code"):
                    effective_region_code = parent["parent_region_code"]

            cur.execute(
                """
                SELECT region_code, sido_name, sigungu_name, admin_level
                FROM regions
                WHERE region_code = %s
                """,
                (effective_region_code,),
            )
            region = cur.fetchone()
            if not region and topology_mode == "scenario" and effective_region_code != region_code:
                region = build_scenario_parent_region(effective_region_code, topology_version_id, cur)
            if not region:
                return []
            if topology_mode == "official":
                region = apply_official_region_overrides(region)

            cur.execute(
                """
                SELECT
                    region_code,
                    office_type,
                    slot_matchup_id,
                    title,
                    source,
                    has_poll_data,
                    latest_matchup_id,
                    is_active
                FROM elections
                WHERE region_code = %s
                ORDER BY has_poll_data DESC, office_type, title
                """,
                (effective_region_code,),
            )
            election_rows = cur.fetchall() or []

            cur.execute(
                """
                SELECT matchup_id, region_code, office_type, title, is_active, updated_at
                FROM matchups
                WHERE region_code = %s
                ORDER BY is_active DESC, updated_at DESC, matchup_id DESC
                """,
                (effective_region_code,),
            )
            matchup_rows = cur.fetchall() or []

            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        o.id,
                        o.office_type,
                        o.matchup_id,
                        o.survey_end_date,
                        ROW_NUMBER() OVER (
                            PARTITION BY o.office_type
                            ORDER BY o.survey_end_date DESC NULLS LAST, o.id DESC
                        ) AS rn
                    FROM poll_observations o
                    WHERE o.region_code = %s
                )
                SELECT
                    r.office_type,
                    TRUE AS has_poll_data,
                    r.survey_end_date::date AS latest_survey_end_date,
                    r.matchup_id AS latest_matchup_id,
                    EXISTS (
                        SELECT 1
                        FROM poll_options po
                        WHERE po.observation_id = r.id
                          AND po.option_type = 'candidate_matchup'
                          AND COALESCE(po.candidate_verified, TRUE) = TRUE
                    ) AS has_candidate_data
                FROM ranked r
                WHERE r.rn = 1
                """,
                (effective_region_code,),
            )
            poll_meta_rows = cur.fetchall() or []

        election_by_office: dict[str, dict] = {}
        for row in election_rows:
            office_type = row.get("office_type")
            if not isinstance(office_type, str):
                continue
            election_by_office[office_type] = row

        resolved_region_code = region.get("region_code") or effective_region_code
        matchup_by_office: dict[str, dict] = {}
        for row in matchup_rows:
            office_type = row.get("office_type")
            if not isinstance(office_type, str):
                continue
            matchup_by_office.setdefault(office_type, row)

        poll_meta_by_office = {
            row["office_type"]: row
            for row in poll_meta_rows
            if isinstance(row.get("office_type"), str)
        }

        is_master_empty = len(election_by_office) == 0

        if election_by_office:
            slots = sorted(
                election_by_office.keys(),
                key=lambda office: (
                    office_order.index(office) if office in office_order else len(office_order),
                    office,
                ),
            )
        else:
            resolved_region_code = normalize_text(region.get("region_code"))
            is_sido_code = bool(re.fullmatch(r"\d{2}-000", resolved_region_code))
            if not is_sido_code and normalize_text(region.get("admin_level")) in {"sigungu", "local"}:
                slots = ["기초자치단체장", "기초의회"]
            else:
                slots = ["광역자치단체장", "광역의회", "교육감"]

            if "재보궐" in matchup_by_office or "재보궐" in poll_meta_by_office:
                slots.append("재보궐")

        extra_offices = sorted(
            (set(election_by_office.keys()) | set(matchup_by_office.keys()) | set(poll_meta_by_office.keys())) - set(slots),
            key=lambda office: (
                office_order.index(office) if office in office_order else len(office_order),
                office,
            ),
        )
        slots.extend(extra_offices)

        election_id = infer_election_id(matchup_rows, poll_meta_rows)
        result: list[dict] = []
        for office_type in slots:
            poll_meta = poll_meta_by_office.get(office_type, {})
            election_row = election_by_office.get(office_type)
            has_poll_data = bool(poll_meta.get("has_poll_data", False))
            if not has_poll_data and election_row is not None:
                has_poll_data = bool(election_row.get("has_poll_data", False))
            has_candidate_data = bool(poll_meta.get("has_candidate_data", False))
            latest_survey_end_date = poll_meta.get("latest_survey_end_date")
            latest_matchup_id = poll_meta.get("latest_matchup_id")
            if latest_matchup_id is None and election_row is not None:
                latest_matchup_id = election_row.get("latest_matchup_id")

            matchup_row = matchup_by_office.get(office_type)
            if election_row:
                slot_matchup_id = election_row.get("slot_matchup_id")
                matchup_id = latest_matchup_id or (matchup_row.get("matchup_id") if matchup_row else None) or slot_matchup_id
                matchup_id = matchup_id or f"{election_id}|{office_type}|{resolved_region_code}"
                title = (
                    election_row.get("title")
                    or (matchup_row.get("title") if matchup_row else None)
                    or derive_placeholder_title(region, office_type)
                )
                is_active = bool(election_row.get("is_active", True))
                is_placeholder = not has_poll_data
                is_fallback = False
                source = normalize_text(election_row.get("source")) or "master"
            elif matchup_row:
                matchup_id = matchup_row["matchup_id"]
                title = matchup_row["title"]
                is_active = bool(matchup_row.get("is_active", True))
                is_placeholder = False
                is_fallback = is_master_empty
                source = "generated" if is_master_empty else "matchups"
            else:
                matchup_id = latest_matchup_id or f"{election_id}|{office_type}|{resolved_region_code}"
                title = derive_placeholder_title(region, office_type)
                is_active = True
                is_placeholder = True
                is_fallback = True
                source = "generated"

            if topology_mode == "official":
                title = apply_official_title_overrides(region, office_type, title)

            result.append(
                {
                    "matchup_id": matchup_id,
                    "region_code": resolved_region_code,
                    "office_type": office_type,
                    "title": title,
                    "is_active": is_active,
                    "is_placeholder": is_placeholder,
                    "is_fallback": is_fallback,
                    "source": source,
                    "has_poll_data": has_poll_data,
                    "has_candidate_data": has_candidate_data,
                    "latest_survey_end_date": latest_survey_end_date,
                    "latest_matchup_id": latest_matchup_id,
                    "status": status_label(has_poll_data=has_poll_data, has_candidate_data=has_candidate_data),
                    "topology": topology_mode,
                    "topology_version_id": topology_version_id,
                }
            )

        return result

    def upsert_election_slot(self, election_slot: dict) -> None:
        payload = dict(election_slot)
        payload.setdefault("source", "code_master")
        payload.setdefault("has_poll_data", False)
        payload.setdefault("latest_matchup_id", None)
        payload.setdefault("is_active", True)
        payload.setdefault("slot_matchup_id", f"master|{payload['office_type']}|{payload['region_code']}")
        payload.setdefault("title", payload["office_type"])

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO elections (
                    region_code, office_type, slot_matchup_id, title,
                    source, has_poll_data, latest_matchup_id, is_active
                )
                VALUES (
                    %(region_code)s, %(office_type)s, %(slot_matchup_id)s, %(title)s,
                    %(source)s, %(has_poll_data)s, %(latest_matchup_id)s, %(is_active)s
                )
                ON CONFLICT (region_code, office_type) DO UPDATE
                SET slot_matchup_id=EXCLUDED.slot_matchup_id,
                    title=EXCLUDED.title,
                    source=EXCLUDED.source,
                    has_poll_data=EXCLUDED.has_poll_data,
                    latest_matchup_id=EXCLUDED.latest_matchup_id,
                    is_active=EXCLUDED.is_active,
                    updated_at=NOW()
                """,
                payload,
            )
        self.conn.commit()
        self._invalidate_api_read_cache()

    def fetch_all_regions(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT region_code, sido_name, sigungu_name, admin_level, parent_region_code
                FROM regions
                ORDER BY region_code
                """
            )
            return cur.fetchall() or []

    def fetch_latest_matchup_ids_by_region_office(self) -> dict[tuple[str, str], str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        region_code,
                        office_type,
                        matchup_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY region_code, office_type
                            ORDER BY survey_end_date DESC NULLS LAST, id DESC
                        ) AS rn
                    FROM poll_observations
                    WHERE verified = TRUE
                      AND matchup_id IS NOT NULL
                )
                SELECT region_code, office_type, matchup_id
                FROM ranked
                WHERE rn = 1
                """
            )
            rows = cur.fetchall() or []
        return {(str(row["region_code"]), str(row["office_type"])): str(row["matchup_id"]) for row in rows}

    def fetch_observed_byelection_pairs(self) -> set[tuple[str, str]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT region_code, office_type
                FROM matchups
                WHERE office_type LIKE '%%재보궐%%'
                UNION
                SELECT DISTINCT region_code, office_type
                FROM poll_observations
                WHERE office_type LIKE '%%재보궐%%'
                """
            )
            rows = cur.fetchall() or []
        return {(str(row["region_code"]), str(row["office_type"])) for row in rows}

    def _find_matchup_meta(self, matchup_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT matchup_id, region_code, office_type, title, is_active
                FROM matchups
                WHERE matchup_id = %s
                """,
                (matchup_id,),
            )
            row = cur.fetchone()
            if row:
                return row

            parts = [x.strip() for x in matchup_id.split("|")]
            if len(parts) != 3:
                return None
            _, office_type, region_code = parts
            cur.execute(
                """
                SELECT matchup_id, region_code, office_type, title, is_active
                FROM matchups
                WHERE office_type = %s
                  AND region_code = %s
                ORDER BY is_active DESC, updated_at DESC, matchup_id DESC
                LIMIT 1
                """,
                (office_type, region_code),
            )
            return cur.fetchone()

    def _fetch_recent_matchup_observations(self, matchup_id: str, *, limit: int = 5) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    o.matchup_id,
                    o.region_code,
                    o.office_type,
                    COALESCE(m.title, o.matchup_id) AS title,
                    o.observation_key,
                    o.pollster,
                    o.survey_start_date,
                    o.survey_end_date,
                    o.confidence_level,
                    o.sample_size,
                    o.response_rate,
                    o.margin_of_error,
                    o.source_grade,
                    o.audience_scope,
                    o.audience_region_code,
                    o.sampling_population_text,
                    o.legal_completeness_score,
                    o.legal_filled_count,
                    o.legal_required_count,
                    o.date_resolution,
                    o.date_inference_mode,
                    o.date_inference_confidence,
                    o.updated_at AS observation_updated_at,
                    o.official_release_at,
                    a.published_at AS article_published_at,
                    CASE
                        WHEN o.source_channel = 'nesdc' THEN TRUE
                        WHEN COALESCE('nesdc' = ANY(o.source_channels), FALSE) THEN TRUE
                        ELSE FALSE
                    END AS nesdc_enriched,
                    EXISTS (
                        SELECT 1
                        FROM review_queue rq
                        WHERE rq.entity_type IN ('poll_observation', 'ingest_record')
                          AND rq.entity_id = o.observation_key
                          AND rq.status IN ('pending', 'in_progress')
                    ) AS needs_manual_review,
                    o.poll_fingerprint,
                    o.source_channel,
                    o.source_channels,
                    o.verified,
                    o.id AS observation_id,
                    COALESCE(opts.options, '[]'::json) AS options
                FROM poll_observations o
                LEFT JOIN matchups m ON m.matchup_id = o.matchup_id
                LEFT JOIN articles a ON a.id = o.article_id
                LEFT JOIN LATERAL (
                    SELECT
                        json_agg(
                            json_build_object(
                                'option_name', po.option_name,
                                'candidate_id', COALESCE(po.candidate_id, c.candidate_id),
                                'party_name', CASE
                                    WHEN COALESCE(c.party_name, '') <> '' THEN c.party_name
                                    WHEN COALESCE(po.party_name, '') <> '' THEN po.party_name
                                    ELSE '미확정(검수대기)'
                                END,
                                'scenario_key', po.scenario_key,
                                'scenario_type', po.scenario_type,
                                'scenario_title', po.scenario_title,
                                'value_mid', po.value_mid,
                                'value_raw', po.value_raw,
                                'party_inferred', CASE
                                    WHEN COALESCE(c.party_name, '') <> '' THEN FALSE
                                    ELSE po.party_inferred
                                END,
                                'party_inference_source', CASE
                                    WHEN COALESCE(c.party_name, '') <> '' THEN NULL
                                    ELSE po.party_inference_source
                                END,
                                'party_inference_confidence', CASE
                                    WHEN COALESCE(c.party_name, '') <> '' THEN NULL
                                    ELSE po.party_inference_confidence
                                END,
                                'party_inference_evidence', CASE
                                    WHEN COALESCE(c.party_name, '') <> '' THEN NULL
                                    ELSE po.party_inference_evidence
                                END,
                                'needs_manual_review', (
                                    po.needs_manual_review
                                    OR (
                                        COALESCE(c.party_name, '') = ''
                                        AND COALESCE(po.party_name, '') = ''
                                    )
                                ),
                                'candidate_verified', po.candidate_verified,
                                'candidate_verify_source', COALESCE(po.candidate_verify_source, 'manual'),
                                'candidate_verify_confidence',
                                    COALESCE(
                                        po.candidate_verify_confidence,
                                        CASE WHEN COALESCE(po.candidate_verified, TRUE) THEN 1.0 ELSE 0.0 END
                                    ),
                                'candidate_verify_matched_key',
                                    COALESCE(po.candidate_verify_matched_key, po.candidate_id, po.option_name)
                            )
                            ORDER BY po.scenario_key, po.value_mid DESC NULLS LAST, po.option_name
                        ) AS options
                    FROM poll_options po
                    LEFT JOIN LATERAL (
                        SELECT c.candidate_id, c.party_name
                        FROM candidates c
                        WHERE c.candidate_id = po.candidate_id
                           OR (po.candidate_id IS NULL AND c.name_ko = po.option_name)
                        ORDER BY
                            (c.candidate_id = po.candidate_id) DESC,
                            (c.party_name IS NOT NULL) DESC,
                            c.updated_at DESC
                        LIMIT 1
                    ) c ON TRUE
                    WHERE po.observation_id = o.id
                      AND COALESCE(po.candidate_verified, TRUE) = TRUE
                ) opts ON TRUE
                WHERE o.matchup_id = %s
                ORDER BY o.survey_end_date DESC NULLS LAST, o.id DESC
                LIMIT %s
                """,
                (matchup_id, max(int(limit), 1)),
            )
            rows: list[dict] = []
            if hasattr(cur, "fetchall"):
                rows = cur.fetchall() or []
            # Test doubles may stub fetchone-only behavior.
            if not rows and hasattr(cur, "fetchone"):
                single = cur.fetchone()
                if single:
                    rows = [single]
            return rows

    @staticmethod
    def _normalize_options(options_payload, *, include_stats: bool = False) -> list[dict] | tuple[list[dict], dict]:
        options = options_payload
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except json.JSONDecodeError:
                options = []
        if options is None:
            options = []
        if not isinstance(options, list):
            options = []
        normalized: list[dict] = []
        candidate_noise_block_count = 0
        for option in options:
            if not isinstance(option, dict):
                continue
            row = dict(option)

            scenario_key = row.get("scenario_key")
            if isinstance(scenario_key, str):
                scenario_key = scenario_key.strip()
            row["scenario_key"] = scenario_key or "default"

            scenario_type = row.get("scenario_type")
            if scenario_type not in {"head_to_head", "multi_candidate"}:
                scenario_type = None
            row["scenario_type"] = scenario_type

            scenario_title = row.get("scenario_title")
            if isinstance(scenario_title, str):
                scenario_title = scenario_title.strip() or None
            row["scenario_title"] = scenario_title

            candidate_id = row.get("candidate_id")
            if isinstance(candidate_id, str):
                candidate_id = candidate_id.strip() or None
            row["candidate_id"] = candidate_id

            option_name = row.get("option_name")
            if isinstance(option_name, str):
                option_name = option_name.strip()
            else:
                option_name = str(option_name or "").strip()
            row["option_name"] = option_name

            if _is_noise_candidate_option(option_name, candidate_id):
                candidate_noise_block_count += 1
                continue

            if _is_low_quality_manual_candidate_option(row):
                continue

            party_name = row.get("party_name")
            if isinstance(party_name, str):
                party_name = party_name.strip() or None
            row["party_name"] = party_name or "미확정(검수대기)"
            if row.get("candidate_id"):
                row["name_validity"] = "valid"
            elif row["party_name"] != "미확정(검수대기)":
                row["name_validity"] = "valid"
            else:
                row["name_validity"] = "unknown"

            normalized.append(row)
        if include_stats:
            return normalized, {
                "candidate_noise_block_count": candidate_noise_block_count,
            }
        return normalized

    @staticmethod
    def _infer_scenario_type(options: list[dict]) -> str:
        for option in options:
            scenario_type = option.get("scenario_type")
            if scenario_type in {"head_to_head", "multi_candidate"}:
                return scenario_type
        return "head_to_head" if len(options) <= 2 else "multi_candidate"

    @staticmethod
    def _infer_scenario_title(options: list[dict], scenario_type: str, scenario_key: str) -> str:
        for option in options:
            scenario_title = option.get("scenario_title")
            if isinstance(scenario_title, str) and scenario_title.strip():
                return scenario_title.strip()

        names = [str(opt.get("option_name", "")).strip() for opt in options if str(opt.get("option_name", "")).strip()]
        if scenario_type == "head_to_head":
            if len(names) >= 2:
                return f"{names[0]} vs {names[1]}"
            if len(names) == 1:
                return f"{names[0]} 단독"
            return "양자대결"

        if names:
            lead = ", ".join(names[:3])
            return f"다자대결: {lead}" if len(names) <= 3 else f"다자대결: {lead} 외"
        return f"다자대결 ({scenario_key})"

    def _build_matchup_scenarios(self, options: list[dict]) -> tuple[list[dict], list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for option in options:
            scenario_key = option.get("scenario_key") or "default"
            grouped.setdefault(scenario_key, []).append(option)

        scenarios: list[dict] = []
        for scenario_key, items in grouped.items():
            sorted_items = sorted(
                items,
                key=lambda item: (
                    -(item.get("value_mid") if item.get("value_mid") is not None else -1),
                    item.get("option_name") or "",
                ),
            )
            scenario_type = self._infer_scenario_type(sorted_items)
            scenario_title = self._infer_scenario_title(sorted_items, scenario_type, scenario_key)
            normalized_options = []
            for option in sorted_items:
                merged = dict(option)
                merged["scenario_key"] = scenario_key
                merged["scenario_type"] = scenario_type
                merged["scenario_title"] = scenario_title
                normalized_options.append(merged)

            scenarios.append(
                {
                    "scenario_key": scenario_key,
                    "scenario_type": scenario_type,
                    "scenario_title": scenario_title,
                    "options": normalized_options,
                }
            )

        scenarios.sort(key=lambda row: (0 if row["scenario_type"] == "head_to_head" else 1, row["scenario_title"]))
        if not scenarios:
            return [], []

        primary = next((row for row in scenarios if row["scenario_key"] == "default"), scenarios[0])
        return scenarios, primary["options"]

    @staticmethod
    def _observation_bundle_key(observation: dict) -> tuple:
        poll_fingerprint = str(observation.get("poll_fingerprint") or "").strip()
        if poll_fingerprint:
            return ("poll_fingerprint", poll_fingerprint)
        return (
            "poll_meta",
            str(observation.get("pollster") or "").strip().lower(),
            observation.get("survey_start_date"),
            observation.get("survey_end_date"),
            observation.get("sample_size"),
            observation.get("margin_of_error"),
            observation.get("confidence_level"),
            str(observation.get("source_channel") or "").strip().lower(),
            observation.get("article_published_at"),
        )

    @staticmethod
    def _matchup_option_identity(option: dict) -> tuple:
        return (
            str(option.get("scenario_key") or "default"),
            str(option.get("option_name") or "").strip(),
            str(option.get("candidate_id") or "").strip(),
            option.get("value_mid"),
            str(option.get("value_raw") or "").strip(),
        )

    @staticmethod
    def _scenario_key_stats(options: list[dict]) -> tuple[int, int]:
        scenario_keys: set[str] = set()
        for option in options:
            key = str(option.get("scenario_key") or "default").strip() or "default"
            scenario_keys.add(key)
        scenario_count = len(scenario_keys)
        explicit_scenario_count = len([key for key in scenario_keys if key != "default"])
        return scenario_count, explicit_scenario_count

    def _select_matchup_observation_bundle(self, observations: list[dict]) -> tuple[dict, list[dict], list[dict], int]:
        normalized_rows: list[tuple[dict, list[dict], int]] = []
        selected_observation: dict | None = None
        selected_options: list[dict] = []
        selected_score: tuple[int, int, int, int] | None = None
        fallback_noise_observation: dict | None = None
        fallback_noise_block_count = 0

        for observation in observations:
            normalized_options, stats = self._normalize_options(observation.get("options"), include_stats=True)
            noise_block_count = int(stats.get("candidate_noise_block_count", 0) or 0)
            normalized_rows.append((observation, normalized_options, noise_block_count))
            if noise_block_count > fallback_noise_block_count:
                fallback_noise_observation = observation
                fallback_noise_block_count = noise_block_count
            if not normalized_options:
                continue
            scenario_count, explicit_scenario_count = self._scenario_key_stats(normalized_options)
            quality_score = (
                1 if scenario_count >= 3 else 0,
                1 if explicit_scenario_count > 0 else 0,
                scenario_count,
                len(normalized_options),
            )
            if selected_score is None or quality_score > selected_score:
                selected_score = quality_score
                selected_observation = observation
                selected_options = normalized_options

        if selected_observation is None:
            if fallback_noise_observation is not None:
                return fallback_noise_observation, [], [], fallback_noise_block_count
            return observations[0], [], [], 0

        bundle_key = self._observation_bundle_key(selected_observation)
        merged_options: list[dict] = []
        seen_option_keys: set[tuple] = set()
        candidate_noise_block_count = 0
        for observation, normalized_options, noise_block_count in normalized_rows:
            if self._observation_bundle_key(observation) != bundle_key:
                continue
            candidate_noise_block_count += noise_block_count
            if not normalized_options:
                continue
            for option in normalized_options:
                option_key = self._matchup_option_identity(option)
                if option_key in seen_option_keys:
                    continue
                seen_option_keys.add(option_key)
                merged_options.append(dict(option))

        if not merged_options:
            merged_options = [dict(row) for row in selected_options]

        scenarios, primary_options = self._build_matchup_scenarios(merged_options)
        return selected_observation, scenarios, primary_options, candidate_noise_block_count

    @staticmethod
    def _strip_region_suffix(name: str) -> str:
        for suffix in ("특별자치도", "특별자치시", "특별시", "광역시", "자치시", "도", "시"):
            if name.endswith(suffix):
                return name[: -len(suffix)] or name
        return name

    @staticmethod
    def _derive_matchup_title_from_region(region: dict | None, office_type: str | None, fallback: str) -> str:
        if not isinstance(region, dict):
            return fallback

        sido_name = str(region.get("sido_name") or "").strip()
        sigungu_name = str(region.get("sigungu_name") or "").strip()
        base_sido = PostgresRepository._strip_region_suffix(sido_name)
        office = str(office_type or "").strip()

        if office == "광역자치단체장":
            if sido_name.endswith(("특별시", "광역시", "특별자치시", "자치시")):
                return f"{base_sido}시장"
            if sido_name.endswith(("도", "특별자치도")):
                return f"{base_sido}도지사"
            return f"{base_sido}광역자치단체장" if base_sido else fallback

        if office == "광역의회":
            if sido_name.endswith(("특별시", "광역시", "특별자치시", "자치시")):
                return f"{base_sido}시의회"
            if sido_name.endswith(("도", "특별자치도")):
                return f"{base_sido}도의회"
            return f"{base_sido}광역의회" if base_sido else fallback

        if office == "교육감":
            return f"{base_sido}교육감" if base_sido else fallback

        target = sigungu_name if sigungu_name and sigungu_name != "전체" else base_sido
        if office == "기초자치단체장":
            if target.endswith("구"):
                return f"{target}청장"
            if target.endswith("군"):
                return f"{target}수"
            if target.endswith("시"):
                return f"{target}장"
            return f"{target}기초자치단체장" if target else fallback

        if office == "기초의회":
            return f"{target}의회" if target else fallback

        if office == "재보궐":
            return f"{target}재보궐" if target else fallback

        if target and office:
            return f"{target} {office}".strip()
        return fallback

    def _fetch_region_for_matchup_title(self, region_code: str | None) -> dict | None:
        normalized = str(region_code or "").strip()
        if not normalized:
            return None
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT region_code, sido_name, sigungu_name, admin_level
                FROM regions
                WHERE region_code = %s
                LIMIT 1
                """,
                (normalized,),
            )
            return cur.fetchone()

    def get_matchup(self, matchup_id: str):
        cache_key = _api_read_cache_key("matchup", matchup_id)
        cached = _api_read_cache_get(cache_key)
        if cached is not None:
            return cached

        matchup_meta = self._find_matchup_meta(matchup_id)
        if not matchup_meta:
            return None

        canonical_matchup_id = matchup_meta["matchup_id"]
        canonical_cache_key = _api_read_cache_key("matchup", canonical_matchup_id)
        if canonical_cache_key != cache_key:
            canonical_cached = _api_read_cache_get(canonical_cache_key)
            if canonical_cached is not None:
                _api_read_cache_set(cache_key, canonical_cached)
                return canonical_cached

        region_for_title = self._fetch_region_for_matchup_title(matchup_meta.get("region_code"))
        canonical_title = self._derive_matchup_title_from_region(
            region_for_title,
            matchup_meta.get("office_type"),
            str(matchup_meta.get("title") or "").strip() or canonical_matchup_id,
        )
        observations = self._fetch_recent_matchup_observations(canonical_matchup_id, limit=5)
        if not observations:
            result = {
                "matchup_id": canonical_matchup_id,
                "region_code": matchup_meta["region_code"],
                "office_type": matchup_meta["office_type"],
                "title": canonical_title,
                "canonical_title": canonical_title,
                "article_title": None,
                "has_data": False,
                "pollster": None,
                "survey_start_date": None,
                "survey_end_date": None,
                "confidence_level": None,
                "sample_size": None,
                "response_rate": None,
                "margin_of_error": None,
                "source_grade": None,
                "audience_scope": None,
                "audience_region_code": None,
                "sampling_population_text": None,
                "legal_completeness_score": None,
                "legal_filled_count": None,
                "legal_required_count": None,
                "date_resolution": None,
                "date_inference_mode": None,
                "date_inference_confidence": None,
                "observation_updated_at": None,
                "official_release_at": None,
                "article_published_at": None,
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "candidate_noise_block_count": 0,
                "poll_fingerprint": None,
                "source_channel": None,
                "source_channels": [],
                "verified": False,
                "scenarios": [],
                "options": [],
            }
            _api_read_cache_set(canonical_cache_key, result)
            if canonical_cache_key != cache_key:
                _api_read_cache_set(cache_key, result)
            return result

        observation, scenarios, primary_options, candidate_noise_block_count = self._select_matchup_observation_bundle(
            observations
        )
        needs_manual_review = bool(observation["needs_manual_review"])
        if candidate_noise_block_count > 0 and not primary_options:
            observation_key = str(observation.get("observation_key") or "").strip()
            if observation_key:
                try:
                    self.ensure_review_queue_pending(
                        entity_type="poll_observation",
                        entity_id=observation_key,
                        issue_type="mapping_error",
                        review_note=(
                            "runtime candidate noise guard removed all candidate options "
                            f"(blocked={candidate_noise_block_count})"
                        ),
                    )
                except Exception:
                    pass
            needs_manual_review = True
        observation_title = str(observation.get("title") or "").strip()
        if not canonical_title:
            canonical_title = observation_title or canonical_matchup_id
        article_title = observation_title or None
        if article_title and article_title == canonical_title:
            article_title = None
        result = {
            "matchup_id": observation["matchup_id"],
            "region_code": observation["region_code"],
            "office_type": observation["office_type"],
            "title": canonical_title,
            "canonical_title": canonical_title,
            "article_title": article_title,
            "has_data": bool(primary_options),
            "pollster": observation["pollster"],
            "survey_start_date": observation["survey_start_date"],
            "survey_end_date": observation["survey_end_date"],
            "confidence_level": observation["confidence_level"],
            "sample_size": observation["sample_size"],
            "response_rate": observation["response_rate"],
            "margin_of_error": observation["margin_of_error"],
            "source_grade": observation["source_grade"],
            "audience_scope": observation["audience_scope"],
            "audience_region_code": observation["audience_region_code"],
            "sampling_population_text": observation["sampling_population_text"],
            "legal_completeness_score": observation["legal_completeness_score"],
            "legal_filled_count": observation["legal_filled_count"],
            "legal_required_count": observation["legal_required_count"],
            "date_resolution": observation["date_resolution"],
            "date_inference_mode": observation["date_inference_mode"],
            "date_inference_confidence": observation["date_inference_confidence"],
            "observation_updated_at": observation["observation_updated_at"],
            "official_release_at": observation["official_release_at"],
            "article_published_at": observation["article_published_at"],
            "nesdc_enriched": observation["nesdc_enriched"],
            "needs_manual_review": needs_manual_review,
            "candidate_noise_block_count": candidate_noise_block_count,
            "poll_fingerprint": observation["poll_fingerprint"],
            "source_channel": observation["source_channel"],
            "source_channels": observation["source_channels"],
            "verified": observation["verified"],
            "scenarios": scenarios,
            "options": primary_options,
        }
        _api_read_cache_set(canonical_cache_key, result)
        if canonical_cache_key != cache_key:
            _api_read_cache_set(cache_key, result)
        return result

    def get_candidate(self, candidate_id: str):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.candidate_id, c.name_ko, c.party_name,
                    c.party_inferred, c.party_inference_source, c.party_inference_confidence,
                    c.source_channel, c.source_channels, c.official_release_at, c.article_published_at,
                    c.profile_updated_at AS observation_updated_at,
                    EXISTS (
                        SELECT 1
                        FROM review_queue rq
                        WHERE rq.entity_type IN ('candidate', 'ingest_record')
                          AND rq.entity_id = c.candidate_id
                          AND rq.status IN ('pending', 'in_progress')
                    ) AS needs_manual_review,
                    c.gender,
                    c.birth_date, c.job,
                    cp.career_summary, cp.election_history,
                    cp.source_type AS profile_source_type,
                    cp.source_url AS profile_source_url
                FROM candidates c
                LEFT JOIN candidate_profiles cp ON cp.candidate_id = c.candidate_id
                WHERE c.candidate_id = %s
                """,
                (candidate_id,),
            )
            return cur.fetchone()

    def fetch_ops_ingestion_metrics(self, window_hours: int = 24):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int AS total_runs,
                    COUNT(*) FILTER (WHERE status = 'success')::int AS success_runs,
                    COUNT(*) FILTER (WHERE status = 'partial_success')::int AS partial_success_runs,
                    COUNT(*) FILTER (WHERE status = 'failed')::int AS failed_runs,
                    COALESCE(SUM(processed_count), 0)::int AS total_processed_count,
                    COALESCE(SUM(error_count), 0)::int AS total_error_count,
                    COALESCE(SUM(date_inference_failed_count), 0)::int AS date_inference_failed_count,
                    COALESCE(SUM(date_inference_estimated_count), 0)::int AS date_inference_estimated_count
                FROM ingestion_runs
                WHERE started_at >= NOW() - (%s * INTERVAL '1 hour')
                """,
                (window_hours,),
            )
            row = cur.fetchone() or {}

        processed = row.get("total_processed_count", 0) or 0
        errors = row.get("total_error_count", 0) or 0
        denominator = processed + errors
        fetch_fail_rate = (errors / denominator) if denominator > 0 else 0.0

        return {
            "total_runs": row.get("total_runs", 0) or 0,
            "success_runs": row.get("success_runs", 0) or 0,
            "partial_success_runs": row.get("partial_success_runs", 0) or 0,
            "failed_runs": row.get("failed_runs", 0) or 0,
            "total_processed_count": processed,
            "total_error_count": errors,
            "date_inference_failed_count": row.get("date_inference_failed_count", 0) or 0,
            "date_inference_estimated_count": row.get("date_inference_estimated_count", 0) or 0,
            "fetch_fail_rate": round(fetch_fail_rate, 4),
        }

    def fetch_ops_review_metrics(self, window_hours: int = 24):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending')::int AS pending_count,
                    COUNT(*) FILTER (WHERE status = 'in_progress')::int AS in_progress_count,
                    COUNT(*) FILTER (WHERE status NOT IN ('pending', 'in_progress'))::int AS resolved_count,
                    COUNT(*) FILTER (
                        WHERE status = 'pending'
                          AND created_at < NOW() - INTERVAL '24 hours'
                    )::int AS pending_over_24h_count,
                    COUNT(*) FILTER (
                        WHERE issue_type = 'mapping_error'
                          AND created_at >= NOW() - (%s * INTERVAL '1 hour')
                    )::int AS mapping_error_24h_count
                FROM review_queue
                """,
                (window_hours,),
            )
            row = cur.fetchone() or {}

        return {
            "pending_count": row.get("pending_count", 0) or 0,
            "in_progress_count": row.get("in_progress_count", 0) or 0,
            "resolved_count": row.get("resolved_count", 0) or 0,
            "pending_over_24h_count": row.get("pending_over_24h_count", 0) or 0,
            "mapping_error_24h_count": row.get("mapping_error_24h_count", 0) or 0,
        }

    def fetch_ops_failure_distribution(self, window_hours: int = 24):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT issue_type, COUNT(*)::int AS count
                FROM review_queue
                WHERE created_at >= NOW() - (%s * INTERVAL '1 hour')
                GROUP BY issue_type
                ORDER BY count DESC, issue_type
                """,
                (window_hours,),
            )
            rows = cur.fetchall()

        total = sum(int(row["count"]) for row in rows) if rows else 0
        out = []
        for row in rows:
            count = int(row["count"])
            ratio = (count / total) if total > 0 else 0.0
            out.append({"issue_type": row["issue_type"], "count": count, "ratio": round(ratio, 4)})
        return out

    def fetch_ops_coverage_summary(self):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int AS regions_total
                FROM regions
                """
            )
            total_row = cur.fetchone() or {}

            cur.execute(
                """
                SELECT
                    COUNT(DISTINCT o.region_code)::int AS regions_covered,
                    COUNT(DISTINCT r.sido_name)::int AS sido_covered,
                    COUNT(*)::int AS observations_total,
                    MAX(o.survey_end_date)::date AS latest_survey_end_date
                FROM poll_observations o
                LEFT JOIN regions r ON r.region_code = o.region_code
                """
            )
            row = cur.fetchone() or {}

        regions_total = total_row.get("regions_total", 0) or 0
        regions_covered = row.get("regions_covered", 0) or 0
        observations_total = row.get("observations_total", 0) or 0

        if observations_total == 0:
            state = "empty"
            warning_message = "No observations ingested yet."
        elif regions_total == 0:
            state = "partial"
            warning_message = "regions_total baseline unavailable."
        elif regions_covered < regions_total:
            state = "partial"
            warning_message = f"Coverage partial: {regions_covered}/{regions_total} regions covered."
        else:
            state = "ready"
            warning_message = None

        return {
            "state": state,
            "warning_message": warning_message,
            "regions_total": regions_total,
            "regions_covered": regions_covered,
            "sido_covered": row.get("sido_covered", 0) or 0,
            "observations_total": observations_total,
            "latest_survey_end_date": row.get("latest_survey_end_date"),
        }

    def fetch_review_queue_items(
        self,
        *,
        status: str | None = None,
        issue_type: str | None = None,
        assigned_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        where_clauses = []
        params: list = []
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        if issue_type:
            where_clauses.append("issue_type = %s")
            params.append(issue_type)
        if assigned_to:
            where_clauses.append("assigned_to = %s")
            params.append(assigned_to)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        params.extend([limit, offset])
        query = f"""
            SELECT
                id, entity_type, entity_id, issue_type, status,
                assigned_to, review_note, created_at, updated_at
            FROM review_queue
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
        """
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def update_review_queue_status(
        self,
        *,
        item_id: int,
        status: str,
        assigned_to: str | None = None,
        review_note: str | None = None,
    ):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE review_queue
                SET
                    status = %s,
                    assigned_to = COALESCE(%s, assigned_to),
                    review_note = COALESCE(%s, review_note),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING
                    id, entity_type, entity_id, issue_type, status,
                    assigned_to, review_note, created_at, updated_at
                """,
                (status, assigned_to, review_note, item_id),
            )
            row = cur.fetchone()
        self.conn.commit()
        self._invalidate_api_read_cache()
        return row

    def fetch_review_queue_stats(self, *, window_hours: int = 24):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int AS total_count,
                    COUNT(*) FILTER (WHERE status = 'pending')::int AS pending_count,
                    COUNT(*) FILTER (WHERE status = 'in_progress')::int AS in_progress_count,
                    COUNT(*) FILTER (WHERE status NOT IN ('pending', 'in_progress'))::int AS resolved_count
                FROM review_queue
                """
            )
            summary = cur.fetchone() or {}

            cur.execute(
                """
                SELECT issue_type, COUNT(*)::int AS count
                FROM review_queue
                WHERE created_at >= NOW() - (%s * INTERVAL '1 hour')
                GROUP BY issue_type
                ORDER BY count DESC, issue_type
                """,
                (window_hours,),
            )
            issue_rows = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COALESCE(NULLIF(split_part(issue_type, ':', 2), ''), 'unknown') AS error_code,
                    COUNT(*)::int AS count
                FROM review_queue
                WHERE created_at >= NOW() - (%s * INTERVAL '1 hour')
                GROUP BY error_code
                ORDER BY count DESC, error_code
                """,
                (window_hours,),
            )
            error_rows = cur.fetchall()

        return {
            "total_count": summary.get("total_count", 0) or 0,
            "pending_count": summary.get("pending_count", 0) or 0,
            "in_progress_count": summary.get("in_progress_count", 0) or 0,
            "resolved_count": summary.get("resolved_count", 0) or 0,
            "issue_type_counts": issue_rows,
            "error_code_counts": error_rows,
        }

    def fetch_review_queue_trends(
        self,
        *,
        window_hours: int = 24,
        bucket_hours: int = 6,
        issue_type: str | None = None,
        error_code: str | None = None,
    ):
        filters = ["created_at >= NOW() - (%s * INTERVAL '1 hour')"]
        where_params: list = [window_hours]
        if issue_type:
            filters.append("split_part(issue_type, ':', 1) = %s")
            where_params.append(issue_type)
        if error_code:
            filters.append("COALESCE(NULLIF(split_part(issue_type, ':', 2), ''), 'unknown') = %s")
            where_params.append(error_code)

        where_sql = " AND ".join(filters)
        bucket_seconds = bucket_hours * 3600
        params: list = [bucket_seconds, bucket_seconds, *where_params]
        query = f"""
            SELECT
                to_timestamp(
                    floor(extract(epoch from created_at) / %s) * %s
                ) AT TIME ZONE 'UTC' AS bucket_start,
                split_part(issue_type, ':', 1) AS issue_type,
                COALESCE(NULLIF(split_part(issue_type, ':', 2), ''), 'unknown') AS error_code,
                COUNT(*)::int AS count
            FROM review_queue
            WHERE {where_sql}
            GROUP BY bucket_start, issue_type, error_code
            ORDER BY bucket_start DESC, count DESC, issue_type, error_code
        """
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
