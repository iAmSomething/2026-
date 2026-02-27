from __future__ import annotations

from app.models.schemas import IngestPayload
from scripts.qa.normalize_ingest_payload_for_schedule import normalize_payload


def test_normalize_payload_candidate_party_fields() -> None:
    payload = {
        "records": [
            {
                "candidates": [
                    {
                        "candidate_id": "c1",
                        "name_ko": "홍길동",
                        "party_name": None,
                        "party_inferred": "더불어민주당",
                        "party_inference_source": "data_go_candidate_api_region",
                    },
                    {
                        "candidate_id": "c2",
                        "name_ko": "김철수",
                        "party_name": "국민의힘",
                        "party_inferred": None,
                        "party_inference_source": None,
                    },
                    {
                        "candidate_id": "c3",
                        "name_ko": "이영희",
                        "party_name": None,
                        "party_inferred": "false",
                        "party_inference_source": "unknown_source",
                    },
                ]
            }
        ]
    }

    out = normalize_payload(payload)
    candidates = out["records"][0]["candidates"]

    assert candidates[0]["party_inferred"] is True
    assert candidates[0]["party_name"] == "더불어민주당"
    assert candidates[0]["party_inference_source"] == "manual"

    assert candidates[1]["party_inferred"] is True
    assert candidates[1]["party_inference_source"] == "manual"

    assert candidates[2]["party_inferred"] is False
    assert candidates[2]["party_inference_source"] is None


def test_normalize_payload_422_repro_candidate_contract() -> None:
    payload = {
        "run_type": "manual",
        "extractor_version": "manual-v1",
        "records": [
            {
                "article": {"url": "https://example.com/1", "title": "sample", "publisher": "pub"},
                "observation": {
                    "observation_key": "obs-422",
                    "survey_name": "survey",
                    "pollster": "MBC",
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                    "matchup_id": "20260603|광역자치단체장|11-000",
                },
                "candidates": [
                    {
                        "candidate_id": "cand-1",
                        "name_ko": "홍길동",
                        "party_name": None,
                        "party_inferred": "더불어민주당",
                        "party_inference_source": "data_go_candidate_api_region",
                    }
                ],
                "options": [
                    {
                        "option_type": "candidate",
                        "option_name": "홍길동",
                        "value_raw": "51%",
                    }
                ],
            }
        ],
    }

    out = normalize_payload(payload)
    candidates = out["records"][0]["candidates"]
    assert candidates[0]["party_inferred"] is True
    assert candidates[0]["party_name"] == "더불어민주당"
    assert candidates[0]["party_inference_source"] == "manual"

    validated = IngestPayload.model_validate(out)
    assert validated.records[0].candidates[0].party_inferred is True


def test_normalize_payload_scope_and_margin_and_option_party_fields() -> None:
    payload = {
        "run_type": "collector_live_coverage_v2",
        "extractor_version": "collector-v2",
        "records": [
            {
                "article": {"url": "https://example.com/2", "title": "sample", "publisher": "pub"},
                "observation": {
                    "observation_key": "obs-scope",
                    "survey_name": "survey",
                    "pollster": "MBC",
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                    "matchup_id": "20260603|광역자치단체장|11-000",
                    "audience_scope": "nationwide",
                    "audience_region_code": "11-000",
                    "margin_of_error": "±3.1%p",
                },
                "options": [
                    {
                        "option_type": "party_support",
                        "option_name": "국민의힘",
                        "value_raw": "44%",
                        "party_inferred": "국민의힘",
                        "party_inference_source": "external-model",
                    }
                ],
            }
        ],
    }

    out = normalize_payload(payload)
    observation = out["records"][0]["observation"]
    option = out["records"][0]["options"][0]

    assert observation["audience_scope"] == "national"
    assert observation["audience_region_code"] is None
    assert observation["margin_of_error"] == 3.1
    assert option["party_inferred"] is True
    assert option["party_inference_source"] == "manual"

    validated = IngestPayload.model_validate(out)
    assert validated.records[0].observation.audience_scope == "national"
    assert validated.records[0].observation.margin_of_error == 3.1


def test_normalize_payload_splits_presidential_option_type() -> None:
    payload = {
        "records": [
            {
                "options": [
                    {
                        "option_type": "presidential_approval",
                        "option_name": "국정안정론",
                        "value_raw": "47%",
                    }
                ]
            }
        ]
    }

    out = normalize_payload(payload)
    option = out["records"][0]["options"][0]
    assert option["option_type"] == "election_frame"
    assert option.get("needs_manual_review", False) is False


def test_normalize_payload_marks_ambiguous_presidential_option_type_for_manual_review() -> None:
    payload = {
        "records": [
            {
                "options": [
                    {
                        "option_type": "presidential_approval",
                        "option_name": "국정안정 긍정평가",
                        "value_raw": "47%",
                    }
                ]
            }
        ]
    }

    out = normalize_payload(payload)
    option = out["records"][0]["options"][0]
    assert option["option_type"] == "presidential_approval"
    assert option["needs_manual_review"] is True


def test_normalize_payload_candidate_verify_fields() -> None:
    payload = {
        "records": [
            {
                "options": [
                    {
                        "option_type": "candidate_matchup",
                        "option_name": "홍길동",
                        "value_raw": "47%",
                        "candidate_verified": "true",
                        "candidate_verify_source": "external-service",
                        "candidate_verify_confidence": "0.83",
                        "candidate_verify_matched_key": "  data_go:cand-1  ",
                    }
                ]
            }
        ]
    }

    out = normalize_payload(payload)
    option = out["records"][0]["options"][0]
    assert option["candidate_verified"] is True
    assert option["candidate_verify_source"] == "article_context"
    assert option["candidate_verify_confidence"] == 0.83
    assert option["candidate_verify_matched_key"] == "data_go:cand-1"


def test_normalize_payload_party_inference_v3_source_and_evidence() -> None:
    payload = {
        "records": [
            {
                "options": [
                    {
                        "option_type": "candidate_matchup",
                        "option_name": "홍길동",
                        "value_raw": "47%",
                        "party_inferred": True,
                        "party_inference_source": "official_registry_v3",
                        "party_inference_evidence": {
                            "method": "party_inference_v3",
                            "rule": "candidate_context_counter",
                        },
                    }
                ]
            }
        ]
    }

    out = normalize_payload(payload)
    option = out["records"][0]["options"][0]
    assert option["party_inference_source"] == "official_registry_v3"
    assert option["party_inference_evidence"] == '{"method":"party_inference_v3","rule":"candidate_context_counter"}'
