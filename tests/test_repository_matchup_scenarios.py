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
                "region_code": "26-000",
                "office_type": "광역자치단체장",
                "title": "부산시장 가상대결",
                "is_active": True,
            }
        if self._step == 1:
            self._step += 1
            return {
                "matchup_id": "m1",
                "region_code": "26-000",
                "office_type": "광역자치단체장",
                "title": "부산시장 가상대결",
                "pollster": "테스트리서치",
                "survey_start_date": date(2026, 2, 15),
                "survey_end_date": date(2026, 2, 18),
                "confidence_level": 95.0,
                "sample_size": 1000,
                "response_rate": 12.3,
                "margin_of_error": 3.1,
                "source_grade": "B",
                "audience_scope": "regional",
                "audience_region_code": "26-000",
                "sampling_population_text": "부산 거주 만 18세 이상",
                "legal_completeness_score": 0.86,
                "legal_filled_count": 6,
                "legal_required_count": 7,
                "date_resolution": "exact",
                "date_inference_mode": "relative_published_at",
                "date_inference_confidence": 0.92,
                "observation_updated_at": "2026-02-18T03:00:00+00:00",
                "official_release_at": None,
                "article_published_at": "2026-02-18T01:00:00+00:00",
                "nesdc_enriched": True,
                "needs_manual_review": False,
                "poll_fingerprint": "f" * 64,
                "source_channel": "article",
                "source_channels": ["article", "nesdc"],
                "verified": True,
                "observation_id": 777,
                "options": [
                    {
                        "option_name": "전재수",
                        "candidate_id": "cand-jjs",
                        "party_name": None,
                        "scenario_key": "h2h-a",
                        "scenario_type": "head_to_head",
                        "scenario_title": "전재수 vs 박형준",
                        "value_mid": 43.4,
                        "value_raw": "43.4%",
                        "party_inferred": True,
                        "party_inference_source": "name_rule",
                        "party_inference_confidence": 0.81,
                        "needs_manual_review": False,
                    },
                    {
                        "option_name": "박형준",
                        "candidate_id": "cand-phj",
                        "party_name": "국민의힘",
                        "scenario_key": "h2h-a",
                        "scenario_type": "head_to_head",
                        "scenario_title": "전재수 vs 박형준",
                        "value_mid": 32.3,
                        "value_raw": "32.3%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    },
                    {
                        "option_name": "전재수",
                        "candidate_id": "cand-jjs",
                        "party_name": "더불어민주당",
                        "scenario_key": "h2h-b",
                        "scenario_type": "head_to_head",
                        "scenario_title": "전재수 vs 김도읍",
                        "value_mid": 43.8,
                        "value_raw": "43.8%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    },
                    {
                        "option_name": "김도읍",
                        "candidate_id": "cand-kdu",
                        "party_name": "국민의힘",
                        "scenario_key": "h2h-b",
                        "scenario_type": "head_to_head",
                        "scenario_title": "전재수 vs 김도읍",
                        "value_mid": 33.2,
                        "value_raw": "33.2%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    },
                    {
                        "option_name": "전재수",
                        "candidate_id": "cand-jjs",
                        "party_name": "더불어민주당",
                        "scenario_key": "multi-a",
                        "scenario_type": "multi_candidate",
                        "scenario_title": "전재수·박형준·김도읍",
                        "value_mid": 26.8,
                        "value_raw": "26.8%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    },
                ],
            }
        return None


class _Conn:
    def __init__(self):
        self.cur = _Cursor()

    def cursor(self):
        return self.cur


def test_get_matchup_groups_options_by_scenario_without_overwrite():
    repo = PostgresRepository(_Conn())

    out = repo.get_matchup("m1")

    assert out is not None
    assert len(out["scenarios"]) == 3

    jeon_values = [
        option["value_mid"]
        for scenario in out["scenarios"]
        for option in scenario["options"]
        if option["candidate_id"] == "cand-jjs"
    ]
    assert sorted(jeon_values) == [26.8, 43.4, 43.8]

    unknown_party_count = sum(
        1
        for scenario in out["scenarios"]
        for option in scenario["options"]
        if option["party_name"] == "미확정(검수대기)"
    )
    assert unknown_party_count == 1
    assert all(scenario["scenario_type"] in {"head_to_head", "multi_candidate"} for scenario in out["scenarios"])
    assert len(out["options"]) == 2


def test_normalize_options_filters_noise_candidate_tokens():
    options = [
        {"option_name": "오차는", "candidate_id": None, "scenario_key": "default", "value_mid": 95.0},
        {"option_name": "민주", "candidate_id": None, "scenario_key": "default", "value_mid": 45.0},
        {"option_name": "같은", "candidate_id": None, "scenario_key": "default", "value_mid": 28.0},
        {"option_name": "국힘", "candidate_id": None, "scenario_key": "default", "value_mid": 17.0},
        {"option_name": "차이", "candidate_id": None, "scenario_key": "default", "value_mid": 16.0},
        {"option_name": "정원오", "candidate_id": None, "scenario_key": "default", "value_mid": 44.0},
        {"option_name": "오세훈", "candidate_id": "cand-oh", "scenario_key": "default", "value_mid": 42.0},
        {"option_name": "김민주", "candidate_id": None, "scenario_key": "default", "value_mid": 12.0},
    ]

    normalized = PostgresRepository._normalize_options(options)
    names = [row["option_name"] for row in normalized]

    assert names == ["정원오", "오세훈", "김민주"]
