from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import re
from typing import Any
import urllib.parse
import urllib.request
from urllib.parse import urlparse, urlunparse
import xml.etree.ElementTree as ET

from app.services.cutoff_policy import (
    ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
    is_article_published_at_allowed,
    parse_datetime_like,
    published_at_cutoff_reason,
)

from .collector import PollCollector
from .contracts import Article, ReviewQueueItem, new_review_queue_item, stable_id


_POLL_KEYWORDS = ("여론조사", "지지율", "가상대결", "오차범위", "표본오차", "후보")
_OFFICE_KEYWORDS = ("시장", "지사", "교육감", "구청장", "군수", "의원")
_PERCENT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?%")


@dataclass
class DiscoveryCandidateV11:
    url: str
    title: str
    published_at_raw: str | None
    query: str | None
    source_type: str
    summary: str | None = None
    publisher_hint: str | None = None
    resolved_url: str | None = None
    classification_label: str | None = None
    classification_confidence: float | None = None
    article: Article | None = None
    used_fallback: bool = False

    def classify_input(self) -> dict[str, Any]:
        if self.article is None:
            return {
                "url": self.resolved_url or self.url,
                "title": self.title,
                "published_at": None,
                "publisher": self.publisher_hint,
                "snippet": self.summary,
                "raw_hash": None,
                "raw_text": None,
            }
        return {
            "url": self.article.url,
            "title": self.article.title,
            "published_at": self.article.published_at,
            "publisher": self.article.publisher,
            "snippet": self.article.snippet,
            "raw_hash": self.article.raw_hash,
            "raw_text": self.article.raw_text,
        }


@dataclass
class DiscoveryResultV11:
    queries: list[str] = field(default_factory=list)
    raw_candidates: list[DiscoveryCandidateV11] = field(default_factory=list)
    deduped_candidates: list[DiscoveryCandidateV11] = field(default_factory=list)
    fetched_candidates: list[DiscoveryCandidateV11] = field(default_factory=list)
    valid_candidates: list[DiscoveryCandidateV11] = field(default_factory=list)
    cutoff_excluded_candidates: list[DiscoveryCandidateV11] = field(default_factory=list)
    review_queue: list[ReviewQueueItem] = field(default_factory=list)

    def metrics(self) -> dict[str, Any]:
        raw = len(self.raw_candidates)
        dedup = len(self.deduped_candidates)
        fetched = len(self.fetched_candidates)
        valid = len(self.valid_candidates)
        cutoff_excluded = len(self.cutoff_excluded_candidates)
        fetch_fail = max(dedup - fetched, 0)
        fallback_count = sum(1 for c in self.fetched_candidates if c.used_fallback)
        return {
            "query_count": len(self.queries),
            "raw_count": raw,
            "dedup_count": dedup,
            "fetched_count": fetched,
            "valid_count": valid,
            "fallback_fetch_count": fallback_count,
            "duplicate_count": max(raw - dedup, 0),
            "duplicate_rate": round((raw - dedup) / raw, 4) if raw else 0.0,
            "fetch_fail_count": fetch_fail,
            "fetch_fail_rate": round(fetch_fail / dedup, 4) if dedup else 0.0,
            "valid_article_rate": round(valid / dedup, 4) if dedup else 0.0,
            "cutoff_excluded_count": cutoff_excluded,
        }


class DiscoveryPipelineV11:
    PUBLISHER_RSS_FEEDS: tuple[str, ...] = (
        "https://www.yna.co.kr/rss/politics.xml",
        "https://www.khan.co.kr/rss/rssdata/politic_news.xml",
        "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://www.newsis.com/RSS/politics.xml",
        "https://www.hankyung.com/feed/politics",
        "https://www.mk.co.kr/rss/30000001/",
        "https://www.segye.com/Articles/RSSList/segye_recent.xml",
        "https://www.mbn.co.kr/rss/",
    )

    ROBOTS_BLOCKLIST_DOMAINS: tuple[str, ...] = ("news.google.com",)

    def __init__(self, collector: PollCollector | None = None):
        self.collector = collector or PollCollector()

    def build_queries(self) -> list[str]:
        election_terms = ("지방선거", "재보궐", "교육감 선거")
        region_terms = ("서울시장", "부산시장", "경기지사", "인천시장", "고양시장", "시흥시장", "제주도지사")
        poll_terms = ("여론조사", "지지율", "가상대결", "오차범위")
        queries: list[str] = []
        for e in election_terms:
            for r in region_terms:
                for p in poll_terms:
                    queries.append(f"{e} {r} {p}")
        return queries

    def run(self, target_count: int = 100, per_query_limit: int = 10, per_feed_limit: int = 40) -> DiscoveryResultV11:
        result = DiscoveryResultV11()
        result.queries = self.build_queries()

        # 1) publisher direct RSS 우선 수집
        for feed in self.PUBLISHER_RSS_FEEDS:
            discovered, errors = self._discover_from_publisher_feed(feed_url=feed, limit=per_feed_limit)
            result.raw_candidates.extend(discovered)
            result.review_queue.extend(errors)
            if len(result.raw_candidates) >= target_count * 2:
                break

        # 2) query 기반 google RSS 보조 수집
        if len(result.raw_candidates) < target_count * 2:
            for query in result.queries:
                discovered, errors = self._discover_from_google_rss(query=query, limit=per_query_limit)
                result.raw_candidates.extend(discovered)
                result.review_queue.extend(errors)
                if len(result.raw_candidates) >= target_count * 3:
                    break

        # 3) dedup + poll score 기반 우선순위
        deduped = self._dedup(result.raw_candidates)
        deduped.sort(key=lambda c: self._poll_score(" ".join(filter(None, [c.title, c.summary or "", c.query or ""]))), reverse=True)
        result.deduped_candidates = deduped[:target_count]

        # 4) fetch + fallback + classify
        for candidate in result.deduped_candidates:
            article, error, used_fallback = self._fetch_candidate(candidate, retries=3)
            candidate.used_fallback = used_fallback
            if error is not None:
                result.review_queue.append(error)
            if article is None:
                continue

            if not is_article_published_at_allowed(article.published_at):
                cutoff_reason = published_at_cutoff_reason(article.published_at)
                parsed_published_at = parse_datetime_like(article.published_at)
                result.cutoff_excluded_candidates.append(candidate)
                result.review_queue.append(
                    new_review_queue_item(
                        entity_type="article",
                        entity_id=article.id,
                        issue_type="mapping_error",
                        stage="discover",
                        error_code=cutoff_reason,
                        error_message=(
                            "article excluded by fixed cutoff policy: "
                            f"published_at must be >= {ARTICLE_PUBLISHED_AT_CUTOFF_ISO}"
                        ),
                        source_url=article.url,
                        payload={
                            "published_at": article.published_at,
                            "published_at_kst": (
                                parsed_published_at.isoformat(timespec="seconds")
                                if parsed_published_at is not None
                                else None
                            ),
                            "published_at_cutoff_kst": ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
                            "source_type": candidate.source_type,
                            "query": candidate.query,
                        },
                    )
                )
                continue

            candidate.article = article
            result.fetched_candidates.append(candidate)

            label, confidence = self.collector.classify(article.raw_text or candidate.title)
            candidate.classification_label = label
            candidate.classification_confidence = confidence
            if label in {"POLL_REPORT", "POLL_MENTION"}:
                result.valid_candidates.append(candidate)

        return result

    def _discover_from_publisher_feed(self, feed_url: str, limit: int) -> tuple[list[DiscoveryCandidateV11], list[ReviewQueueItem]]:
        out: list[DiscoveryCandidateV11] = []
        errors: list[ReviewQueueItem] = []
        try:
            xml_text = self._http_get_text(feed_url, timeout=20)
            root = ET.fromstring(xml_text)

            for item in root.findall(".//item"):
                title = self._cleanup_text(item.findtext("title"))
                link = self._cleanup_text(item.findtext("link"))
                pub_date = self._cleanup_text(item.findtext("pubDate"))
                summary = self._cleanup_text(item.findtext("description"))
                if not title or not link:
                    continue
                candidate = DiscoveryCandidateV11(
                    url=self._canonicalize_url_v11(link),
                    resolved_url=self._canonicalize_url_v11(link),
                    title=title,
                    published_at_raw=pub_date,
                    query=None,
                    source_type="publisher_rss",
                    summary=summary,
                    publisher_hint=urlparse(link).netloc,
                )
                if self._poll_score(" ".join(filter(None, [candidate.title, candidate.summary or ""]))) <= 0:
                    continue
                out.append(candidate)
                if len(out) >= limit:
                    break

            # atom feed fallback
            if not out:
                atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", atom_ns):
                    title = self._cleanup_text(entry.findtext("atom:title", default="", namespaces=atom_ns))
                    link_node = entry.find("atom:link", atom_ns)
                    link = link_node.attrib.get("href", "") if link_node is not None else ""
                    summary = self._cleanup_text(entry.findtext("atom:summary", default="", namespaces=atom_ns))
                    if not title or not link:
                        continue
                    candidate = DiscoveryCandidateV11(
                        url=self._canonicalize_url_v11(link),
                        resolved_url=self._canonicalize_url_v11(link),
                        title=title,
                        published_at_raw=None,
                        query=None,
                        source_type="publisher_rss",
                        summary=summary,
                        publisher_hint=urlparse(link).netloc,
                    )
                    if self._poll_score(" ".join(filter(None, [candidate.title, candidate.summary or ""]))) <= 0:
                        continue
                    out.append(candidate)
                    if len(out) >= limit:
                        break

        except Exception as exc:  # noqa: BLE001
            errors.append(
                new_review_queue_item(
                    entity_type="source",
                    entity_id=feed_url,
                    issue_type="discover_error",
                    stage="discover",
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    source_url=feed_url,
                    payload={"source_type": "publisher_rss"},
                )
            )
        return out, errors

    def _discover_from_google_rss(self, query: str, limit: int) -> tuple[list[DiscoveryCandidateV11], list[ReviewQueueItem]]:
        rss_url = (
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote(query)
            + "&hl=ko&gl=KR&ceid=KR:ko"
        )
        out: list[DiscoveryCandidateV11] = []
        errors: list[ReviewQueueItem] = []
        try:
            xml_text = self._http_get_text(rss_url, timeout=20)
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item"):
                title = self._cleanup_text(item.findtext("title"))
                link = self._cleanup_text(item.findtext("link"))
                pub_date = self._cleanup_text(item.findtext("pubDate"))
                summary = self._cleanup_text(item.findtext("description"))
                if not title or not link:
                    continue
                if self._poll_score(" ".join(filter(None, [title, summary or "", query]))) <= 0:
                    continue
                out.append(
                    DiscoveryCandidateV11(
                        url=self._canonicalize_url_v11(link),
                        resolved_url=self._canonicalize_url_v11(link),
                        title=title,
                        published_at_raw=pub_date,
                        query=query,
                        source_type="google_rss",
                        summary=summary,
                    )
                )
                if len(out) >= limit:
                    break
        except Exception as exc:  # noqa: BLE001
            errors.append(
                new_review_queue_item(
                    entity_type="source",
                    entity_id=rss_url,
                    issue_type="discover_error",
                    stage="discover",
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    source_url=rss_url,
                    payload={"query": query, "source_type": "google_rss"},
                )
            )
        return out, errors

    def _dedup(self, candidates: list[DiscoveryCandidateV11]) -> list[DiscoveryCandidateV11]:
        out: list[DiscoveryCandidateV11] = []
        seen_url: set[str] = set()
        seen_title_date: set[str] = set()

        for c in candidates:
            canonical_url = self._canonicalize_url_v11(c.resolved_url or c.url)
            date_key = self._date_key(c.published_at_raw)
            title_date_key = f"{self._normalize_title(c.title)}|{date_key or 'na'}"
            if canonical_url in seen_url:
                continue
            if title_date_key in seen_title_date:
                continue
            seen_url.add(canonical_url)
            seen_title_date.add(title_date_key)
            out.append(c)
        return out

    def _fetch_candidate(
        self,
        candidate: DiscoveryCandidateV11,
        retries: int = 3,
    ) -> tuple[Article | None, ReviewQueueItem | None, bool]:
        fetch_url = self._canonicalize_url_v11(candidate.resolved_url or candidate.url)
        domain = (urlparse(fetch_url).netloc or "").lower()

        if domain in self.ROBOTS_BLOCKLIST_DOMAINS:
            fallback = self._fallback_article(candidate)
            error = new_review_queue_item(
                entity_type="article",
                entity_id=fetch_url,
                issue_type="fetch_error",
                stage="fetch",
                error_code="ROBOTS_BLOCKLIST_BYPASS",
                error_message="blocked domain routed to fallback source",
                source_url=fetch_url,
                payload={"source_type": candidate.source_type},
            )
            return fallback, error, True

        article, error = self._fetch_with_retry(fetch_url, retries=retries)
        if error is None and article is not None:
            return article, None, False

        fallback = self._fallback_article(candidate)
        if fallback is not None:
            return fallback, error, True
        return None, error, False

    def _fetch_with_retry(self, url: str, retries: int = 3) -> tuple[Article | None, ReviewQueueItem | None]:
        last_error: ReviewQueueItem | None = None
        for _ in range(retries):
            article, error = self.collector.fetch(url)
            if error is None:
                return article, None
            last_error = error
        return None, last_error

    def _fallback_article(self, candidate: DiscoveryCandidateV11) -> Article | None:
        raw_text = " ".join(filter(None, [candidate.title, candidate.summary or "", candidate.query or ""])).strip()
        if not raw_text:
            return None

        title = candidate.title
        publisher = candidate.publisher_hint or "unknown"
        if " - " in title:
            title, publisher = title.rsplit(" - ", 1)

        return Article(
            id=stable_id("art-fallback", candidate.url),
            url=self._canonicalize_url_v11(candidate.resolved_url or candidate.url),
            title=title.strip(),
            publisher=publisher.strip(),
            published_at=None,
            snippet=raw_text[:220],
            collected_at="",
            raw_hash=stable_id("raw", raw_text),
            raw_text=raw_text,
        )

    def _http_get_text(self, url: str, timeout: int = 20) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": self.collector.user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _canonicalize_url_v11(self, url: str) -> str:
        canonical = self.collector._canonicalize_url(url)
        parsed = urlparse(canonical)

        if parsed.netloc.lower() == "news.google.com":
            # google rss 경유 링크는 tracking query 제거 + 안정적인 path key만 유지
            return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", "", ""))

        return canonical

    @staticmethod
    def _cleanup_text(value: str | None) -> str | None:
        if value is None:
            return None
        no_html = re.sub(r"<[^>]+>", " ", value)
        no_html = urllib.parse.unquote(no_html)
        return " ".join(no_html.split()) or None

    @staticmethod
    def _normalize_title(title: str) -> str:
        return " ".join(title.lower().split())

    @staticmethod
    def _date_key(pub_date: str | None) -> str | None:
        if not pub_date:
            return None
        try:
            return parsedate_to_datetime(pub_date).date().isoformat()
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _poll_score(text: str) -> int:
        score = 0
        lowered = text.lower()
        for keyword in _POLL_KEYWORDS:
            if keyword in text:
                score += 2
        for hint in _OFFICE_KEYWORDS:
            if hint in text:
                score += 1
        if _PERCENT_RE.search(text):
            score += 2
        if "조사" in lowered:
            score += 1
        return score


def discovery_v11_report_payload(
    *,
    result: DiscoveryResultV11,
    baseline_report_path: str | None = None,
    output_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "metrics_v11": result.metrics(),
        "classify_input_schema": {
            "type": "object",
            "required": ["url", "title", "published_at", "publisher", "snippet", "raw_hash", "raw_text"],
            "properties": {
                "url": {"type": ["string", "null"]},
                "title": {"type": ["string", "null"]},
                "published_at": {"type": ["string", "null"]},
                "publisher": {"type": ["string", "null"]},
                "snippet": {"type": ["string", "null"]},
                "raw_hash": {"type": ["string", "null"]},
                "raw_text": {"type": ["string", "null"]},
            },
        },
        "valid_candidates_preview": [c.classify_input() for c in result.valid_candidates[:20]],
        "review_queue": [x.to_dict() for x in result.review_queue[:200]],
    }

    if baseline_report_path:
        p = Path(baseline_report_path)
        if p.exists():
            base = json.loads(p.read_text(encoding="utf-8"))
            base_metrics = base.get("metrics", {})
            m11 = result.metrics()
            payload["metrics_v1"] = base_metrics
            payload["metrics_comparison"] = {
                "fetch_fail_rate_delta": round(
                    float(m11.get("fetch_fail_rate", 0.0)) - float(base_metrics.get("fetch_fail_rate", 0.0)),
                    4,
                ),
                "valid_article_rate_delta": round(
                    float(m11.get("valid_article_rate", 0.0)) - float(base_metrics.get("valid_article_rate", 0.0)),
                    4,
                ),
            }

    if output_paths:
        payload["output_paths"] = output_paths

    return payload


def save_discovery_v11_outputs(
    *,
    result: DiscoveryResultV11,
    output_dir: str,
    baseline_report_path: str | None = None,
) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    candidates_path = out / "discovery_candidates_v11.json"
    report_path = out / "discovery_report_v11.json"

    candidates_payload = [c.classify_input() for c in result.valid_candidates]
    candidates_path.write_text(json.dumps(candidates_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_payload = discovery_v11_report_payload(
        result=result,
        baseline_report_path=baseline_report_path,
        output_paths={"candidates": str(candidates_path), "report": str(report_path)},
    )
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "candidates": str(candidates_path),
        "report": str(report_path),
    }
