from app.services.candidate_token_policy import is_noise_candidate_token


def test_runtime_noise_tokens_are_blocked_for_matchup_hotfix() -> None:
    blocked = [
        "최고치",
        "접촉률은",
        "엔비디아",
        "가격",
        "조정했는데도",
        "보다",
        "주전보다",
        "지지율이",
        "하위",
        "주째",
        "상승한",
        "평가는",
        "라인업에도",
        "반영하면",
        "구청장이",
        "시장이",
        "의원이",
    ]
    for token in blocked:
        assert is_noise_candidate_token(token) is True


def test_human_candidate_names_remain_allowed() -> None:
    allowed = ["정원오", "오세훈", "김민주", "박형준", "전재수"]
    for token in allowed:
        assert is_noise_candidate_token(token) is False
