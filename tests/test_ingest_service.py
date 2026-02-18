from copy import deepcopy

from app.models.schemas import IngestPayload
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
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "matchup_id": "20260603|광역자치단체장|11-000"
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
