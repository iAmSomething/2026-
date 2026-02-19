from datetime import date

from app.services.repository import PostgresRepository


class _Cursor:
    def __init__(self):
        self.execs: list[str] = []
        self._step = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def execute(self, query, params=None):  # noqa: ARG002
        self.execs.append(query)

    def fetchone(self):
        if self._step == 0:
            self._step += 1
            return {
                "matchup_id": "m1",
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "pollster": "KBS",
                "survey_start_date": date(2026, 2, 15),
                "survey_end_date": date(2026, 2, 18),
                "confidence_level": 95.0,
                "sample_size": 1000,
                "response_rate": 12.3,
                "margin_of_error": 3.1,
                "source_grade": "B",
                "audience_scope": "regional",
                "audience_region_code": "11-000",
                "sampling_population_text": "서울시 거주 만 18세 이상",
                "legal_completeness_score": 0.86,
                "legal_filled_count": 6,
                "legal_required_count": 7,
                "date_resolution": "exact",
                "date_inference_mode": "relative_published_at",
                "date_inference_confidence": 0.92,
                "nesdc_enriched": True,
                "needs_manual_review": True,
                "poll_fingerprint": "f" * 64,
                "source_channel": "article",
                "source_channels": ["article", "nesdc"],
                "verified": True,
                "observation_id": 101,
            }
        return None

    def fetchall(self):
        return [{"option_name": "정원오", "value_mid": 44.0, "value_raw": "44%"}]


class _Conn:
    def __init__(self):
        self.cur = _Cursor()

    def cursor(self):
        return self.cur


def test_get_matchup_returns_legal_metadata_fields():
    repo = PostgresRepository(_Conn())
    out = repo.get_matchup("m1")

    assert out is not None
    assert out["survey_start_date"] == date(2026, 2, 15)
    assert out["confidence_level"] == 95.0
    assert out["sample_size"] == 1000
    assert out["response_rate"] == 12.3
    assert out["audience_scope"] == "regional"
    assert out["date_inference_mode"] == "relative_published_at"
    assert out["date_inference_confidence"] == 0.92
    assert out["nesdc_enriched"] is True
    assert out["needs_manual_review"] is True
