CREATE TABLE IF NOT EXISTS regions (
    region_code TEXT PRIMARY KEY,
    sido_name TEXT NOT NULL,
    sigungu_name TEXT NOT NULL,
    admin_level TEXT NOT NULL,
    parent_region_code TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS region_topology_versions (
    version_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    effective_from DATE NULL,
    effective_to DATE NULL,
    status TEXT NOT NULL,
    note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'region_topology_versions_mode_check'
    ) THEN
        ALTER TABLE region_topology_versions
            ADD CONSTRAINT region_topology_versions_mode_check
            CHECK (mode IN ('official', 'scenario'));
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'region_topology_versions_status_check'
    ) THEN
        ALTER TABLE region_topology_versions
            ADD CONSTRAINT region_topology_versions_status_check
            CHECK (status IN ('draft', 'announced', 'effective'));
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS region_topology_edges (
    id BIGSERIAL PRIMARY KEY,
    parent_region_code TEXT NOT NULL,
    child_region_code TEXT NOT NULL,
    version_id TEXT NOT NULL REFERENCES region_topology_versions(version_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (version_id, parent_region_code, child_region_code)
);

CREATE INDEX IF NOT EXISTS idx_region_topology_edges_child
    ON region_topology_edges (version_id, child_region_code);
CREATE INDEX IF NOT EXISTS idx_region_topology_edges_parent
    ON region_topology_edges (version_id, parent_region_code);

INSERT INTO region_topology_versions (
    version_id, mode, effective_from, effective_to, status, note
)
VALUES (
    'official-v1', 'official', NULL, NULL, 'effective', 'default official topology'
)
ON CONFLICT (version_id) DO NOTHING;

INSERT INTO region_topology_versions (
    version_id, mode, effective_from, effective_to, status, note
)
VALUES (
    'scenario-gj-jn-merge-v1', 'scenario', NULL, NULL, 'draft', '광주·전남 통합특별시 시나리오'
)
ON CONFLICT (version_id) DO NOTHING;

INSERT INTO region_topology_edges (parent_region_code, child_region_code, version_id)
VALUES
    ('29-46-000', '29-000', 'scenario-gj-jn-merge-v1'),
    ('29-46-000', '46-000', 'scenario-gj-jn-merge-v1')
ON CONFLICT (version_id, parent_region_code, child_region_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    party_name TEXT NULL,
    party_inferred BOOLEAN NOT NULL DEFAULT FALSE,
    party_inference_source TEXT NULL,
    party_inference_confidence FLOAT NULL,
    source_channel TEXT NULL,
    source_channels TEXT[] NULL,
    official_release_at TIMESTAMPTZ NULL,
    article_published_at TIMESTAMPTZ NULL,
    gender TEXT NULL,
    birth_date DATE NULL,
    job TEXT NULL,
    profile_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS party_inferred BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS party_inference_source TEXT NULL,
    ADD COLUMN IF NOT EXISTS party_inference_confidence FLOAT NULL,
    ADD COLUMN IF NOT EXISTS source_channel TEXT NULL,
    ADD COLUMN IF NOT EXISTS source_channels TEXT[] NULL,
    ADD COLUMN IF NOT EXISTS official_release_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS article_published_at TIMESTAMPTZ NULL;

UPDATE candidates
SET source_channels = ARRAY[source_channel]
WHERE source_channels IS NULL
  AND source_channel IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'candidates_source_channel_check'
    ) THEN
        ALTER TABLE candidates
            ADD CONSTRAINT candidates_source_channel_check
            CHECK (source_channel IN ('article', 'nesdc'));
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'candidates_source_channels_check'
    ) THEN
        ALTER TABLE candidates
            ADD CONSTRAINT candidates_source_channels_check
            CHECK (source_channels IS NULL OR source_channels <@ ARRAY['article', 'nesdc']::text[]);
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'candidates_party_inference_source_check'
    ) THEN
        ALTER TABLE candidates
            DROP CONSTRAINT candidates_party_inference_source_check;
    END IF;
    ALTER TABLE candidates
        ADD CONSTRAINT candidates_party_inference_source_check
        CHECK (
            party_inference_source IS NULL
            OR party_inference_source IN (
                'name_rule',
                'article_context',
                'manual',
                'official_registry_v3',
                'incumbent_context_v3'
            )
        );
END;
$$;

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
    date_inference_failed_count INT NOT NULL DEFAULT 0,
    date_inference_estimated_count INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ NULL
);

ALTER TABLE ingestion_runs
    ADD COLUMN IF NOT EXISTS date_inference_failed_count INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS date_inference_estimated_count INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS poll_observations (
    id BIGSERIAL PRIMARY KEY,
    observation_key TEXT NOT NULL UNIQUE,
    article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    survey_name TEXT NOT NULL,
    pollster TEXT NOT NULL,
    poll_block_id TEXT NULL,
    survey_start_date DATE NULL,
    survey_end_date DATE NULL,
    confidence_level FLOAT NULL,
    sample_size INT NULL,
    response_rate FLOAT NULL,
    margin_of_error FLOAT NULL,
    sponsor TEXT NULL,
    method TEXT NULL,
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
    date_inference_mode TEXT NULL,
    date_inference_confidence FLOAT NULL,
    official_release_at TIMESTAMPTZ NULL,
    poll_fingerprint TEXT NULL,
    source_channel TEXT NULL,
    source_channels TEXT[] NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    source_grade TEXT NOT NULL DEFAULT 'C',
    ingestion_run_id BIGINT NULL REFERENCES ingestion_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE poll_observations
    ADD COLUMN IF NOT EXISTS confidence_level FLOAT NULL,
    ADD COLUMN IF NOT EXISTS sponsor TEXT NULL,
    ADD COLUMN IF NOT EXISTS method TEXT NULL,
    ADD COLUMN IF NOT EXISTS poll_block_id TEXT NULL,
    ADD COLUMN IF NOT EXISTS audience_scope TEXT NULL,
    ADD COLUMN IF NOT EXISTS audience_region_code TEXT NULL,
    ADD COLUMN IF NOT EXISTS sampling_population_text TEXT NULL,
    ADD COLUMN IF NOT EXISTS legal_completeness_score FLOAT NULL,
    ADD COLUMN IF NOT EXISTS legal_filled_count INT NULL,
    ADD COLUMN IF NOT EXISTS legal_required_count INT NULL,
    ADD COLUMN IF NOT EXISTS date_resolution TEXT NULL,
    ADD COLUMN IF NOT EXISTS date_inference_mode TEXT NULL,
    ADD COLUMN IF NOT EXISTS date_inference_confidence FLOAT NULL,
    ADD COLUMN IF NOT EXISTS official_release_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS poll_fingerprint TEXT NULL,
    ADD COLUMN IF NOT EXISTS source_channel TEXT NULL,
    ADD COLUMN IF NOT EXISTS source_channels TEXT[] NULL;

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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_observations_source_channels_check'
    ) THEN
        ALTER TABLE poll_observations
            ADD CONSTRAINT poll_observations_source_channels_check
            CHECK (source_channels IS NULL OR source_channels <@ ARRAY['article', 'nesdc']::text[]);
    END IF;
END;
$$;

UPDATE poll_observations
SET source_channels = ARRAY[source_channel]
WHERE source_channels IS NULL
  AND source_channel IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_observations_source_channel_check'
    ) THEN
        ALTER TABLE poll_observations
            ADD CONSTRAINT poll_observations_source_channel_check
            CHECK (source_channel IN ('article', 'nesdc'));
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

CREATE TABLE IF NOT EXISTS elections (
    region_code TEXT NOT NULL REFERENCES regions(region_code) ON DELETE CASCADE,
    office_type TEXT NOT NULL,
    slot_matchup_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'code_master',
    has_poll_data BOOLEAN NOT NULL DEFAULT FALSE,
    latest_matchup_id TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (region_code, office_type)
);

ALTER TABLE elections
    ADD COLUMN IF NOT EXISTS slot_matchup_id TEXT,
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'code_master',
    ADD COLUMN IF NOT EXISTS has_poll_data BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS latest_matchup_id TEXT NULL,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

UPDATE elections
SET slot_matchup_id = COALESCE(slot_matchup_id, 'master|' || office_type || '|' || region_code),
    title = COALESCE(title, office_type)
WHERE slot_matchup_id IS NULL
   OR title IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'elections_source_check'
    ) THEN
        ALTER TABLE elections
            ADD CONSTRAINT elections_source_check
            CHECK (source IN ('code_master', 'observed'));
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS poll_options (
    id BIGSERIAL PRIMARY KEY,
    observation_id BIGINT NOT NULL REFERENCES poll_observations(id) ON DELETE CASCADE,
    poll_block_id TEXT NULL,
    option_type TEXT NOT NULL,
    option_name TEXT NOT NULL,
    candidate_id TEXT NULL,
    party_name TEXT NULL,
    scenario_key TEXT NOT NULL DEFAULT 'default',
    scenario_type TEXT NULL,
    scenario_title TEXT NULL,
    value_raw TEXT NULL,
    value_min FLOAT NULL,
    value_max FLOAT NULL,
    value_mid FLOAT NULL,
    is_missing BOOLEAN NOT NULL DEFAULT FALSE,
    party_inferred BOOLEAN NOT NULL DEFAULT FALSE,
    party_inference_source TEXT NULL,
    party_inference_confidence FLOAT NULL,
    party_inference_evidence TEXT NULL,
    candidate_verified BOOLEAN NOT NULL DEFAULT TRUE,
    candidate_verify_source TEXT NULL,
    candidate_verify_confidence FLOAT NULL,
    candidate_verify_matched_key TEXT NULL,
    needs_manual_review BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT poll_options_observation_option_scenario_unique
        UNIQUE (observation_id, option_type, option_name, scenario_key)
);

ALTER TABLE poll_options
    ADD COLUMN IF NOT EXISTS poll_block_id TEXT NULL,
    ADD COLUMN IF NOT EXISTS candidate_id TEXT NULL,
    ADD COLUMN IF NOT EXISTS party_name TEXT NULL,
    ADD COLUMN IF NOT EXISTS scenario_key TEXT NOT NULL DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS scenario_type TEXT NULL,
    ADD COLUMN IF NOT EXISTS scenario_title TEXT NULL,
    ADD COLUMN IF NOT EXISTS party_inferred BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS party_inference_source TEXT NULL,
    ADD COLUMN IF NOT EXISTS party_inference_confidence FLOAT NULL,
    ADD COLUMN IF NOT EXISTS party_inference_evidence TEXT NULL,
    ADD COLUMN IF NOT EXISTS candidate_verified BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS candidate_verify_source TEXT NULL,
    ADD COLUMN IF NOT EXISTS candidate_verify_confidence FLOAT NULL,
    ADD COLUMN IF NOT EXISTS candidate_verify_matched_key TEXT NULL,
    ADD COLUMN IF NOT EXISTS needs_manual_review BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_options_observation_id_option_type_option_name_key'
    ) THEN
        ALTER TABLE poll_options
            DROP CONSTRAINT poll_options_observation_id_option_type_option_name_key;
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_options_observation_option_scenario_unique'
    ) THEN
        ALTER TABLE poll_options
            ADD CONSTRAINT poll_options_observation_option_scenario_unique
            UNIQUE (observation_id, option_type, option_name, scenario_key);
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_options_party_inference_source_check'
    ) THEN
        ALTER TABLE poll_options
            DROP CONSTRAINT poll_options_party_inference_source_check;
    END IF;
    ALTER TABLE poll_options
        ADD CONSTRAINT poll_options_party_inference_source_check
        CHECK (
            party_inference_source IS NULL
            OR party_inference_source IN (
                'name_rule',
                'article_context',
                'manual',
                'official_registry_v3',
                'incumbent_context_v3'
            )
        );
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_options_candidate_verify_source_check'
    ) THEN
        ALTER TABLE poll_options
            ADD CONSTRAINT poll_options_candidate_verify_source_check
            CHECK (
                candidate_verify_source IS NULL
                OR candidate_verify_source IN ('data_go', 'article_context', 'manual')
            );
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'poll_options_scenario_type_check'
    ) THEN
        ALTER TABLE poll_options
            ADD CONSTRAINT poll_options_scenario_type_check
            CHECK (
                scenario_type IS NULL
                OR scenario_type IN ('head_to_head', 'multi_candidate')
            );
    END IF;
END;
$$;

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
CREATE INDEX IF NOT EXISTS idx_poll_observations_matchup_latest
    ON poll_observations (matchup_id, survey_end_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_poll_observations_scope_date ON poll_observations (audience_scope, survey_end_date DESC);
CREATE INDEX IF NOT EXISTS idx_poll_observations_verified_date
    ON poll_observations (survey_end_date DESC, id DESC)
    WHERE verified = TRUE;
CREATE INDEX IF NOT EXISTS idx_poll_observations_verified_region_office_date
    ON poll_observations (region_code, office_type, survey_end_date DESC, id DESC)
    WHERE verified = TRUE;
CREATE INDEX IF NOT EXISTS idx_poll_observations_fingerprint ON poll_observations (poll_fingerprint);
CREATE INDEX IF NOT EXISTS idx_poll_observations_poll_block ON poll_observations (poll_block_id);
CREATE INDEX IF NOT EXISTS idx_poll_observations_source_channels ON poll_observations USING GIN (source_channels);
CREATE INDEX IF NOT EXISTS idx_candidates_source_channels ON candidates USING GIN (source_channels);
CREATE INDEX IF NOT EXISTS idx_elections_region_active ON elections (region_code, is_active, office_type);
CREATE INDEX IF NOT EXISTS idx_elections_latest_matchup ON elections (latest_matchup_id);
CREATE INDEX IF NOT EXISTS idx_poll_options_type ON poll_options (option_type);
CREATE INDEX IF NOT EXISTS idx_poll_options_poll_block ON poll_options (poll_block_id);
CREATE INDEX IF NOT EXISTS idx_poll_options_observation_value
    ON poll_options (observation_id, value_mid DESC, option_name);
CREATE INDEX IF NOT EXISTS idx_poll_options_summary_type_observation
    ON poll_options (option_type, observation_id, option_name)
    WHERE option_type IN ('party_support', 'president_job_approval', 'election_frame', 'presidential_approval');
CREATE INDEX IF NOT EXISTS idx_poll_options_candidate_matchup_observation_value
    ON poll_options (observation_id, value_mid DESC, option_name)
    WHERE option_type = 'candidate_matchup' AND value_mid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_queue_entity_status
    ON review_queue (entity_type, entity_id, status);
CREATE INDEX IF NOT EXISTS idx_matchups_region_active ON matchups (region_code, is_active);
