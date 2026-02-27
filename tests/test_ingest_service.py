from copy import deepcopy
import json

from app.models.schemas import IngestPayload
from app.services.errors import DuplicateConflictError
import app.services.ingest_service as ingest_service_module
from app.services.ingest_service import ingest_payload


class FakeRepo:
    def __init__(self):
        self.run_id = 0
        self.articles = {}
        self.matchups = []
        self.observations = {}
        self.options = set()
        self.option_rows = []
        self.candidate_rows = []
        self.review = []
        self.policy_counters = []
        self.cleanup_default_calls = 0

    def create_ingestion_run(self, run_type, extractor_version, llm_model):
        self.run_id += 1
        return self.run_id

    def finish_ingestion_run(self, run_id, status, processed_count, error_count):
        self.last_run = (run_id, status, processed_count, error_count)

    def upsert_region(self, region):
        pass

    def upsert_matchup(self, matchup):
        self.matchups.append(matchup)

    def upsert_candidate(self, candidate):
        self.candidate_rows.append(candidate)

    def upsert_article(self, article):
        self.articles[article["url"]] = article
        return 1

    def upsert_poll_observation(self, observation, article_id, ingestion_run_id):
        self.observations[observation["observation_key"]] = observation
        return 1

    def upsert_poll_option(self, observation_id, option):
        self.option_rows.append(option)
        self.options.add(
            (
                observation_id,
                option["option_type"],
                option["option_name"],
                option["value_mid"],
                option.get("party_inferred"),
                option.get("party_inference_source"),
                option.get("party_inference_confidence"),
                option.get("candidate_verified"),
                option.get("candidate_verify_source"),
                option.get("candidate_verify_confidence"),
                option.get("candidate_verify_matched_key"),
                option.get("needs_manual_review"),
            )
        )

    def delete_candidate_default_poll_options(self, observation_id):  # noqa: ARG002
        self.cleanup_default_calls += 1
        self.option_rows = [
            row
            for row in self.option_rows
            if not (row.get("option_type") == "candidate_matchup" and row.get("scenario_key") == "default")
        ]
        self.options = {
            (
                observation_id,
                row["option_type"],
                row["option_name"],
                row["value_mid"],
                row.get("party_inferred"),
                row.get("party_inference_source"),
                row.get("party_inference_confidence"),
                row.get("candidate_verified"),
                row.get("candidate_verify_source"),
                row.get("candidate_verify_confidence"),
                row.get("needs_manual_review"),
            )
            for row in self.option_rows
        }
        return 1

    def fetch_candidate_default_poll_options(self, observation_id):  # noqa: ARG002
        return [
            {
                "option_name": row.get("option_name"),
                "value_raw": row.get("value_raw"),
                "value_min": row.get("value_min"),
                "value_max": row.get("value_max"),
                "value_mid": row.get("value_mid"),
                "is_missing": row.get("is_missing"),
            }
            for row in self.option_rows
            if row.get("option_type") == "candidate_matchup" and row.get("scenario_key") == "default"
        ]

    def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):
        self.review.append((entity_type, entity_id, issue_type, review_note))

    def update_ingestion_policy_counters(
        self,
        run_id,
        *,
        date_inference_failed_count=0,
        date_inference_estimated_count=0,
    ):
        self.policy_counters.append((run_id, date_inference_failed_count, date_inference_estimated_count))


PAYLOAD = {
    "run_type": "manual",
    "extractor_version": "manual-v1",
    "records": [
        {
            "article": {
                "url": "https://example.com/1",
                "title": "sample",
                "publisher": "pub"
            },
            "region": {
                "region_code": "11-000",
                "sido_name": "서울특별시",
                "sigungu_name": "전체",
                "admin_level": "sido"
            },
            "observation": {
                "observation_key": "obs-1",
                "survey_name": "survey",
                "pollster": "MBC",
                "confidence_level": 95.0,
                "sponsor": "서울일보",
                "method": "전화면접",
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "matchup_id": "20260603|광역자치단체장|11-000",
                "audience_scope": "national",
                "audience_region_code": "11-000",
                "sampling_population_text": "전국 만 18세 이상 남녀",
                "legal_completeness_score": 0.86,
                "legal_filled_count": 6,
                "legal_required_count": 7,
                "date_resolution": "exact",
                "source_channels": ["article"],
            },
            "options": [
                {"option_type": "presidential_approval", "option_name": "국정안정론", "value_raw": "53~55%"}
            ]
        }
    ]
}


def test_idempotent_ingest_no_duplicate_records():
    repo = FakeRepo()
    payload = IngestPayload.model_validate(deepcopy(PAYLOAD))

    ingest_payload(payload, repo)
    ingest_payload(payload, repo)

    assert len(repo.articles) == 1
    assert len(repo.observations) == 1
    assert len(repo.options) == 1
    assert repo.option_rows[0]["option_type"] == "election_frame"
    assert repo.option_rows[0]["candidate_verified"] is True
    assert repo.option_rows[0]["scenario_key"] == "default"
    assert repo.observations["obs-1"]["audience_scope"] == "national"
    assert repo.observations["obs-1"]["legal_filled_count"] == 6
    assert len(repo.observations["obs-1"]["poll_fingerprint"]) == 64
    assert repo.observations["obs-1"]["source_channels"] == ["article"]
    assert repo.observations["obs-1"]["confidence_level"] == 95.0


def test_ingest_error_pushes_review_queue():
    class BrokenRepo(FakeRepo):
        def upsert_poll_observation(self, observation, article_id, ingestion_run_id):
            raise RuntimeError("forced error")

    repo = BrokenRepo()
    payload = IngestPayload.model_validate(deepcopy(PAYLOAD))

    result = ingest_payload(payload, repo)

    assert result.error_count == 1
    assert len(repo.review) == 1
    assert repo.review[0][2] == "ingestion_error"


def test_scope_inference_from_population_text_sets_regional_scope_and_region_code():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["audience_scope"] = None
    payload_data["records"][0]["observation"]["audience_region_code"] = None
    payload_data["records"][0]["observation"]["sampling_population_text"] = "서울시 거주 만 18세 이상 남녀"
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert result.error_count == 0
    assert repo.observations["obs-1"]["audience_scope"] == "regional"
    assert repo.observations["obs-1"]["audience_region_code"] == "11-000"


def test_scope_conflict_between_declared_and_population_hard_fails_record():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["audience_scope"] = "national"
    payload_data["records"][0]["observation"]["audience_region_code"] = None
    payload_data["records"][0]["observation"]["sampling_population_text"] = "서울시 거주 만 18세 이상 남녀"
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "partial_success"
    assert result.processed_count == 0
    assert result.error_count == 1
    assert "obs-1" not in repo.observations
    assert any(
        row[2] == "mapping_error" and "AUDIENCE_SCOPE_CONFLICT_POPULATION" in row[3]
        for row in repo.review
    )


def test_scope_conflict_between_declared_and_population_region_hard_fails_record():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["audience_scope"] = "regional"
    payload_data["records"][0]["observation"]["audience_region_code"] = "26-000"
    payload_data["records"][0]["observation"]["sampling_population_text"] = "서울시 거주 만 18세 이상 남녀"
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "partial_success"
    assert result.processed_count == 0
    assert result.error_count == 1
    assert "obs-1" not in repo.observations
    assert any(
        row[2] == "mapping_error" and "AUDIENCE_SCOPE_CONFLICT_REGION" in row[3]
        for row in repo.review
    )


def test_scope_inference_from_population_text_sets_local_scope_and_region_code():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["region_code"] = "11-680"
    payload_data["records"][0]["observation"]["matchup_id"] = "20260603|기초자치단체장|11-680"
    payload_data["records"][0]["observation"]["office_type"] = "기초자치단체장"
    payload_data["records"][0]["observation"]["audience_scope"] = None
    payload_data["records"][0]["observation"]["audience_region_code"] = None
    payload_data["records"][0]["observation"]["sampling_population_text"] = "서울 강남구 거주 만 18세 이상 남녀"
    payload_data["records"][0]["region"]["region_code"] = "11-680"
    payload_data["records"][0]["region"]["sigungu_name"] = "강남구"
    payload_data["records"][0]["region"]["admin_level"] = "sigungu"
    payload_data["records"][0]["region"]["parent_region_code"] = "11-000"
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert result.error_count == 0
    assert repo.observations["obs-1"]["audience_scope"] == "local"
    assert repo.observations["obs-1"]["audience_region_code"] == "11-680"


def test_duplicate_conflict_routes_to_specific_review_issue_type():
    class ConflictRepo(FakeRepo):
        def upsert_poll_observation(self, observation, article_id, ingestion_run_id):  # noqa: ARG002
            raise DuplicateConflictError("DUPLICATE_CONFLICT core fields mismatch: sample_size")

    repo = ConflictRepo()
    payload = IngestPayload.model_validate(deepcopy(PAYLOAD))
    result = ingest_payload(payload, repo)

    assert result.error_count == 1
    assert len(repo.review) == 1
    assert repo.review[0][2] == "DUPLICATE_CONFLICT"


def test_uncertain_date_inference_routes_review_and_updates_run_counters():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["date_inference_mode"] = "estimated_timestamp"
    payload_data["records"][0]["observation"]["date_inference_confidence"] = 0.55
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert any(row[2] == "extract_error" for row in repo.review)
    assert repo.policy_counters[-1] == (result.run_id, 0, 1)


def test_low_party_inference_confidence_routes_review_queue():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["options"][0]["party_inferred"] = True
    payload_data["records"][0]["options"][0]["party_inference_source"] = "name_rule"
    payload_data["records"][0]["options"][0]["party_inference_confidence"] = 0.55
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert any(row[2] == "party_inference_low_confidence" for row in repo.review)


def test_party_inference_v3_uses_candidate_registry_context_with_evidence():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["candidates"] = [
        {"candidate_id": "cand-jwo", "name_ko": "정원오", "party_name": "더불어민주당"}
    ]
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "정원오", "value_raw": "44%"}
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    row = repo.option_rows[0]
    assert row["party_name"] == "더불어민주당"
    assert row["party_inferred"] is True
    assert row["party_inference_source"] == "official_registry_v3"
    assert float(row["party_inference_confidence"]) >= 0.9
    evidence = json.loads(str(row["party_inference_evidence"]))
    assert evidence["rule"] == "candidate_context_counter"
    assert evidence["selected_party"] == "더불어민주당"


def test_party_inference_v3_conflict_routes_low_confidence_review():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["candidates"] = [
        {"candidate_id": "cand-a1", "name_ko": "홍길동", "party_name": "더불어민주당"},
        {"candidate_id": "cand-a2", "name_ko": "홍길동", "party_name": "국민의힘"},
    ]
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "홍길동", "value_raw": "41%"}
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    row = repo.option_rows[0]
    assert row["party_inferred"] is True
    assert row["party_inference_source"] == "incumbent_context_v3"
    assert float(row["party_inference_confidence"]) < 0.8
    assert row["needs_manual_review"] is True
    assert any(item[2] == "party_inference_low_confidence" for item in repo.review)
    evidence = json.loads(str(row["party_inference_evidence"]))
    assert evidence["rule"] == "candidate_context_counter"
    assert evidence["total_count"] == 2


def test_ambiguous_presidential_option_routes_mapping_error_review_queue():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["options"][0]["option_name"] = "국정안정 긍정평가"
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert any(row[2] == "mapping_error" for row in repo.review)
    assert repo.option_rows[0]["option_type"] == "presidential_approval"
    assert repo.option_rows[0]["needs_manual_review"] is True


def test_article_source_record_before_cutoff_is_blocked():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["article"]["published_at"] = "2025-11-30T23:59:59+09:00"
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "partial_success"
    assert result.processed_count == 0
    assert result.error_count == 1
    assert len(repo.articles) == 0
    assert len(repo.observations) == 0
    assert any("ARTICLE_PUBLISHED_AT_CUTOFF_BLOCK" in row[3] for row in repo.review)


def test_record_with_survey_end_before_cutoff_is_blocked_even_if_article_is_new():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["article"]["published_at"] = "2026-01-15T09:00:00+09:00"
    payload_data["records"][0]["observation"]["survey_end_date"] = "2025-11-30"
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "partial_success"
    assert result.processed_count == 0
    assert result.error_count == 1
    assert len(repo.articles) == 0
    assert len(repo.observations) == 0
    assert any("STALE_CYCLE_BLOCK" in row[3] for row in repo.review)
    assert any("SURVEY_END_DATE_BEFORE_CUTOFF" in row[3] for row in repo.review)


def test_nesdc_source_record_without_article_published_at_is_allowed():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["source_channel"] = "nesdc"
    payload_data["records"][0]["observation"]["source_channels"] = ["nesdc"]
    payload_data["records"][0]["article"]["published_at"] = None
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert result.processed_count == 1
    assert result.error_count == 0
    assert len(repo.articles) == 1


def test_candidate_noise_token_routes_manual_review_mapping_error():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "응답률은", "value_raw": "44%"}
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert repo.option_rows[0]["candidate_verified"] is False
    assert repo.option_rows[0]["candidate_verify_source"] == "manual"
    assert str(repo.option_rows[0]["candidate_verify_matched_key"]).startswith("noise:")
    assert repo.option_rows[0]["needs_manual_review"] is True
    assert any(row[2] == "mapping_error" and "CANDIDATE_TOKEN_NOISE" in row[3] for row in repo.review)


def test_candidate_party_alias_token_routes_manual_review_mapping_error():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "민주", "value_raw": "45%"}
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert repo.option_rows[0]["candidate_verified"] is False
    assert repo.option_rows[0]["candidate_verify_source"] == "manual"
    assert str(repo.option_rows[0]["candidate_verify_matched_key"]).startswith("noise:")
    assert repo.option_rows[0]["needs_manual_review"] is True
    assert any(row[2] == "mapping_error" and "CANDIDATE_TOKEN_NOISE" in row[3] for row in repo.review)


def test_candidate_particle_noise_token_routes_manual_review_mapping_error():
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "국민의힘은", "value_raw": "45%"},
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert repo.option_rows[0]["candidate_verified"] is False
    assert repo.option_rows[0]["candidate_verify_source"] == "manual"
    assert str(repo.option_rows[0]["candidate_verify_matched_key"]).startswith("noise:")
    assert repo.option_rows[0]["needs_manual_review"] is True
    assert any(row[2] == "mapping_error" and "CANDIDATE_TOKEN_NOISE" in row[3] for row in repo.review)


def test_candidate_data_go_verified_sets_data_go_source(monkeypatch):
    class _FakeVerifier:
        def enrich_candidate(self, candidate):  # noqa: ANN001
            return candidate

        def verify_candidate(self, *, candidate_name, party_name=None):  # noqa: ARG002
            return (candidate_name == "정원오", 0.97)

    def fake_build_service(*, record, sg_typecode):  # noqa: ARG001
        return _FakeVerifier()

    monkeypatch.setattr(ingest_service_module, "_build_candidate_service", fake_build_service)

    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["candidates"] = [
        {
            "candidate_id": "cand-jwo",
            "name_ko": "정원오",
            "party_name": "더불어민주당",
        }
    ]
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "정원오", "value_raw": "44%"}
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert repo.option_rows[0]["candidate_verified"] is True
    assert repo.option_rows[0]["candidate_verify_source"] == "data_go"
    assert float(repo.option_rows[0]["candidate_verify_confidence"]) >= 0.9
    assert repo.option_rows[0]["candidate_verify_matched_key"] == "data_go:cand-jwo"


def test_candidate_profile_enrichment_fills_candidate_fields(monkeypatch):
    class _FakeService:
        def enrich_candidate(self, candidate):  # noqa: ANN001
            out = dict(candidate)
            out["party_name"] = "더불어민주당"
            out["gender"] = "M"
            out["birth_date"] = "1968-08-12"
            out["job"] = "정치인"
            out["career_summary"] = "성동구청장"
            out["election_history"] = "2018 지방선거 당선"
            return out

        def verify_candidate(self, *, candidate_name, party_name=None):  # noqa: ARG002
            return (candidate_name == "정원오", 0.98)

    def fake_build_service(*, record, sg_typecode):  # noqa: ARG001
        return _FakeService()

    monkeypatch.setattr(ingest_service_module, "_build_candidate_service", fake_build_service)

    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["candidates"] = [
        {
            "candidate_id": "cand-jwo",
            "name_ko": "정원오",
            "party_name": None,
            "gender": None,
            "birth_date": None,
            "job": None,
            "career_summary": None,
            "election_history": None,
        }
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert len(repo.candidate_rows) == 1
    row = repo.candidate_rows[0]
    assert row["party_name"] == "더불어민주당"
    assert row["career_summary"] == "성동구청장"
    assert row["election_history"] == "2018 지방선거 당선"


def test_candidate_profile_incomplete_routes_mapping_error(monkeypatch):
    class _FakeService:
        def enrich_candidate(self, candidate):  # noqa: ANN001
            out = dict(candidate)
            out["party_name"] = None
            out["career_summary"] = None
            out["election_history"] = None
            return out

        def verify_candidate(self, *, candidate_name, party_name=None):  # noqa: ARG002
            return (False, 0.0)

    def fake_build_service(*, record, sg_typecode):  # noqa: ARG001
        return _FakeService()

    monkeypatch.setattr(ingest_service_module, "_build_candidate_service", fake_build_service)

    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["candidates"] = [
        {
            "candidate_id": "cand-jwo",
            "name_ko": "정원오",
            "party_name": None,
            "gender": None,
            "birth_date": None,
            "job": None,
            "career_summary": None,
            "election_history": None,
        }
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    assert any(
        row[0] == "candidate" and row[1] == "cand-jwo" and row[2] == "mapping_error" and "CANDIDATE_PROFILE_INCOMPLETE" in row[3]
        for row in repo.review
    )


def test_candidate_matchup_scenarios_are_split_when_default_would_mix_groups() -> None:
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["survey_name"] = (
        "[2026지방선거] 부산시장, 전재수 43.4-박형준 32.3%, "
        "전재수 43.8%-김도읍33.2%...다자대결 전재수26.8% 선두"
    )
    payload_data["records"][0]["candidates"] = [
        {"candidate_id": "cand-js", "name_ko": "전재수", "party_name": "더불어민주당"},
        {"candidate_id": "cand-phj", "name_ko": "박형준", "party_name": "국민의힘"},
        {"candidate_id": "cand-kdy", "name_ko": "김도읍", "party_name": "국민의힘"},
    ]
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "박형준", "value_raw": "32.3%"},
        {"option_type": "candidate_matchup", "option_name": "전재수", "value_raw": "43.8%"},
        {"option_type": "candidate_matchup", "option_name": "김도읍", "value_raw": "33.2%"},
        {"option_type": "candidate_matchup", "option_name": "전재수", "value_raw": "26.8%"},
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    option_rows = [row for row in repo.option_rows if row["option_type"] == "candidate_matchup"]
    scenario_keys = {row.get("scenario_key") for row in option_rows}
    scenario_types = {row.get("scenario_type") for row in option_rows}
    assert "default" not in scenario_keys
    assert len(scenario_keys) >= 3
    assert "h2h-전재수-박형준" in scenario_keys
    assert "h2h-전재수-김도읍" in scenario_keys
    assert "multi-전재수" in scenario_keys
    assert "head_to_head" in scenario_types
    assert "multi_candidate" in scenario_types
    assert {row["option_name"] for row in option_rows} == {"전재수", "박형준", "김도읍"}
    grouped = {}
    for row in option_rows:
        grouped.setdefault(row.get("scenario_key"), []).append(row["option_name"])
    assert set(grouped["h2h-전재수-박형준"]) == {"전재수", "박형준"}
    assert set(grouped["h2h-전재수-김도읍"]) == {"전재수", "김도읍"}


def test_candidate_matchup_scenarios_drop_default_when_explicit_and_multi_coexist() -> None:
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["observation"]["survey_name"] = (
        "[2026지방선거] 부산시장 양자대결 전재수 43.4-박형준 32.3%, "
        "전재수 43.8%-김도읍33.2%...다자대결 전재수26.8%, 박형준 19.1%, 김도읍 10.6%, "
        "조경태 10.1%, 조국 6.7%, 박재호 6.4%, 이재성 5.8%, 윤택근 2.4% 순"
    )
    payload_data["records"][0]["candidates"] = [
        {"candidate_id": "cand-js", "name_ko": "전재수", "party_name": "더불어민주당"},
        {"candidate_id": "cand-phj", "name_ko": "박형준", "party_name": "국민의힘"},
        {"candidate_id": "cand-kdy", "name_ko": "김도읍", "party_name": "국민의힘"},
    ]
    payload_data["records"][0]["options"] = [
        {
            "option_type": "candidate_matchup",
            "option_name": "전재수",
            "value_raw": "43.4%",
            "scenario_key": "h2h-전재수-박형준",
            "scenario_type": "head_to_head",
            "scenario_title": "전재수 vs 박형준",
        },
        {
            "option_type": "candidate_matchup",
            "option_name": "박형준",
            "value_raw": "32.3%",
            "scenario_key": "h2h-전재수-박형준",
            "scenario_type": "head_to_head",
            "scenario_title": "전재수 vs 박형준",
        },
        {
            "option_type": "candidate_matchup",
            "option_name": "전재수",
            "value_raw": "43.8%",
            "scenario_key": "h2h-전재수-김도읍",
            "scenario_type": "head_to_head",
            "scenario_title": "전재수 vs 김도읍",
        },
        {
            "option_type": "candidate_matchup",
            "option_name": "김도읍",
            "value_raw": "33.2%",
            "scenario_key": "h2h-전재수-김도읍",
            "scenario_type": "head_to_head",
            "scenario_title": "전재수 vs 김도읍",
        },
        {
            "option_type": "candidate_matchup",
            "option_name": "전재수",
            "value_raw": "26.8%",
            "scenario_key": "multi-전재수",
            "scenario_type": "multi_candidate",
            "scenario_title": "다자대결",
        },
        {"option_type": "candidate_matchup", "option_name": "박형준", "value_raw": "24.0%", "scenario_key": "default"},
        {"option_type": "candidate_matchup", "option_name": "김도읍", "value_raw": "20.0%", "scenario_key": "default"},
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    option_rows = [row for row in repo.option_rows if row["option_type"] == "candidate_matchup"]
    scenario_keys = {row.get("scenario_key") for row in option_rows}
    assert "default" not in scenario_keys

    multi_rows = [row for row in option_rows if row.get("scenario_key") == "multi-전재수"]
    assert {row["option_name"] for row in multi_rows} == {
        "전재수",
        "박형준",
        "김도읍",
        "조경태",
        "조국",
        "박재호",
        "이재성",
        "윤택근",
    }
    value_by_name = {row["option_name"]: row["value_mid"] for row in multi_rows}
    assert value_by_name == {
        "전재수": 26.8,
        "박형준": 19.1,
        "김도읍": 10.6,
        "조경태": 10.1,
        "조국": 6.7,
        "박재호": 6.4,
        "이재성": 5.8,
        "윤택근": 2.4,
    }
    assert {row.get("scenario_type") for row in multi_rows} == {"multi_candidate"}


def test_survey_name_correction_promotes_busan_mayor_to_metro_office() -> None:
    repo = FakeRepo()
    payload_data = deepcopy(PAYLOAD)
    payload_data["records"][0]["article"]["title"] = "부산시장 양자대결"
    payload_data["records"][0]["observation"]["survey_name"] = "부산시장 양자대결 전재수 43.4-박형준 32.3"
    payload_data["records"][0]["observation"]["region_code"] = "26-710"
    payload_data["records"][0]["observation"]["office_type"] = "기초자치단체장"
    payload_data["records"][0]["observation"]["matchup_id"] = "2026_local|기초자치단체장|26-710"
    payload_data["records"][0]["observation"]["audience_scope"] = None
    payload_data["records"][0]["observation"]["audience_region_code"] = None
    payload_data["records"][0]["observation"]["sampling_population_text"] = "부산 만 18세 이상 남녀"
    payload_data["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "전재수", "value_raw": "43.4%"},
        {"option_type": "candidate_matchup", "option_name": "박형준", "value_raw": "32.3%"},
    ]
    payload = IngestPayload.model_validate(payload_data)

    result = ingest_payload(payload, repo)

    assert result.status == "success"
    observation = repo.observations["obs-1"]
    assert observation["region_code"] == "26-000"
    assert observation["office_type"] == "광역자치단체장"
    assert observation["matchup_id"] == "2026_local|광역자치단체장|26-000"
    assert observation["audience_scope"] == "regional"
    assert observation["audience_region_code"] == "26-000"
    assert repo.matchups[-1]["matchup_id"] == "2026_local|광역자치단체장|26-000"


def test_explicit_candidate_scenario_ingest_cleans_previous_default_rows() -> None:
    repo = FakeRepo()

    baseline_payload = deepcopy(PAYLOAD)
    baseline_payload["records"][0]["observation"]["survey_name"] = "부산시장 후보 지지도"
    baseline_payload["records"][0]["options"] = [
        {"option_type": "candidate_matchup", "option_name": "전재수", "value_raw": "26.8%"},
        {"option_type": "candidate_matchup", "option_name": "박형준", "value_raw": "24.0%"},
        {"option_type": "candidate_matchup", "option_name": "김도읍", "value_raw": "20.0%"},
    ]
    ingest_payload(IngestPayload.model_validate(baseline_payload), repo)

    assert any(
        row.get("option_type") == "candidate_matchup" and row.get("scenario_key") == "default"
        for row in repo.option_rows
    )

    explicit_payload = deepcopy(PAYLOAD)
    explicit_payload["records"][0]["observation"]["survey_name"] = "부산시장 양자대결/다자대결"
    explicit_payload["records"][0]["options"] = [
        {
            "option_type": "candidate_matchup",
            "option_name": "전재수",
            "value_raw": "43.4%",
            "scenario_key": "h2h-전재수-박형준",
            "scenario_type": "head_to_head",
            "scenario_title": "전재수 vs 박형준",
        },
        {
            "option_type": "candidate_matchup",
            "option_name": "박형준",
            "value_raw": "32.3%",
            "scenario_key": "h2h-전재수-박형준",
            "scenario_type": "head_to_head",
            "scenario_title": "전재수 vs 박형준",
        },
        {
            "option_type": "candidate_matchup",
            "option_name": "전재수",
            "value_raw": "26.8%",
            "scenario_key": "multi-전재수",
            "scenario_type": "multi_candidate",
            "scenario_title": "다자대결",
        },
    ]
    ingest_payload(IngestPayload.model_validate(explicit_payload), repo)

    assert repo.cleanup_default_calls >= 1
    assert all(
        not (row.get("option_type") == "candidate_matchup" and row.get("scenario_key") == "default")
        for row in repo.option_rows
    )
    multi_rows = [
        row
        for row in repo.option_rows
        if row.get("option_type") == "candidate_matchup" and row.get("scenario_key") == "multi-전재수"
    ]
    assert {row.get("option_name") for row in multi_rows} == {"전재수", "박형준", "김도읍"}
