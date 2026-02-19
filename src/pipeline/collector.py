from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import re
import time
from typing import Iterable
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

from .contracts import (
    Article,
    PollObservation,
    PollOption,
    ReviewQueueItem,
    build_candidate_id,
    build_matchup_id,
    new_review_queue_item,
    normalize_value,
    stable_id,
    utc_now_iso,
)
from .standards import COMMON_CODE_REGIONS, REGION_ALIASES, REGION_OFFICE_DIRECT_PATTERNS


@dataclass
class CollectorOutput:
    articles: list[Article] = field(default_factory=list)
    poll_observations: list[PollObservation] = field(default_factory=list)
    poll_options: list[PollOption] = field(default_factory=list)
    review_queue: list[ReviewQueueItem] = field(default_factory=list)
    stats: dict[str, int | float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "articles": [row.to_dict() for row in self.articles],
            "poll_observations": [row.to_dict() for row in self.poll_observations],
            "poll_options": [row.to_dict() for row in self.poll_options],
            "review_queue": [row.to_dict() for row in self.review_queue],
            "stats": self.stats,
        }


class PollCollector:
    _INCLUDE_KEYWORDS = ("여론조사", "표본", "오차범위", "응답률", "조사기관", "지지율", "가상대결")
    _EXCLUDE_KEYWORDS = ("사설", "칼럼", "오피니언")
    _PERCENT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?%")
    _MARGIN_RE = re.compile(r"(?:오차범위|표본오차)\s*[:：]?\s*±\s*(\d{1,2}(?:\.\d+)?)\s*%?")
    _SAMPLE_RE = re.compile(r"표본\s*[:：]?\s*([0-9,]{2,8})\s*명")
    _RESPONSE_RATE_RE = re.compile(r"응답률\s*[:：]?\s*(\d{1,2}(?:\.\d+)?)\s*%")
    _MATCHUP_RE = re.compile(
        r"([가-힣A-Za-z]{2,20})\s*(\d{1,3}(?:\.\d+)?)%\s*(?:vs|VS|대)\s*([가-힣A-Za-z]{2,20})\s*(\d{1,3}(?:\.\d+)?)%"
    )
    _NAME_VALUE_RE = re.compile(r"([가-힣A-Za-z]{2,20})\s*(\d{1,3}(?:\.\d+)?(?:\s*[~\-]\s*\d{1,3}(?:\.\d+)?)?%대?)")
    _POLLSTER_RE = re.compile(r"\b(KBS|MBC|SBS|한국갤럽|리얼미터|NBS|조원씨앤아이|미디어리서치)\b")
    _GATE_POLICY_KEYWORDS = (
        "국정지지율",
        "국정 안정",
        "국정안정론",
        "정당지지도",
        "대통령 국정",
        "국정평가",
    )
    _GATE_PREFERENCE_KEYWORDS = ("찬성", "반대", "호감도", "비호감", "정책", "개헌")
    _GATE_ELECTION_OFFICE_HINTS = ("시장", "지사", "교육감", "구청장", "군수", "의회", "단체장", "재보궐")
    _NON_CANDIDATE_TOKENS = {
        "여론조사",
        "응답률",
        "표본",
        "조사기관",
        "조사결과",
        "오차범위",
        "표본오차",
        "지지율",
    }
    _CANDIDATE_STOPWORDS = {
        "대통령",
        "정부",
        "민주당",
        "국민의힘",
        "정당",
        "국정",
        "찬성",
        "반대",
        "호감",
        "비호감",
        "여당",
        "야당",
    }
    _BODY_NOISE_MARKERS = (
        "무단전재",
        "재배포",
        "저작권",
        "Copyright",
        "기자 =",
        "기자=",
        "광고",
        "구독",
        "기사입력",
        "기사수정",
    )
    _LOCAL_OFFICE_HINTS = ("구청장", "군수", "시장")
    _QUERY_TEMPLATES = (
        "{election} {region} 여론조사",
        "{election} {region} {office} 지지율",
        "{election} {region} 가상대결 조사기관",
        "{election} {region} 표본 오차범위 응답률",
    )

    def __init__(self, election_id: str = "2026_local", user_agent: str = "ElectionCollector/0.1") -> None:
        self.election_id = election_id
        self.user_agent = user_agent

    def run(
        self,
        *,
        seeds: Iterable[str],
        rss_feeds: Iterable[str] | None = None,
    ) -> CollectorOutput:
        output = CollectorOutput()
        urls, discover_errors, discover_stats = self.discover(seeds=seeds, rss_feeds=rss_feeds or [])
        output.review_queue.extend(discover_errors)
        output.stats.update(discover_stats)
        article_signature_seen: set[tuple[str, str, str]] = set()

        for url in urls:
            article, fetch_error = self.fetch(url)
            if fetch_error is not None:
                output.review_queue.append(fetch_error)
                continue
            if article is None:
                continue

            title_key = article.title.strip().lower()
            date_key = (article.published_at or "")[:10]
            publisher_key = article.publisher.strip().lower()
            signature = (title_key, date_key, publisher_key)
            if signature in article_signature_seen:
                output.stats["article_signature_dedup_dropped"] = int(
                    output.stats.get("article_signature_dedup_dropped", 0)
                ) + 1
                continue
            article_signature_seen.add(signature)
            output.articles.append(article)

            label, confidence = self.classify(article.raw_text)
            if label == "NON_POLL":
                continue
            if label == "POLL_MENTION":
                output.review_queue.append(
                    new_review_queue_item(
                        entity_type="article",
                        entity_id=article.id,
                        issue_type="classify_error",
                        stage="classify",
                        error_code="LOW_CONFIDENCE",
                        error_message=f"classification={label} confidence={confidence:.2f}",
                        source_url=article.url,
                        payload={"classification_label": label, "classification_confidence": confidence},
                    )
                )
                # POLL_MENTION은 검수 큐로만 보내고 자동 추출은 보류한다.
                continue

            gate_passed, gate_reason = self.pre_extract_gate(article)
            if not gate_passed:
                output.review_queue.append(
                    new_review_queue_item(
                        entity_type="article",
                        entity_id=article.id,
                        issue_type="classify_error",
                        stage="classify",
                        error_code=gate_reason or "GATE_FILTERED",
                        error_message="pre-extract classify gate filtered out article",
                        source_url=article.url,
                        payload={
                            "classification_label": label,
                            "classification_confidence": confidence,
                            "title": article.title,
                        },
                    )
                )
                continue

            observations, options, extract_errors = self.extract(article)
            output.poll_observations.extend(observations)
            output.poll_options.extend(options)
            output.review_queue.extend(extract_errors)

        issue_counts: dict[str, int] = {}
        for item in output.review_queue:
            issue_counts[item.issue_type] = issue_counts.get(item.issue_type, 0) + 1
        for key, value in issue_counts.items():
            output.stats[f"{key}_count"] = value
        output.stats["article_count"] = len(output.articles)
        output.stats["poll_observation_count"] = len(output.poll_observations)
        output.stats["poll_option_count"] = len(output.poll_options)
        output.stats["review_queue_count"] = len(output.review_queue)
        output.stats["valid_article_rate"] = (
            float(len(output.poll_observations)) / float(len(output.articles)) if output.articles else 0.0
        )
        return output

    def discover(
        self,
        *,
        seeds: Iterable[str],
        rss_feeds: Iterable[str],
    ) -> tuple[list[str], list[ReviewQueueItem], dict[str, int]]:
        urls: list[str] = []
        errors: list[ReviewQueueItem] = []
        seen: set[str] = set()
        raw_count = 0

        for seed in seeds:
            canonical = self._canonicalize_url(seed)
            if canonical:
                raw_count += 1
                if canonical not in seen:
                    seen.add(canonical)
                    urls.append(canonical)

        for rss_url in rss_feeds:
            try:
                xml_text = self._http_get_text(rss_url)
                parsed = ET.fromstring(xml_text)
                for tag_name in ("link",):
                    for elem in parsed.findall(f".//item/{tag_name}"):
                        if elem.text:
                            canonical = self._canonicalize_url(elem.text.strip())
                            if canonical and canonical not in seen:
                                seen.add(canonical)
                                urls.append(canonical)
                    for elem in parsed.findall(f".//entry/{tag_name}"):
                        href = elem.attrib.get("href") if elem.attrib else None
                        link_text = href or elem.text
                        if link_text:
                            canonical = self._canonicalize_url(link_text.strip())
                            if canonical:
                                raw_count += 1
                                if canonical not in seen:
                                    seen.add(canonical)
                                    urls.append(canonical)
            except Exception as exc:  # pragma: no cover - defensive path for network/rss failures
                errors.append(
                    new_review_queue_item(
                        entity_type="source",
                        entity_id=rss_url,
                        issue_type="discover_error",
                        stage="discover",
                        error_code=exc.__class__.__name__,
                        error_message=str(exc),
                        source_url=rss_url,
                        payload={},
                    )
                )
        stats = {
            "discover_raw_count": raw_count,
            "discover_unique_count": len(urls),
            "discover_dedup_dropped": max(0, raw_count - len(urls)),
        }
        return urls, errors, stats

    @classmethod
    def discovery_query_templates(cls) -> list[str]:
        return list(cls._QUERY_TEMPLATES)

    def fetch(self, url: str) -> tuple[Article | None, ReviewQueueItem | None]:
        try:
            if not self._robots_allowed(url):
                return None, new_review_queue_item(
                    entity_type="article",
                    entity_id=url,
                    issue_type="fetch_error",
                    stage="fetch",
                    error_code="ROBOTS_DISALLOW",
                    error_message="robots.txt disallow",
                    source_url=url,
                    payload={"url": url},
                )

            html = self._http_get_text(url)
            text = self._extract_main_text(html)
            title = self._extract_title(html) or self._fallback_title_from_url(url)
            publisher = self._extract_meta(html, "og:site_name") or urlparse(url).netloc
            published_at = (
                self._extract_meta(html, "article:published_time")
                or self._extract_meta(html, "og:published_time")
                or None
            )

            content_hash = sha256(text.encode("utf-8")).hexdigest()
            collected_at = utc_now_iso()
            article = Article(
                id=stable_id("art", url, content_hash),
                url=self._canonicalize_url(url),
                title=title,
                publisher=publisher,
                published_at=published_at,
                snippet=text[:220],
                collected_at=collected_at,
                raw_hash=content_hash,
                raw_text=text,
            )
            return article, None
        except (HTTPError, URLError) as exc:
            return None, new_review_queue_item(
                entity_type="article",
                entity_id=url,
                issue_type="fetch_error",
                stage="fetch",
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                source_url=url,
                payload={"url": url},
            )
        except Exception as exc:  # pragma: no cover - defensive path for unknown fetch failures
            return None, new_review_queue_item(
                entity_type="article",
                entity_id=url,
                issue_type="fetch_error",
                stage="fetch",
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                source_url=url,
                payload={"url": url},
            )

    def classify(self, raw_text: str) -> tuple[str, float]:
        lowered = raw_text.lower()
        include_hits = sum(1 for keyword in self._INCLUDE_KEYWORDS if keyword in raw_text)
        exclude_hit = any(keyword in raw_text for keyword in self._EXCLUDE_KEYWORDS)
        has_percent = bool(self._PERCENT_RE.search(raw_text))
        has_pollster = bool(self._POLLSTER_RE.search(raw_text))

        if exclude_hit and include_hits == 0:
            return "NON_POLL", 0.95
        if include_hits >= 2 and has_percent and (has_pollster or "조사" in lowered):
            return "POLL_REPORT", 0.93
        if include_hits >= 1 and has_percent:
            return "POLL_MENTION", 0.68
        return "NON_POLL", 0.90

    def extract(
        self,
        article: Article,
    ) -> tuple[list[PollObservation], list[PollOption], list[ReviewQueueItem]]:
        observations: list[PollObservation] = []
        options: list[PollOption] = []
        errors: list[ReviewQueueItem] = []

        margin_of_error = self._extract_margin_of_error(article.raw_text)
        sample_size = self._extract_sample_size(article.raw_text)
        response_rate = self._extract_response_rate(article.raw_text)
        region_mapping = self._extract_region_office(article.raw_text + "\n" + article.title)
        if region_mapping is None:
            errors.append(
                new_review_queue_item(
                    entity_type="article",
                    entity_id=article.id,
                    issue_type="mapping_error",
                    stage="extract",
                    error_code="REGION_OFFICE_NOT_MAPPED",
                    error_message="failed to map region_code/office_type to CommonCodeService and standard enum",
                    source_url=article.url,
                    payload={"title": article.title},
                )
            )
            return observations, options, errors
        region_code, office_type = region_mapping
        matchup_id = build_matchup_id(self.election_id, office_type, region_code)
        pollster = self._extract_pollster(article.raw_text)

        observation = PollObservation(
            id=stable_id("obs", article.id, matchup_id, pollster or "unknown"),
            article_id=article.id,
            survey_name=article.title,
            pollster=pollster or "미상조사기관",
            survey_start_date=None,
            survey_end_date=self._coerce_date(article.published_at),
            sample_size=sample_size,
            response_rate=response_rate,
            margin_of_error=margin_of_error,
            sponsor=None,
            method=None,
            region_code=region_code,
            office_type=office_type,
            matchup_id=matchup_id,
            verified=False,
            source_grade=None,
            ingestion_run_id=None,
            evidence_text=article.raw_text[:280],
            source_url=article.url,
            source_channel="article",
            source_channels=["article"],
        )
        observations.append(observation)

        try:
            extracted_pairs = self.extract_candidate_pairs(article.raw_text, title=article.title, mode="v2")
            extracted_any = len(extracted_pairs) > 0
            for pair in extracted_pairs:
                options.append(
                    self._build_option(
                        observation=observation,
                        option_type="candidate",
                        option_name=pair["name"],
                        value_raw=pair["value_raw"],
                        evidence_text=pair["evidence_text"],
                    )
                )

            if not extracted_any:
                reason = self._diagnose_extract_failure(article.raw_text, article.title)
                errors.append(
                    new_review_queue_item(
                        entity_type="poll_observation",
                        entity_id=observation.id,
                        issue_type="extract_error",
                        stage="extract",
                        error_code=reason,
                        error_message="no candidate/value pair extracted",
                        source_url=article.url,
                        payload={"article_id": article.id},
                    )
                )
        except Exception as exc:
            errors.append(
                new_review_queue_item(
                    entity_type="poll_observation",
                    entity_id=observation.id,
                    issue_type="extract_error",
                    stage="extract",
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    source_url=article.url,
                    payload={"article_id": article.id},
                )
            )

        return observations, options, errors

    def extract_candidate_pairs(
        self,
        text: str,
        *,
        title: str | None = None,
        mode: str = "v2",
    ) -> list[dict[str, str]]:
        if mode == "v1":
            return self.extract_candidate_pairs_v1(text)
        return self.extract_candidate_pairs_v2(text=text, title=title)

    def extract_candidate_pairs_v1(self, text: str) -> list[dict[str, str]]:
        pairs: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for match in self._MATCHUP_RE.finditer(text):
            a_name, a_value, b_name, b_value = match.groups()
            for name, value in ((a_name, f"{a_value}%"), (b_name, f"{b_value}%")):
                key = (name, value)
                if key in seen:
                    continue
                seen.add(key)
                pairs.append({"name": name, "value_raw": value, "evidence_text": match.group(0)})

        if pairs:
            return pairs

        # Fallback extraction for generic "이름 + 수치" patterns.
        for match in self._NAME_VALUE_RE.finditer(text):
            name, value_raw = match.groups()
            if name in self._NON_CANDIDATE_TOKENS:
                continue
            key = (name, value_raw)
            if key in seen:
                continue
            seen.add(key)
            pairs.append({"name": name, "value_raw": value_raw, "evidence_text": match.group(0)})
        return pairs

    def extract_candidate_pairs_v2(self, text: str, title: str | None = None) -> list[dict[str, str]]:
        cleaned_body = self._clean_body_for_extraction(text)
        focus_text = self._candidate_value_signals(cleaned_body, title=title)

        pairs: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for source in (focus_text, cleaned_body):
            if not source:
                continue
            for match in self._MATCHUP_RE.finditer(source):
                a_name, a_value, b_name, b_value = match.groups()
                for name, value in ((a_name, f"{a_value}%"), (b_name, f"{b_value}%")):
                    if not self._is_candidate_name(name):
                        continue
                    key = (name, value)
                    if key in seen:
                        continue
                    seen.add(key)
                    pairs.append({"name": name, "value_raw": value, "evidence_text": match.group(0)})

        if pairs:
            return pairs

        for match in self._NAME_VALUE_RE.finditer(focus_text or cleaned_body):
            name, value_raw = match.groups()
            if not self._is_candidate_name(name):
                continue
            key = (name, value_raw)
            if key in seen:
                continue
            seen.add(key)
            pairs.append({"name": name, "value_raw": value_raw, "evidence_text": match.group(0)})
        return pairs

    def pre_extract_gate(self, article: Article) -> tuple[bool, str | None]:
        text = f"{article.title}\n{article.raw_text}"

        if self._is_policy_or_qualitative_only(text):
            return False, "GATE_POLICY_QUALITATIVE_ONLY"

        if not self.extract_candidate_pairs(text, title=article.title, mode="v2"):
            return False, "GATE_NO_CANDIDATE_NUMERIC_SIGNAL"

        if self._extract_region_office(text) is None:
            return False, "GATE_REGION_OFFICE_UNMAPPED"

        return True, None

    def _build_option(
        self,
        *,
        observation: PollObservation,
        option_type: str,
        option_name: str,
        value_raw: str,
        evidence_text: str,
    ) -> PollOption:
        normalized = normalize_value(value_raw)
        candidate_id = build_candidate_id(option_name)
        return PollOption(
            id=stable_id("opt", observation.id, candidate_id, value_raw),
            observation_id=observation.id,
            option_type=option_type,
            option_name=option_name,
            candidate_id=candidate_id,
            value_raw=value_raw,
            value_min=normalized.value_min,
            value_max=normalized.value_max,
            value_mid=normalized.value_mid,
            is_missing=normalized.is_missing,
            margin_of_error=observation.margin_of_error,
            evidence_text=evidence_text,
        )

    def _canonicalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        keep_query = [(k, v) for k, v in query_pairs if not k.startswith("utm_") and k not in {"fbclid", "gclid"}]
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                urlencode(keep_query, doseq=True),
                "",
            )
        )

    def _http_get_text(self, url: str, timeout: int = 12, retries: int = 2) -> str:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                req = request.Request(url, headers={"User-Agent": self.user_agent})
                with request.urlopen(req, timeout=timeout) as response:
                    raw = response.read()
                    charset = response.headers.get_content_charset() or "utf-8"
                    return raw.decode(charset, errors="replace")
            except HTTPError as exc:
                if exc.code >= 500 and attempt < retries:
                    last_error = exc
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise
            except (URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("unexpected fetch failure")

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
        except Exception:
            return True
        return parser.can_fetch(self.user_agent, url)

    def _extract_title(self, html: str) -> str | None:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        return self._cleanup_space(unescape(m.group(1)))

    def _extract_meta(self, html: str, key: str) -> str | None:
        pattern = (
            r'<meta[^>]+(?:property|name)=["\']'
            + re.escape(key)
            + r'["\'][^>]+content=["\'](.*?)["\']'
        )
        m = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        return self._cleanup_space(unescape(m.group(1)))

    def _extract_main_text(self, html: str) -> str:
        cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = unescape(cleaned)
        return self._cleanup_space(cleaned)

    def _cleanup_space(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _fallback_title_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        name = parsed.path.rsplit("/", 1)[-1]
        return name or parsed.netloc

    def _extract_margin_of_error(self, text: str) -> float | None:
        m = self._MARGIN_RE.search(text)
        return float(m.group(1)) if m else None

    def _extract_sample_size(self, text: str) -> int | None:
        m = self._SAMPLE_RE.search(text)
        if not m:
            return None
        return int(m.group(1).replace(",", ""))

    def _extract_response_rate(self, text: str) -> float | None:
        m = self._RESPONSE_RATE_RE.search(text)
        return float(m.group(1)) if m else None

    def _clean_body_for_extraction(self, text: str) -> str:
        normalized = self._cleanup_space(text)
        if not normalized:
            return normalized

        normalized = re.sub(r"https?://\S+", " ", normalized)
        segments = re.split(r"(?<=[\.\?\!])\s+|(?<=다)\s+", normalized)
        kept: list[str] = []
        for seg in segments:
            part = seg.strip()
            if not part:
                continue
            if any(marker in part for marker in self._BODY_NOISE_MARKERS):
                continue
            if len(part) < 7:
                continue
            kept.append(part)
        return self._cleanup_space(" ".join(kept))

    def _candidate_value_signals(self, cleaned_body: str, title: str | None = None) -> str:
        lines = re.split(r"(?<=[\.\?\!])\s+|(?<=다)\s+", cleaned_body)
        focus: list[str] = []
        for line in lines:
            sentence = line.strip()
            if not sentence:
                continue
            has_percent = bool(self._PERCENT_RE.search(sentence))
            has_poll = any(k in sentence for k in self._INCLUDE_KEYWORDS)
            has_office = any(k in sentence for k in self._GATE_ELECTION_OFFICE_HINTS)
            if has_percent and (has_poll or has_office):
                focus.append(sentence)
        if title:
            focus.append(title)
        return self._cleanup_space(" ".join(focus))

    def _is_candidate_name(self, name: str) -> bool:
        clean = name.strip()
        if len(clean) < 2:
            return False
        if clean in self._NON_CANDIDATE_TOKENS:
            return False
        if clean in self._CANDIDATE_STOPWORDS:
            return False
        if clean.endswith(("정당", "정부", "대통령")):
            return False
        return True

    def _diagnose_extract_failure(self, body_text: str, title: str | None = None) -> str:
        full_text = f"{title or ''}\n{body_text}"
        if self._is_policy_or_qualitative_only(full_text):
            return "POLICY_ONLY_SIGNAL"
        raw_names = [match.group(1) for match in self._NAME_VALUE_RE.finditer(full_text)]
        if raw_names and not any(self._is_candidate_name(name) for name in raw_names):
            return "POLICY_ONLY_SIGNAL"
        if not self._PERCENT_RE.search(full_text):
            return "NO_NUMERIC_SIGNAL"
        if not self.extract_candidate_pairs_v1(title or ""):
            return "NO_TITLE_CANDIDATE_SIGNAL"
        return "NO_BODY_CANDIDATE_SIGNAL"

    def _is_policy_or_qualitative_only(self, text: str) -> bool:
        has_policy = any(keyword in text for keyword in self._GATE_POLICY_KEYWORDS)
        has_preference = any(keyword in text for keyword in self._GATE_PREFERENCE_KEYWORDS)
        has_election_office_hint = any(keyword in text for keyword in self._GATE_ELECTION_OFFICE_HINTS)
        has_candidate_numeric = bool(self._MATCHUP_RE.search(text)) or bool(self._NAME_VALUE_RE.search(text))

        if has_policy and not has_election_office_hint:
            return True
        if has_preference and not has_candidate_numeric:
            return True
        return False

    def _extract_pollster(self, text: str) -> str | None:
        m = self._POLLSTER_RE.search(text)
        return m.group(1) if m else None

    def _extract_region_office(self, text: str) -> tuple[str, str] | None:
        for needle, region_code, office_type in REGION_OFFICE_DIRECT_PATTERNS:
            if needle in text:
                return region_code, office_type

        region_code = self._extract_region_code(text)
        if region_code is None:
            return None

        is_sigungu = not region_code.endswith("-000")
        if is_sigungu:
            if "재보궐" in text or "보궐" in text:
                return region_code, "재보궐"
            if "의회" in text:
                return region_code, "기초의회"
            if any(hint in text for hint in self._LOCAL_OFFICE_HINTS):
                return region_code, "기초자치단체장"

        if "교육감" in text:
            return region_code, "교육감"
        if "광역" in text and "의회" in text:
            return region_code, "광역의회"
        if "기초" in text and "의회" in text:
            return region_code, "기초의회"
        if "기초" in text and "단체장" in text:
            return region_code, "기초자치단체장"
        if "재보궐" in text or "보궐" in text:
            return region_code, "재보궐"
        if "단체장" in text:
            if is_sigungu:
                return region_code, "기초자치단체장"
            return region_code, "광역자치단체장"
        if "시장" in text and not is_sigungu:
            return region_code, "광역자치단체장"
        if "지사" in text and not is_sigungu:
            return region_code, "광역자치단체장"
        return None

    def _extract_region_code(self, text: str) -> str | None:
        for alias in sorted(REGION_ALIASES.keys(), key=len, reverse=True):
            if alias in text:
                code = REGION_ALIASES[alias]
                if code in COMMON_CODE_REGIONS:
                    return code
        return None

    def _coerce_date(self, iso_date_time: str | None) -> str | None:
        if not iso_date_time:
            return None
        try:
            dt = datetime.fromisoformat(iso_date_time.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).date().isoformat()
        except ValueError:
            return None
