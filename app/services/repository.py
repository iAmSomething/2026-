from datetime import date

from app.services.errors import DuplicateConflictError
from app.services.fingerprint import merge_observation_by_priority


class PostgresRepository:
    def __init__(self, conn):
        self.conn = conn

    def rollback(self) -> None:
        self.conn.rollback()

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

    def upsert_candidate(self, candidate: dict) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidates (candidate_id, name_ko, party_name, gender, birth_date, job, profile_updated_at)
                VALUES (%(candidate_id)s, %(name_ko)s, %(party_name)s, %(gender)s, %(birth_date)s, %(job)s, NOW())
                ON CONFLICT (candidate_id) DO UPDATE
                SET name_ko=EXCLUDED.name_ko,
                    party_name=EXCLUDED.party_name,
                    gender=EXCLUDED.gender,
                    birth_date=EXCLUDED.birth_date,
                    job=EXCLUDED.job,
                    profile_updated_at=NOW()
                """,
                candidate,
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
                candidate,
            )
        self.conn.commit()

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
                    date_resolution, date_inference_mode, date_inference_confidence,
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
                    date_inference_mode, date_inference_confidence,
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
                    %(date_inference_mode)s, %(date_inference_confidence)s,
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

    def upsert_poll_option(self, observation_id: int, option: dict) -> None:
        payload = dict(option)
        payload["observation_id"] = observation_id
        payload.setdefault("party_inferred", False)
        payload.setdefault("party_inference_source", None)
        payload.setdefault("party_inference_confidence", None)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poll_options (
                    observation_id, option_type, option_name,
                    value_raw, value_min, value_max, value_mid, is_missing,
                    party_inferred, party_inference_source, party_inference_confidence
                )
                VALUES (
                    %(observation_id)s, %(option_type)s, %(option_name)s,
                    %(value_raw)s, %(value_min)s, %(value_max)s, %(value_mid)s, %(is_missing)s,
                    %(party_inferred)s, %(party_inference_source)s, %(party_inference_confidence)s
                )
                ON CONFLICT (observation_id, option_type, option_name) DO UPDATE
                SET value_raw=EXCLUDED.value_raw,
                    value_min=EXCLUDED.value_min,
                    value_max=EXCLUDED.value_max,
                    value_mid=EXCLUDED.value_mid,
                    is_missing=EXCLUDED.is_missing,
                    party_inferred=EXCLUDED.party_inferred,
                    party_inference_source=EXCLUDED.party_inference_source,
                    party_inference_confidence=EXCLUDED.party_inference_confidence,
                    updated_at=NOW()
                """,
                payload,
            )
        self.conn.commit()

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

    def count_review_queue(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*)::int AS count FROM review_queue")
            row = cur.fetchone() or {}
        return int(row.get("count", 0) or 0)

    def fetch_dashboard_summary(self, as_of: date | None):
        params = []
        as_of_filter = ""
        if as_of is not None:
            as_of_filter = "AND o.survey_end_date <= %s"
            params.append(as_of)
        scope_filter = "AND o.audience_scope = 'national'"

        query = f"""
            WITH latest AS (
                SELECT po.option_type, MAX(o.survey_end_date) AS max_date
                FROM poll_options po
                JOIN poll_observations o ON o.id = po.observation_id
                WHERE po.option_type IN ('party_support', 'presidential_approval')
                  AND o.verified = TRUE
                  {scope_filter}
                  {as_of_filter}
                GROUP BY po.option_type
            )
            SELECT
                po.option_type,
                po.option_name,
                po.value_mid,
                o.pollster,
                o.survey_end_date,
                o.audience_scope,
                o.source_channel,
                COALESCE(o.source_channels, CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END) AS source_channels,
                o.verified
            FROM poll_options po
            JOIN poll_observations o ON o.id = po.observation_id
            JOIN latest l ON l.option_type = po.option_type AND l.max_date = o.survey_end_date
            WHERE po.option_type IN ('party_support', 'presidential_approval')
              {scope_filter}
            ORDER BY po.option_type, po.option_name
        """

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return rows

    def fetch_dashboard_map_latest(self, as_of: date | None, limit: int = 100):
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
                    o.source_channel,
                    COALESCE(
                        o.source_channels,
                        CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END
                    ) AS source_channels,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.region_code, o.office_type
                        ORDER BY o.survey_end_date DESC NULLS LAST,
                                 o.id DESC,
                                 po.value_mid DESC NULLS LAST,
                                 po.option_name
                    ) AS rn
                FROM poll_observations o
                JOIN poll_options po ON po.observation_id = o.id
                WHERE o.verified = TRUE
                  AND po.option_type = 'candidate_matchup'
                  AND po.value_mid IS NOT NULL
                  {as_of_filter}
            )
            SELECT
                r.region_code,
                r.office_type,
                COALESCE(m.title, r.matchup_id) AS title,
                r.value_mid,
                r.survey_end_date,
                r.option_name,
                r.audience_scope,
                r.source_channel,
                r.source_channels
            FROM ranked r
            LEFT JOIN matchups m ON m.matchup_id = r.matchup_id
            WHERE r.rn = 1
            ORDER BY r.region_code, r.office_type
            LIMIT %s
        """

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def fetch_dashboard_big_matches(self, as_of: date | None, limit: int = 3):
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
                s.survey_end_date,
                s.value_mid,
                s.spread,
                lo.audience_scope,
                lo.source_channel,
                lo.source_channels
            FROM scored s
            JOIN latest_obs lo ON lo.id = s.observation_id
            LEFT JOIN matchups m ON m.matchup_id = s.matchup_id
            ORDER BY s.spread ASC NULLS LAST, s.survey_end_date DESC NULLS LAST, s.matchup_id
            LIMIT %s
        """

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def search_regions(self, query: str, limit: int = 20):
        q = f"%{query}%"
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT region_code, sido_name, sigungu_name, admin_level
                FROM regions
                WHERE (sido_name || ' ' || sigungu_name) ILIKE %s
                   OR sido_name ILIKE %s
                   OR sigungu_name ILIKE %s
                ORDER BY admin_level, sido_name, sigungu_name
                LIMIT %s
                """,
                (q, q, q, limit),
            )
            return cur.fetchall()

    def fetch_region_elections(self, region_code: str):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT matchup_id, region_code, office_type, title, is_active
                FROM matchups
                WHERE region_code = %s
                ORDER BY is_active DESC, office_type, title
                """,
                (region_code,),
            )
            rows = cur.fetchall()

            if rows:
                return rows

            cur.execute(
                """
                SELECT DISTINCT
                    matchup_id,
                    region_code,
                    office_type,
                    matchup_id AS title,
                    TRUE AS is_active
                FROM poll_observations
                WHERE region_code = %s
                ORDER BY office_type, matchup_id
                """,
                (region_code,),
            )
            return cur.fetchall()

    def get_matchup(self, matchup_id: str):
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
                    o.id AS observation_id
                FROM poll_observations o
                LEFT JOIN matchups m ON m.matchup_id = o.matchup_id
                WHERE o.matchup_id = %s
                ORDER BY o.survey_end_date DESC NULLS LAST, o.id DESC
                LIMIT 1
                """,
                (matchup_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            cur.execute(
                """
                SELECT
                    option_name,
                    value_mid,
                    value_raw,
                    party_inferred,
                    party_inference_source,
                    party_inference_confidence
                FROM poll_options
                WHERE observation_id = %s
                ORDER BY value_mid DESC NULLS LAST, option_name
                """,
                (row["observation_id"],),
            )
            options = cur.fetchall()

        return {
            "matchup_id": row["matchup_id"],
            "region_code": row["region_code"],
            "office_type": row["office_type"],
            "title": row["title"],
            "pollster": row["pollster"],
            "survey_start_date": row["survey_start_date"],
            "survey_end_date": row["survey_end_date"],
            "confidence_level": row["confidence_level"],
            "sample_size": row["sample_size"],
            "response_rate": row["response_rate"],
            "margin_of_error": row["margin_of_error"],
            "source_grade": row["source_grade"],
            "audience_scope": row["audience_scope"],
            "audience_region_code": row["audience_region_code"],
            "sampling_population_text": row["sampling_population_text"],
            "legal_completeness_score": row["legal_completeness_score"],
            "legal_filled_count": row["legal_filled_count"],
            "legal_required_count": row["legal_required_count"],
            "date_resolution": row["date_resolution"],
            "date_inference_mode": row["date_inference_mode"],
            "date_inference_confidence": row["date_inference_confidence"],
            "nesdc_enriched": row["nesdc_enriched"],
            "needs_manual_review": row["needs_manual_review"],
            "poll_fingerprint": row["poll_fingerprint"],
            "source_channel": row["source_channel"],
            "source_channels": row["source_channels"],
            "verified": row["verified"],
            "options": options,
        }

    def get_candidate(self, candidate_id: str):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.candidate_id, c.name_ko, c.party_name, c.gender,
                    c.birth_date, c.job,
                    cp.career_summary, cp.election_history
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
