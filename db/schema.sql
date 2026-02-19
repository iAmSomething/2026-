CREATE TABLE IF NOT EXISTS regions (
    region_code TEXT PRIMARY KEY,
    sido_name TEXT NOT NULL,
    sigungu_name TEXT NOT NULL,
    admin_level TEXT NOT NULL,
    parent_region_code TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    party_name TEXT NULL,
    gender TEXT NULL,
    birth_date DATE NULL,
    job TEXT NULL,
    profile_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    id BIGSERIAL PRIMARY KEY,
    candidate_id TEXT NOT NULL UNIQUE REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    career_summary TEXT NULL,
    election_history TEXT NULL,
    source_type TEXT NULL,
    source_url TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    published_at TIMESTAMPTZ NULL,
    raw_text TEXT NULL,
    raw_hash TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    extractor_version TEXT NULL,
    llm_model TEXT NULL,
    processed_count INT NOT NULL DEFAULT 0,
    error_count INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS poll_observations (
    id BIGSERIAL PRIMARY KEY,
    observation_key TEXT NOT NULL UNIQUE,
    article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    survey_name TEXT NOT NULL,
    pollster TEXT NOT NULL,
    survey_start_date DATE NULL,
    survey_end_date DATE NULL,
    sample_size INT NULL,
    response_rate FLOAT NULL,
    margin_of_error FLOAT NULL,
    region_code TEXT NOT NULL REFERENCES regions(region_code),
    office_type TEXT NOT NULL,
    matchup_id TEXT NOT NULL,
    audience_scope TEXT NULL,
    audience_region_code TEXT NULL,
    sampling_population_text TEXT NULL,
    legal_completeness_score FLOAT NULL,
    legal_filled_count INT NULL,
    legal_required_count INT NULL,
    date_resolution TEXT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    source_grade TEXT NOT NULL DEFAULT 'C',
    ingestion_run_id BIGINT NULL REFERENCES ingestion_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE poll_observations
    ADD COLUMN IF NOT EXISTS audience_scope TEXT NULL,
    ADD COLUMN IF NOT EXISTS audience_region_code TEXT NULL,
    ADD COLUMN IF NOT EXISTS sampling_population_text TEXT NULL,
    ADD COLUMN IF NOT EXISTS legal_completeness_score FLOAT NULL,
    ADD COLUMN IF NOT EXISTS legal_filled_count INT NULL,
    ADD COLUMN IF NOT EXISTS legal_required_count INT NULL,
    ADD COLUMN IF NOT EXISTS date_resolution TEXT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_observations_audience_scope_check'
    ) THEN
        ALTER TABLE poll_observations
            ADD CONSTRAINT poll_observations_audience_scope_check
            CHECK (audience_scope IN ('national', 'regional', 'local'));
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS matchups (
    matchup_id TEXT PRIMARY KEY,
    election_id TEXT NOT NULL,
    office_type TEXT NOT NULL,
    region_code TEXT NOT NULL REFERENCES regions(region_code),
    title TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS poll_options (
    id BIGSERIAL PRIMARY KEY,
    observation_id BIGINT NOT NULL REFERENCES poll_observations(id) ON DELETE CASCADE,
    option_type TEXT NOT NULL,
    option_name TEXT NOT NULL,
    value_raw TEXT NULL,
    value_min FLOAT NULL,
    value_max FLOAT NULL,
    value_mid FLOAT NULL,
    is_missing BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (observation_id, option_type, option_name)
);

CREATE TABLE IF NOT EXISTS review_queue (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    assigned_to TEXT NULL,
    review_note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regions_search ON regions (sido_name, sigungu_name);
CREATE INDEX IF NOT EXISTS idx_poll_observations_date ON poll_observations (survey_end_date DESC);
CREATE INDEX IF NOT EXISTS idx_poll_observations_matchup ON poll_observations (matchup_id);
CREATE INDEX IF NOT EXISTS idx_poll_observations_scope_date ON poll_observations (audience_scope, survey_end_date DESC);
CREATE INDEX IF NOT EXISTS idx_poll_options_type ON poll_options (option_type);
CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_matchups_region_active ON matchups (region_code, is_active);
