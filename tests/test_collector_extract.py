from __future__ import annotations

import unittest

from src.pipeline.collector import PollCollector
from src.pipeline.contracts import Article, stable_id


class CollectorExtractTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
