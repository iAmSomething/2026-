from __future__ import annotations

import unittest

from src.pipeline.collector import PollCollector
from src.pipeline.contracts import Article, stable_id


class CollectorExtractTest(unittest.TestCase):
    def test_extract_candidate_pairs_from_text(self) -> None:
        collector = PollCollector()
        text = "서울시장 여론조사에서 정원오 44% vs 오세훈 31%였다."
        pairs = collector.extract_candidate_pairs(text, mode="v1")
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["name"], "정원오")
        self.assertEqual(pairs[0]["value_raw"], "44%")
        self.assertEqual(pairs[1]["name"], "오세훈")
        self.assertEqual(pairs[1]["value_raw"], "31%")

    def test_extract_candidate_pairs_v2_prefers_body_signal(self) -> None:
        collector = PollCollector()
        body = (
            "무단전재 및 재배포 금지. 서울시장 여론조사 본문에서 "
            "정원오 41% vs 오세훈 37% 결과가 나왔다."
        )
        pairs = collector.extract_candidate_pairs(body, title="서울시장 조사", mode="v2")
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["name"], "정원오")
        self.assertEqual(pairs[0]["value_raw"], "41%")
        self.assertEqual(pairs[1]["name"], "오세훈")
        self.assertEqual(pairs[1]["value_raw"], "37%")

    def test_fetch_success_path(self) -> None:
        collector = PollCollector()
        collector._robots_allowed = lambda _url: True  # type: ignore[method-assign]
        collector._http_get_text = lambda _url: (  # type: ignore[method-assign]
            "<html><head><title>기사 제목</title>"
            "<meta property='og:site_name' content='테스트언론' />"
            "<meta property='article:published_time' content='2026-02-18T00:00:00+09:00' />"
            "</head><body>여론조사 수치 40%</body></html>"
        )

        article, error = collector.fetch("https://example.com/news/1?utm_source=test")
        self.assertIsNone(error)
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article.url, "https://example.com/news/1")
        self.assertEqual(article.publisher, "테스트언론")
        self.assertEqual(article.title, "기사 제목")
        self.assertTrue(bool(article.collected_at))

    def test_classify_poll_report(self) -> None:
        collector = PollCollector()
        text = "여론조사 결과 오차범위 ±3.1%로 조사기관 KBS가 발표했다. 정원오 44% vs 오세훈 31%"
        label, confidence = collector.classify(text)
        self.assertEqual(label, "POLL_REPORT")
        self.assertGreater(confidence, 0.8)

    def test_extract_minimum_contract_fields(self) -> None:
        collector = PollCollector()
        article_text = (
            "서울시장 여론조사에서 KBS가 발표했다. 표본 1000명, 응답률 12.3%, "
            "표본오차 ±3.1%. 정원오 44% vs 오세훈 31%"
        )
        article = Article(
            id=stable_id("art", "https://example.com/1"),
            url="https://example.com/1",
            title="서울시장 가상대결",
            publisher="테스트",
            published_at="2026-02-18T00:00:00+09:00",
            snippet=article_text[:100],
            collected_at="2026-02-18T00:00:00+00:00",
            raw_hash="abc",
            raw_text=article_text,
        )

        observations, options, errors = collector.extract(article)
        self.assertEqual(len(errors), 0)
        self.assertGreaterEqual(len(observations), 1)
        self.assertGreaterEqual(len(options), 2)

        obs = observations[0].to_dict()
        self.assertIn("region_code", obs)
        self.assertIn("office_type", obs)
        self.assertIn("matchup_id", obs)
        self.assertEqual(obs["region_code"], "11-000")
        self.assertEqual(obs["office_type"], "광역자치단체장")
        self.assertIsNotNone(obs["margin_of_error"])

        opt = options[0].to_dict()
        self.assertIn("candidate_id", opt)
        self.assertIn("value_raw", opt)
        self.assertIn("value_min", opt)
        self.assertIn("value_max", opt)
        self.assertIn("value_mid", opt)
        self.assertIn("is_missing", opt)
        self.assertEqual(opt["margin_of_error"], obs["margin_of_error"])

    def test_pre_extract_gate_rejects_policy_only_poll(self) -> None:
        collector = PollCollector()
        article = Article(
            id=stable_id("art", "https://example.com/policy"),
            url="https://example.com/policy",
            title="국정지지율 조사 결과 발표",
            publisher="테스트",
            published_at=None,
            snippet="국정지지율",
            collected_at="2026-02-18T00:00:00+00:00",
            raw_hash="h1",
            raw_text="국정지지율 55%, 정당지지도 40% 조사 결과",
        )
        passed, reason = collector.pre_extract_gate(article)
        self.assertFalse(passed)
        self.assertEqual(reason, "GATE_POLICY_QUALITATIVE_ONLY")

    def test_pre_extract_gate_rejects_when_candidate_numeric_missing(self) -> None:
        collector = PollCollector()
        article = Article(
            id=stable_id("art", "https://example.com/no-numeric"),
            url="https://example.com/no-numeric",
            title="서울시장 여론조사 접전",
            publisher="테스트",
            published_at=None,
            snippet="서울시장 여론조사",
            collected_at="2026-02-18T00:00:00+00:00",
            raw_hash="h2",
            raw_text="서울시장 여론조사에서 후보 간 접전 양상이라는 분석이 나왔다.",
        )
        passed, reason = collector.pre_extract_gate(article)
        self.assertFalse(passed)
        self.assertEqual(reason, "GATE_NO_CANDIDATE_NUMERIC_SIGNAL")

    def test_pre_extract_gate_rejects_unmapped_region(self) -> None:
        collector = PollCollector()
        article = Article(
            id=stable_id("art", "https://example.com/unmapped"),
            url="https://example.com/unmapped",
            title="알수없는지역시장 여론조사",
            publisher="테스트",
            published_at=None,
            snippet="알수없는지역시장",
            collected_at="2026-02-18T00:00:00+00:00",
            raw_hash="h3",
            raw_text="알수없는지역시장 후보 A 40% vs 후보B 32%",
        )
        passed, reason = collector.pre_extract_gate(article)
        self.assertFalse(passed)
        self.assertEqual(reason, "GATE_REGION_OFFICE_UNMAPPED")

    def test_extract_error_code_is_granular(self) -> None:
        collector = PollCollector()
        article = Article(
            id=stable_id("art", "https://example.com/policy-only"),
            url="https://example.com/policy-only",
            title="서울시장 여론조사 정책 찬반",
            publisher="테스트",
            published_at=None,
            snippet="정책 찬반",
            collected_at="2026-02-18T00:00:00+00:00",
            raw_hash="h4",
            raw_text="서울시장 여론조사 정책 찬성 55%, 반대 35% 결과가 나왔다.",
        )
        observations, options, errors = collector.extract(article)
        self.assertEqual(len(observations), 1)
        self.assertEqual(len(options), 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].issue_type, "extract_error")
        self.assertEqual(errors[0].error_code, "POLICY_ONLY_SIGNAL")

    def test_relative_date_strict_fail_routes_to_review_queue(self) -> None:
        collector = PollCollector(relative_date_policy="strict_fail")
        article = Article(
            id=stable_id("art", "https://example.com/relative-strict"),
            url="https://example.com/relative-strict",
            title="서울시장 조사",
            publisher="테스트",
            published_at=None,
            snippet="어제 조사",
            collected_at="2026-02-19T00:00:00+00:00",
            raw_hash="h5",
            raw_text="어제 발표된 서울시장 여론조사에서 정원오 44% vs 오세훈 31%",
        )
        observations, options, errors = collector.extract(article)
        self.assertEqual(len(observations), 1)
        self.assertEqual(len(options), 2)
        self.assertEqual(observations[0].survey_end_date, None)
        self.assertEqual(observations[0].date_inference_mode, "strict_fail_blocked")
        self.assertTrue(any(err.error_code == "RELATIVE_DATE_STRICT_FAIL" for err in errors))

    def test_relative_date_allow_estimated_policy_uses_collected_at(self) -> None:
        collector = PollCollector(relative_date_policy="allow_estimated_timestamp")
        article = Article(
            id=stable_id("art", "https://example.com/relative-estimated"),
            url="https://example.com/relative-estimated",
            title="서울시장 조사",
            publisher="테스트",
            published_at=None,
            snippet="어제 조사",
            collected_at="2026-02-19T00:00:00+00:00",
            raw_hash="h6",
            raw_text="어제 발표된 서울시장 여론조사에서 정원오 44% vs 오세훈 31%",
        )
        observations, _, errors = collector.extract(article)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].survey_end_date, "2026-02-18")
        self.assertEqual(observations[0].date_inference_mode, "estimated_timestamp")
        self.assertTrue(any(err.error_code == "RELATIVE_DATE_ESTIMATED" for err in errors))

    def test_relative_date_low_confidence_routes_uncertain_review(self) -> None:
        collector = PollCollector(relative_date_policy="strict_fail")
        article = Article(
            id=stable_id("art", "https://example.com/relative-uncertain"),
            url="https://example.com/relative-uncertain",
            title="서울시장 조사",
            publisher="테스트",
            published_at="2026-02-18T00:00:00+09:00",
            snippet="지난주 조사",
            collected_at="2026-02-19T00:00:00+00:00",
            raw_hash="h7",
            raw_text="지난주 서울시장 여론조사에서 정원오 44% vs 오세훈 31%",
        )
        observations, _, errors = collector.extract(article)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].survey_end_date, "2026-02-10")
        self.assertEqual(observations[0].date_inference_mode, "relative_published_at")
        self.assertLess(float(observations[0].date_inference_confidence or 0), 0.8)
        self.assertTrue(any(err.error_code == "RELATIVE_DATE_UNCERTAIN" for err in errors))


if __name__ == "__main__":
    unittest.main()
