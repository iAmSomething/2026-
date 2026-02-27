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
                "region_code": "26-000",
                "sido_name": "부산광역시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        if self._step == 2:
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
        {"option_name": "대비", "candidate_id": None, "scenario_key": "default", "value_mid": 11.0},
        {"option_name": "더불어민주당은", "candidate_id": None, "scenario_key": "default", "value_mid": 31.0},
        {"option_name": "국민의힘은", "candidate_id": None, "scenario_key": "default", "value_mid": 29.0},
        {"option_name": "전라는", "candidate_id": None, "scenario_key": "default", "value_mid": 13.0},
        {"option_name": "국정안정론", "candidate_id": "cand:국정안정론", "scenario_key": "default", "value_mid": 53.0},
        {"option_name": "재정자립도", "candidate_id": "cand:재정자립도", "scenario_key": "default", "value_mid": 24.0},
        {"option_name": "최고치", "candidate_id": "cand:최고치", "scenario_key": "default", "value_mid": 19.0},
        {"option_name": "접촉률은", "candidate_id": "cand:접촉률은", "scenario_key": "default", "value_mid": 18.0},
        {"option_name": "엔비디아", "candidate_id": "cand:엔비디아", "scenario_key": "default", "value_mid": 17.0},
        {"option_name": "가격", "candidate_id": "cand:가격", "scenario_key": "default", "value_mid": 16.0},
        {"option_name": "조정했는데도", "candidate_id": "cand:조정했는데도", "scenario_key": "default", "value_mid": 15.0},
        {"option_name": "보다", "candidate_id": "cand:보다", "scenario_key": "default", "value_mid": 14.0},
        {"option_name": "주전보다", "candidate_id": "cand:주전보다", "scenario_key": "default", "value_mid": 13.0},
        {"option_name": "정원오", "candidate_id": None, "scenario_key": "default", "value_mid": 44.0},
        {"option_name": "오세훈", "candidate_id": "cand-oh", "scenario_key": "default", "value_mid": 42.0},
        {"option_name": "김민주", "candidate_id": None, "scenario_key": "default", "value_mid": 12.0},
    ]

    normalized = PostgresRepository._normalize_options(options)
    names = [row["option_name"] for row in normalized]

    assert names == ["정원오", "오세훈", "김민주"]


def test_normalize_options_filters_low_quality_manual_candidate_rows():
    options = [
        {
            "option_name": "대비",
            "candidate_id": "cand:대비",
            "party_name": None,
            "scenario_key": "default",
            "value_mid": 7.0,
            "candidate_verify_source": "manual",
            "candidate_verify_confidence": 1.0,
            "candidate_verify_matched_key": "대비",
        },
        {
            "option_name": "정원오",
            "candidate_id": "cand:정원오",
            "party_name": "더불어민주당",
            "scenario_key": "default",
            "value_mid": 44.0,
            "candidate_verify_source": "manual",
            "candidate_verify_confidence": 1.0,
            "candidate_verify_matched_key": "정원오",
        },
    ]

    normalized = PostgresRepository._normalize_options(options)
    names = [row["option_name"] for row in normalized]

    assert names == ["정원오"]


class _FallbackCursor:
    def __init__(self):
        self.execs: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def execute(self, query, params=None):  # noqa: ARG002
        self.execs.append(query)

    def fetchone(self):
        step = len(self.execs)
        if step == 1:
            return {
                "matchup_id": "m-fallback",
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "is_active": True,
            }
        if step == 2:
            return {
                "region_code": "11-000",
                "sido_name": "서울특별시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        return None

    def fetchall(self):
        step = len(self.execs)
        if step != 3:
            return []
        return [
            {
                "matchup_id": "m-fallback",
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "pollster": "최신리서치",
                "survey_start_date": date(2026, 2, 19),
                "survey_end_date": date(2026, 2, 20),
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
                "observation_updated_at": "2026-02-20T03:00:00+00:00",
                "official_release_at": None,
                "article_published_at": "2026-02-20T01:00:00+00:00",
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "poll_fingerprint": "f1",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
                "observation_id": 1001,
                "options": [
                    {
                        "option_name": "대비",
                        "candidate_id": "cand:대비",
                        "party_name": "미확정(검수대기)",
                        "scenario_key": "default",
                        "scenario_type": "head_to_head",
                        "scenario_title": "대비 단독",
                        "value_mid": 7.0,
                        "value_raw": "7%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": True,
                        "candidate_verify_source": "manual",
                        "candidate_verify_confidence": 1.0,
                        "candidate_verify_matched_key": "대비",
                    }
                ],
            },
            {
                "matchup_id": "m-fallback",
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "pollster": "직전리서치",
                "survey_start_date": date(2026, 2, 17),
                "survey_end_date": date(2026, 2, 18),
                "confidence_level": 95.0,
                "sample_size": 1000,
                "response_rate": 12.1,
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
                "observation_updated_at": "2026-02-18T03:00:00+00:00",
                "official_release_at": None,
                "article_published_at": "2026-02-18T01:00:00+00:00",
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "poll_fingerprint": "f2",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
                "observation_id": 1000,
                "options": [
                    {
                        "option_name": "정원오",
                        "candidate_id": "cand-jwo",
                        "party_name": "더불어민주당",
                        "scenario_key": "default",
                        "scenario_type": "head_to_head",
                        "scenario_title": "정원오 vs 오세훈",
                        "value_mid": 44.0,
                        "value_raw": "44%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    },
                    {
                        "option_name": "오세훈",
                        "candidate_id": "cand-oh",
                        "party_name": "국민의힘",
                        "scenario_key": "default",
                        "scenario_type": "head_to_head",
                        "scenario_title": "정원오 vs 오세훈",
                        "value_mid": 41.0,
                        "value_raw": "41%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    },
                ],
            },
        ]


class _FallbackConn:
    def __init__(self):
        self.cur = _FallbackCursor()

    def cursor(self):
        return self.cur


def test_get_matchup_falls_back_to_previous_observation_when_latest_is_invalid():
    repo = PostgresRepository(_FallbackConn())

    out = repo.get_matchup("m-fallback")

    assert out is not None
    assert out["has_data"] is True
    assert out["pollster"] == "직전리서치"
    assert out["survey_end_date"] == date(2026, 2, 18)
    assert [row["option_name"] for row in out["options"]] == ["정원오", "오세훈"]


class _BundleCursor:
    def __init__(self):
        self.execs: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def execute(self, query, params=None):  # noqa: ARG002
        self.execs.append(query)

    def fetchone(self):
        step = len(self.execs)
        if step == 1:
            return {
                "matchup_id": "m-bundle",
                "region_code": "26-000",
                "office_type": "광역자치단체장",
                "title": "부산시장 가상대결",
                "is_active": True,
            }
        if step == 2:
            return {
                "region_code": "26-000",
                "sido_name": "부산광역시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        return None

    def fetchall(self):
        step = len(self.execs)
        if step != 3:
            return []
        return [
            {
                "matchup_id": "m-bundle",
                "region_code": "26-000",
                "office_type": "광역자치단체장",
                "title": "[여론조사] 부산시장 가상대결 A",
                "pollster": "부산리서치",
                "survey_start_date": date(2026, 2, 19),
                "survey_end_date": date(2026, 2, 21),
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
                "observation_updated_at": "2026-02-21T03:00:00+00:00",
                "official_release_at": None,
                "article_published_at": "2026-02-21T01:00:00+00:00",
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "poll_fingerprint": "fp-busan-a",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
                "observation_id": 2002,
                "options": [
                    {
                        "option_name": "전재수",
                        "candidate_id": "cand-jjs",
                        "party_name": "더불어민주당",
                        "scenario_key": "h2h-a",
                        "scenario_type": "head_to_head",
                        "scenario_title": "전재수 vs 박형준",
                        "value_mid": 43.4,
                        "value_raw": "43.4%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
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
                ],
            },
            {
                "matchup_id": "m-bundle",
                "region_code": "26-000",
                "office_type": "광역자치단체장",
                "title": "[여론조사] 부산시장 가상대결 A",
                "pollster": "부산리서치",
                "survey_start_date": date(2026, 2, 19),
                "survey_end_date": date(2026, 2, 21),
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
                "observation_updated_at": "2026-02-21T02:00:00+00:00",
                "official_release_at": None,
                "article_published_at": "2026-02-21T01:00:00+00:00",
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "poll_fingerprint": "fp-busan-a",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
                "observation_id": 2001,
                "options": [
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
                        "scenario_title": "다자대결",
                        "value_mid": 26.8,
                        "value_raw": "26.8%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    },
                ],
            },
            {
                "matchup_id": "m-bundle",
                "region_code": "26-000",
                "office_type": "광역자치단체장",
                "title": "[여론조사] 부산시장 가상대결 B",
                "pollster": "다른리서치",
                "survey_start_date": date(2026, 2, 10),
                "survey_end_date": date(2026, 2, 12),
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
                "observation_updated_at": "2026-02-12T02:00:00+00:00",
                "official_release_at": None,
                "article_published_at": "2026-02-12T01:00:00+00:00",
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "poll_fingerprint": "fp-busan-b",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
                "observation_id": 1900,
                "options": [
                    {
                        "option_name": "홍길동",
                        "candidate_id": "cand-hgd",
                        "party_name": "무소속",
                        "scenario_key": "default",
                        "scenario_type": "head_to_head",
                        "scenario_title": "홍길동 단독",
                        "value_mid": 9.0,
                        "value_raw": "9.0%",
                        "party_inferred": False,
                        "party_inference_source": None,
                        "party_inference_confidence": None,
                        "needs_manual_review": False,
                    }
                ],
            },
        ]


class _BundleConn:
    def __init__(self):
        self.cur = _BundleCursor()

    def cursor(self):
        return self.cur


def test_get_matchup_merges_recent_observations_with_same_poll_fingerprint():
    repo = PostgresRepository(_BundleConn())

    out = repo.get_matchup("m-bundle")

    assert out is not None
    assert out["has_data"] is True
    assert out["pollster"] == "부산리서치"
    assert out["survey_end_date"] == date(2026, 2, 21)
    assert len(out["scenarios"]) == 3
    assert {row["scenario_key"] for row in out["scenarios"]} == {"h2h-a", "h2h-b", "multi-a"}
    option_names = [row["option_name"] for scenario in out["scenarios"] for row in scenario["options"]]
    assert "홍길동" not in option_names

    jeon_values = [
        option["value_mid"]
        for scenario in out["scenarios"]
        for option in scenario["options"]
        if option["candidate_id"] == "cand-jjs"
    ]
    assert sorted(jeon_values) == [26.8, 43.4, 43.8]


class _RichScenarioCursor(_BundleCursor):
    def fetchall(self):
        step = len(self.execs)
        if step != 3:
            return []
        rows = super().fetchall()
        latest_minimal = dict(rows[0])
        latest_minimal["pollster"] = "최신리서치"
        latest_minimal["survey_end_date"] = date(2026, 2, 22)
        latest_minimal["poll_fingerprint"] = "fp-latest-minimal"
        latest_minimal["options"] = [
            {
                "option_name": "전재수",
                "candidate_id": "cand-jjs",
                "party_name": "더불어민주당",
                "scenario_key": "default",
                "scenario_type": "head_to_head",
                "scenario_title": "전재수 vs 박형준",
                "value_mid": 44.1,
                "value_raw": "44.1%",
                "party_inferred": False,
                "party_inference_source": None,
                "party_inference_confidence": None,
                "needs_manual_review": False,
            },
            {
                "option_name": "박형준",
                "candidate_id": "cand-phj",
                "party_name": "국민의힘",
                "scenario_key": "default",
                "scenario_type": "head_to_head",
                "scenario_title": "전재수 vs 박형준",
                "value_mid": 33.0,
                "value_raw": "33.0%",
                "party_inferred": False,
                "party_inference_source": None,
                "party_inference_confidence": None,
                "needs_manual_review": False,
            },
        ]
        rich_older = dict(rows[1])
        rich_older["pollster"] = "풍부리서치"
        rich_older["survey_end_date"] = date(2026, 2, 21)
        rich_older["poll_fingerprint"] = "fp-rich-older"
        rich_older["options"] = list(rows[0]["options"]) + list(rows[1]["options"])
        return [latest_minimal, rich_older]


class _RichScenarioConn:
    def __init__(self):
        self.cur = _RichScenarioCursor()

    def cursor(self):
        return self.cur


def test_get_matchup_prefers_richer_scenario_observation_over_latest_minimal_default():
    repo = PostgresRepository(_RichScenarioConn())

    out = repo.get_matchup("m-bundle")

    assert out is not None
    assert out["has_data"] is True
    assert out["pollster"] == "풍부리서치"
    assert out["survey_end_date"] == date(2026, 2, 21)
    assert len(out["scenarios"]) == 3
    assert {row["scenario_key"] for row in out["scenarios"]} == {"h2h-b", "multi-a", "h2h-a"}


class _AllInvalidCursor(_FallbackCursor):
    def fetchall(self):
        step = len(self.execs)
        if step != 3:
            return []
        rows = super().fetchall()
        return rows[:1]


class _AllInvalidConn:
    def __init__(self):
        self.cur = _AllInvalidCursor()
        self.commit_count = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commit_count += 1


def test_get_matchup_sets_has_data_false_when_all_recent_observations_invalid():
    repo = PostgresRepository(_AllInvalidConn())

    out = repo.get_matchup("m-fallback")

    assert out is not None
    assert out["has_data"] is False
    assert out["options"] == []
    assert out["scenarios"] == []


class _NoiseOnlyCursor:
    def __init__(self):
        self.execs: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def execute(self, query, params=None):  # noqa: ARG002
        self.execs.append(query)

    def fetchone(self):
        step = len(self.execs)
        if step == 1:
            return {
                "matchup_id": "m-noise",
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "is_active": True,
            }
        if step == 2:
            return {
                "region_code": "11-000",
                "sido_name": "서울특별시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        if step == 4:
            return None
        return None

    def fetchall(self):
        step = len(self.execs)
        if step != 3:
            return []
        return [
            {
                "matchup_id": "m-noise",
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "observation_key": "obs-noise",
                "pollster": "테스트리서치",
                "survey_start_date": date(2026, 2, 19),
                "survey_end_date": date(2026, 2, 20),
                "confidence_level": 95.0,
                "sample_size": 1000,
                "response_rate": 12.3,
                "margin_of_error": 3.1,
                "source_grade": "B",
                "audience_scope": "regional",
                "audience_region_code": "11-000",
                "sampling_population_text": "서울 거주 만 18세 이상",
                "legal_completeness_score": 0.86,
                "legal_filled_count": 6,
                "legal_required_count": 7,
                "date_resolution": "exact",
                "date_inference_mode": "relative_published_at",
                "date_inference_confidence": 0.92,
                "observation_updated_at": "2026-02-20T03:00:00+00:00",
                "official_release_at": None,
                "article_published_at": "2026-02-20T01:00:00+00:00",
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "poll_fingerprint": "noise-fingerprint",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
                "observation_id": 9001,
                "options": [
                    {"option_name": "최고치", "candidate_id": "cand:최고치", "scenario_key": "default", "value_mid": 70.0},
                    {"option_name": "접촉률은", "candidate_id": "cand:접촉률은", "scenario_key": "default", "value_mid": 60.0},
                    {"option_name": "엔비디아", "candidate_id": "cand:엔비디아", "scenario_key": "default", "value_mid": 50.0},
                    {"option_name": "가격", "candidate_id": "cand:가격", "scenario_key": "default", "value_mid": 40.0},
                    {
                        "option_name": "조정했는데도",
                        "candidate_id": "cand:조정했는데도",
                        "scenario_key": "default",
                        "value_mid": 30.0,
                    },
                    {"option_name": "보다", "candidate_id": "cand:보다", "scenario_key": "default", "value_mid": 20.0},
                    {"option_name": "주전보다", "candidate_id": "cand:주전보다", "scenario_key": "default", "value_mid": 10.0},
                ],
            }
        ]


class _NoiseOnlyConn:
    def __init__(self):
        self.cur = _NoiseOnlyCursor()
        self.commit_count = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commit_count += 1


def test_get_matchup_routes_review_queue_when_noise_filter_removes_all_candidates():
    conn = _NoiseOnlyConn()
    repo = PostgresRepository(conn)

    out = repo.get_matchup("m-noise")

    assert out is not None
    assert out["has_data"] is False
    assert out["options"] == []
    assert out["scenarios"] == []
    assert out["candidate_noise_block_count"] == 7
    assert out["needs_manual_review"] is True
    assert conn.commit_count == 1
    assert any("INSERT INTO review_queue" in query for query in conn.cur.execs)
