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
        self.review = []

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
        self.options.add((observation_id, option["option_type"], option["option_name"], option["value_mid"]))

    def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):
        self.review.append((entity_type, entity_id, issue_type, review_note))


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
