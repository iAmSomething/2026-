from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import re
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

    def to_dict(self) -> dict:
        return {
            "articles": [row.to_dict() for row in self.articles],
            "poll_observations": [row.to_dict() for row in self.poll_observations],
            "poll_options": [row.to_dict() for row in self.poll_options],
            "review_queue": [row.to_dict() for row in self.review_queue],
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
        urls, discover_errors = self.discover(seeds=seeds, rss_feeds=rss_feeds or [])
        output.review_queue.extend(discover_errors)

        for url in urls:
            article, fetch_error = self.fetch(url)
            if fetch_error is not None:
                output.review_queue.append(fetch_error)
                continue
            if article is None:
                continue
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

            observations, options, extract_errors = self.extract(article)
            output.poll_observations.extend(observations)
            output.poll_options.extend(options)
            output.review_queue.extend(extract_errors)

        return output

    def discover(
        self,
        *,
        seeds: Iterable[str],
        rss_feeds: Iterable[str],
    ) -> tuple[list[str], list[ReviewQueueItem]]:
        urls: list[str] = []
        errors: list[ReviewQueueItem] = []
        seen: set[str] = set()

        for seed in seeds:
            canonical = self._canonicalize_url(seed)
            if canonical and canonical not in seen:
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
                            if canonical and canonical not in seen:
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
        return urls, errors

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
            region_code=region_code,
            office_type=office_type,
            matchup_id=matchup_id,
            verified=False,
            source_grade=None,
            ingestion_run_id=None,
            evidence_text=article.raw_text[:280],
            source_url=article.url,
        )
        observations.append(observation)

        try:
            extracted_any = False
            for match in self._MATCHUP_RE.finditer(article.raw_text):
                a_name, a_value, b_name, b_value = match.groups()
                options.append(
                    self._build_option(
                        observation=observation,
                        option_type="candidate",
                        option_name=a_name,
                        value_raw=f"{a_value}%",
                        evidence_text=match.group(0),
                    )
                )
                options.append(
                    self._build_option(
                        observation=observation,
                        option_type="candidate",
                        option_name=b_name,
                        value_raw=f"{b_value}%",
                        evidence_text=match.group(0),
                    )
                )
                extracted_any = True

            if not extracted_any:
                # Fallback extraction for generic "이름 + 수치" patterns.
                for match in self._NAME_VALUE_RE.finditer(article.raw_text):
                    name, value_raw = match.groups()
                    if name in self._NON_CANDIDATE_TOKENS:
                        continue
                    options.append(
                        self._build_option(
                            observation=observation,
                            option_type="candidate",
                            option_name=name,
                            value_raw=value_raw,
                            evidence_text=match.group(0),
                        )
                    )
                    extracted_any = True

            if not extracted_any:
                errors.append(
                    new_review_queue_item(
                        entity_type="poll_observation",
                        entity_id=observation.id,
                        issue_type="extract_error",
                        stage="extract",
                        error_code="NO_NUMERIC_SIGNAL",
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

    def _http_get_text(self, url: str, timeout: int = 12) -> str:
        req = request.Request(url, headers={"User-Agent": self.user_agent})
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")

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
