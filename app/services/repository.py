from datetime import date


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

    def upsert_poll_observation(self, observation: dict, article_id: int, ingestion_run_id: int) -> int:
        payload = dict(observation)
        payload["article_id"] = article_id
        payload["ingestion_run_id"] = ingestion_run_id

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poll_observations (
                    observation_key, article_id, survey_name, pollster,
                    survey_start_date, survey_end_date, sample_size,
                    response_rate, margin_of_error, region_code,
                    office_type, matchup_id, verified, source_grade,
                    ingestion_run_id
                )
                VALUES (
                    %(observation_key)s, %(article_id)s, %(survey_name)s, %(pollster)s,
                    %(survey_start_date)s, %(survey_end_date)s, %(sample_size)s,
                    %(response_rate)s, %(margin_of_error)s, %(region_code)s,
                    %(office_type)s, %(matchup_id)s, %(verified)s, %(source_grade)s,
                    %(ingestion_run_id)s
                )
                ON CONFLICT (observation_key) DO UPDATE
                SET article_id=EXCLUDED.article_id,
                    survey_name=EXCLUDED.survey_name,
                    pollster=EXCLUDED.pollster,
                    survey_start_date=EXCLUDED.survey_start_date,
                    survey_end_date=EXCLUDED.survey_end_date,
                    sample_size=EXCLUDED.sample_size,
                    response_rate=EXCLUDED.response_rate,
                    margin_of_error=EXCLUDED.margin_of_error,
                    region_code=EXCLUDED.region_code,
                    office_type=EXCLUDED.office_type,
                    matchup_id=EXCLUDED.matchup_id,
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

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poll_options (
                    observation_id, option_type, option_name,
                    value_raw, value_min, value_max, value_mid, is_missing
                )
                VALUES (
                    %(observation_id)s, %(option_type)s, %(option_name)s,
                    %(value_raw)s, %(value_min)s, %(value_max)s, %(value_mid)s, %(is_missing)s
                )
                ON CONFLICT (observation_id, option_type, option_name) DO UPDATE
                SET value_raw=EXCLUDED.value_raw,
                    value_min=EXCLUDED.value_min,
                    value_max=EXCLUDED.value_max,
                    value_mid=EXCLUDED.value_mid,
                    is_missing=EXCLUDED.is_missing,
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

    def fetch_dashboard_summary(self, as_of: date | None):
        params = []
        as_of_filter = ""
        if as_of is not None:
            as_of_filter = "AND o.survey_end_date <= %s"
            params.append(as_of)

        query = f"""
            WITH latest AS (
                SELECT po.option_type, MAX(o.survey_end_date) AS max_date
                FROM poll_options po
                JOIN poll_observations o ON o.id = po.observation_id
                WHERE po.option_type IN ('party_support', 'presidential_approval')
                  AND o.verified = TRUE
                  {as_of_filter}
                GROUP BY po.option_type
            )
            SELECT po.option_type, po.option_name, po.value_mid, o.pollster, o.survey_end_date, o.verified
            FROM poll_options po
            JOIN poll_observations o ON o.id = po.observation_id
            JOIN latest l ON l.option_type = po.option_type AND l.max_date = o.survey_end_date
            WHERE po.option_type IN ('party_support', 'presidential_approval')
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
                r.option_name
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
                    matchup_id,
                    survey_end_date,
                    MAX(value_mid) FILTER (WHERE option_rank = 1) AS value_mid,
                    MAX(value_mid) FILTER (WHERE option_rank = 1)
                      - MAX(value_mid) FILTER (WHERE option_rank = 2) AS spread
                FROM ranked_options
                GROUP BY matchup_id, survey_end_date
            )
            SELECT
                s.matchup_id,
                COALESCE(m.title, s.matchup_id) AS title,
                s.survey_end_date,
                s.value_mid,
                s.spread
            FROM scored s
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
                    o.pollster,
                    o.survey_end_date,
                    o.margin_of_error,
                    o.source_grade,
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
                SELECT option_name, value_mid, value_raw
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
            "survey_end_date": row["survey_end_date"],
            "margin_of_error": row["margin_of_error"],
            "source_grade": row["source_grade"],
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
