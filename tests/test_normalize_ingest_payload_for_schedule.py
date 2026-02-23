from __future__ import annotations

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
