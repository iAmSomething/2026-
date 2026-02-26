from copy import deepcopy

from app.models.schemas import IngestPayload
from app.services.errors import DuplicateConflictError
from app.services.ingest_service import ingest_payload


class FakeRepo:
    def __init__(self):
        self.run_id = 0
        self.articles = {}
        self.observations = {}
        self.options = set()
        self.option_rows = []
        self.review = []
        self.policy_counters = []

    def create_ingestion_run(self, run_type, extractor_version, llm_model):
        self.run_id += 1
        return self.run_id

    def finish_ingestion_run(self, run_id, status, processed_count, error_count):
        self.last_run = (run_id, status, processed_count, error_count)

    def upsert_region(self, region):
        pass

    def upsert_matchup(self, matchup):
        pass

    def upsert_candidate(self, candidate):
        pass

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
                option.get("needs_manual_review"),
            )
        )

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
                "sampling_population_text": "서울 거주 만 18세 이상",
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
