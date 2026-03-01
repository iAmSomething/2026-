from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
import os
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
    _POLLSTER_TOKENS = (
        "한국사회여론연구소",
        "KSOI",
        "리얼미터",
        "한국갤럽",
        "갤럽",
        "NBS",
        "조원씨앤아이",
        "미디어리서치",
        "한국리서치",
        "엠브레인퍼블릭",
        "케이스탯리서치",
        "코리아리서치",
        "KBS",
        "MBC",
        "SBS",
    )
    _POLLSTER_ALIAS_MAP = {
        "한국사회여론연구소": "KSOI",
        "갤럽": "한국갤럽",
    }
    _POLLSTER_RE = re.compile(
        "(" + "|".join(re.escape(token) for token in sorted(_POLLSTER_TOKENS, key=len, reverse=True)) + ")"
    )
    _SURVEY_PERIOD_YMD_RANGE_RE = re.compile(
        r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?\s*(?:~|∼|-|부터)\s*"
        r"(?:(20\d{2})\s*[.\-/년]\s*)?(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?(?:까지)?"
    )
    _SURVEY_PERIOD_MD_RANGE_RE = re.compile(
        r"(\d{1,2})\s*월\s*(\d{1,2})\s*일?\s*(?:~|∼|-|부터)\s*(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*일?(?:까지)?"
    )
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
        "응답률은",
        "표본",
        "조사기관",
        "조사결과",
        "오차범위",
        "표본오차",
        "오차는",
        "지지율",
        "지지율은",
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
        "응답률은",
        "오차는",
        "지지율은",
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
    _DATE_POLICY_DEFAULT = "strict_fail"
    _DATE_POLICY_ALLOW_ESTIMATED = "allow_estimated_timestamp"
    _DATE_INFERENCE_TZ = timezone(timedelta(hours=9))
    _DATE_INFERENCE_TZ_NAME = "Asia/Seoul"
    _RELATIVE_FIXED_DATE_PATTERNS = (
        (re.compile(r"그저께"), -3, "relative_day", 0.93, "그저께"),
        (re.compile(r"그제"), -2, "relative_day", 0.94, "그제"),
        (re.compile(r"어제"), -1, "relative_day", 0.95, "어제"),
        (re.compile(r"오늘|금일|당일"), 0, "relative_day", 0.9, "오늘"),
        (re.compile(r"지난주|전주"), -7, "relative_week", 0.82, "지난주"),
        (re.compile(r"이번주|금주"), 0, "relative_week_current", 0.58, "이번주"),
        (re.compile(r"최근"), 0, "relative_recent", 0.45, "최근"),
    )
    _RELATIVE_N_DAYS_AGO_RE = re.compile(r"(\d{1,2})일전")
    _RELATIVE_N_WEEKS_AGO_RE = re.compile(r"(\d{1,2})주전")
    _RELATIVE_N_MONTHS_AGO_RE = re.compile(r"(\d{1,2})개월전")
    _RELATIVE_LAST_N_DAYS_RE = re.compile(r"지난(\d{1,2})일")
    _RELATIVE_LAST_MONTH_RE = re.compile(r"지난달")
    _SCENARIO_NAME_RE = re.compile(r"[가-힣]{2,6}")
    _SCENARIO_H2H_PAIR_RE = re.compile(
        r"([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?\s*[-~]\s*([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?"
    )
    _SCENARIO_MULTI_SINGLE_RE = re.compile(r"다자대결[^가-힣0-9%]*([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?")

    def __init__(
        self,
        election_id: str = "2026_local",
        user_agent: str = "ElectionCollector/0.1",
        relative_date_policy: str | None = None,
    ) -> None:
        self.election_id = election_id
        self.user_agent = user_agent
        configured_policy = (
            (relative_date_policy or os.getenv("RELATIVE_DATE_POLICY", self._DATE_POLICY_DEFAULT)).strip().lower()
        )
        if configured_policy not in {self._DATE_POLICY_DEFAULT, self._DATE_POLICY_ALLOW_ESTIMATED}:
            configured_policy = self._DATE_POLICY_DEFAULT
        self.relative_date_policy = configured_policy

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
        (
            survey_end_date,
            date_resolution,
            date_inference_mode,
            date_inference_confidence,
            date_inference_error,
        ) = self._resolve_survey_date_inference(article)
        if date_inference_error is not None:
            errors.append(date_inference_error)

        survey_blocks = self._split_survey_blocks(article.raw_text)
        if not survey_blocks:
            survey_blocks = [article.raw_text]
        has_multi_blocks = len(survey_blocks) > 1

        for block_index, raw_block in enumerate(survey_blocks):
            block_text = self._cleanup_space(raw_block)
            if not block_text:
                continue

            pollster_tokens = self._extract_pollster_tokens(block_text)
            pollster = pollster_tokens[0] if pollster_tokens else self._extract_pollster(article.raw_text)
            block_margin = self._extract_margin_of_error(block_text)
            block_sample = self._extract_sample_size(block_text)
            block_response_rate = self._extract_response_rate(block_text)

            if not has_multi_blocks:
                if block_margin is None:
                    block_margin = margin_of_error
                if block_sample is None:
                    block_sample = sample_size
                if block_response_rate is None:
                    block_response_rate = response_rate

            block_start_date, block_end_date = self._extract_survey_period(block_text, article=article)
            block_question_group = self._extract_poll_block_question_group(
                article_title=article.title,
                block_text=block_text,
                has_multi_blocks=has_multi_blocks,
            )
            poll_block_id = self._build_poll_block_id(
                block_index=block_index,
                pollster=pollster,
                survey_start_date=block_start_date,
                survey_end_date=block_end_date or survey_end_date,
                sample_size=block_sample,
                question_group=block_question_group,
            )
            observation = PollObservation(
                id=stable_id("obs", article.id, matchup_id, pollster or "unknown", str(block_index)),
                article_id=article.id,
                poll_block_id=poll_block_id,
                survey_name=article.title,
                pollster=pollster or "미상조사기관",
                survey_start_date=block_start_date,
                survey_end_date=block_end_date or survey_end_date,
                sample_size=block_sample,
                response_rate=block_response_rate,
                margin_of_error=block_margin,
                sponsor=None,
                method=None,
                region_code=region_code,
                office_type=office_type,
                matchup_id=matchup_id,
                verified=False,
                source_grade=None,
                ingestion_run_id=None,
                evidence_text=block_text[:280],
                source_url=article.url,
                source_channel="article",
                source_channels=["article"],
                date_resolution=date_resolution,
                date_inference_mode=date_inference_mode,
                date_inference_confidence=date_inference_confidence,
            )
            observations.append(observation)

            if len(pollster_tokens) >= 2:
                errors.append(
                    new_review_queue_item(
                        entity_type="poll_observation",
                        entity_id=observation.id,
                        issue_type="metadata_cross_contamination",
                        stage="extract",
                        error_code="MULTIPLE_POLLSTER_TOKENS_IN_OBSERVATION",
                        error_message="multiple pollster tokens detected in one survey block",
                        source_url=article.url,
                        payload={
                            "article_id": article.id,
                            "pollsters": pollster_tokens,
                            "block_index": block_index,
                            "block_text": block_text[:400],
                        },
                    )
                )

            try:
                extracted_pairs = self.extract_candidate_pairs(
                    block_text,
                    title=None if has_multi_blocks else article.title,
                    mode="v2",
                )
                extracted_any = len(extracted_pairs) > 0
                block_options: list[PollOption] = []
                for pair in extracted_pairs:
                    block_options.append(
                        self._build_option(
                            observation=observation,
                            option_type="candidate",
                            option_name=pair["name"],
                            value_raw=pair["value_raw"],
                            evidence_text=pair["evidence_text"],
                            poll_block_id=poll_block_id,
                        )
                    )

                if not extracted_any:
                    reason = self._diagnose_extract_failure(block_text, article.title)
                    errors.append(
                        new_review_queue_item(
                            entity_type="poll_observation",
                            entity_id=observation.id,
                            issue_type="extract_error",
                            stage="extract",
                            error_code=reason,
                            error_message="no candidate/value pair extracted",
                            source_url=article.url,
                            payload={"article_id": article.id, "block_index": block_index},
                        )
                    )
                else:
                    self._split_candidate_matchup_scenarios(
                        survey_name=None if has_multi_blocks else article.title,
                        body_text=block_text,
                        observation=observation,
                        options=block_options,
                    )
                    options.extend(block_options)
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
                        payload={"article_id": article.id, "block_index": block_index},
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
        poll_block_id: str | None = None,
        scenario_key: str | None = "default",
        scenario_type: str | None = None,
        scenario_title: str | None = None,
    ) -> PollOption:
        normalized = normalize_value(value_raw)
        candidate_id = build_candidate_id(option_name)
        normalized_scenario_key = (scenario_key or "default").strip() or "default"
        return PollOption(
            id=stable_id("opt", observation.id, candidate_id, value_raw, normalized_scenario_key),
            observation_id=observation.id,
            poll_block_id=poll_block_id or observation.poll_block_id,
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
            scenario_key=normalized_scenario_key,
            scenario_type=scenario_type,
            scenario_title=scenario_title,
        )

    def _extract_poll_block_question_group(
        self,
        *,
        article_title: str,
        block_text: str,
        has_multi_blocks: bool,
    ) -> str:
        if not has_multi_blocks:
            return self._cleanup_space(article_title)[:120]
        focus = self._candidate_value_signals(block_text, title=None)
        if focus:
            return self._cleanup_space(focus)[:120]
        return self._cleanup_space(article_title)[:120]

    def _build_poll_block_id(
        self,
        *,
        block_index: int,
        pollster: str | None,
        survey_start_date: str | None,
        survey_end_date: str | None,
        sample_size: int | None,
        question_group: str,
    ) -> str:
        question_token = self._cleanup_space(question_group)
        if not question_token:
            question_token = f"block-{block_index}"
        return stable_id(
            "pblk",
            pollster or "미상조사기관",
            survey_start_date or "",
            survey_end_date or "",
            str(sample_size or ""),
            question_token,
        )

    def _split_candidate_matchup_scenarios(
        self,
        *,
        survey_name: str | None,
        body_text: str | None,
        observation: PollObservation,
        options: list[PollOption],
    ) -> bool:
        text = self._cleanup_space(f"{survey_name or ''} {body_text or ''}")
        if "다자대결" not in text:
            return False

        candidate_indexes = [idx for idx, row in enumerate(options) if row.option_type == "candidate"]
        if len(candidate_indexes) < 3:
            return False

        for idx in candidate_indexes:
            if not options[idx].scenario_key:
                options[idx].scenario_key = "default"

        h2h_pairs = self._extract_h2h_pairs(text)
        if len(h2h_pairs) < 2:
            return False

        names_by_index = {idx: self._scenario_name_token(options[idx].option_name) for idx in candidate_indexes}
        candidate_indexes_all = list(candidate_indexes)
        names_all = dict(names_by_index)
        used_indexes: set[int] = set()
        assigned = False
        anchor_for_multi: str | None = None

        for left_name, left_value, right_name, right_value in h2h_pairs:
            left_idx = self._match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=left_name,
                value=left_value,
                exclude=used_indexes,
            )
            if left_idx is None:
                left_idx = self._clone_candidate_option(
                    options=options,
                    observation=observation,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=left_name,
                    value=left_value,
                    evidence_text=text,
                )
                if left_idx is not None:
                    candidate_indexes_all.append(left_idx)
                    names_all[left_idx] = left_name

            right_idx = self._match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=right_name,
                value=right_value,
                exclude=used_indexes,
            )
            if right_idx is None:
                right_idx = self._clone_candidate_option(
                    options=options,
                    observation=observation,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=right_name,
                    value=right_value,
                    evidence_text=text,
                )
                if right_idx is not None:
                    candidate_indexes_all.append(right_idx)
                    names_all[right_idx] = right_name

            if left_idx is None or right_idx is None or left_idx == right_idx:
                continue

            scenario_key = f"h2h-{left_name}-{right_name}"
            scenario_title = f"{left_name} vs {right_name}"
            for idx, name, value in (
                (left_idx, left_name, left_value),
                (right_idx, right_name, right_value),
            ):
                row = options[idx]
                self._override_option_value(row, value)
                row.option_name = name
                row.candidate_id = build_candidate_id(name)
                row.scenario_key = scenario_key
                row.scenario_type = "head_to_head"
                row.scenario_title = scenario_title
                self._refresh_option_identity(option=row, observation=observation)
                used_indexes.add(idx)

            if anchor_for_multi is None:
                anchor_for_multi = left_name
            assigned = True

        multi_indexes = [idx for idx in candidate_indexes_all if idx not in used_indexes and names_all.get(idx)]
        multi_anchor = self._extract_multi_anchor(text)
        if multi_anchor is not None:
            multi_name, multi_value = multi_anchor
            multi_idx = self._match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=multi_name,
                value=multi_value,
                exclude=used_indexes,
            )
            if multi_idx is None:
                multi_idx = self._clone_candidate_option(
                    options=options,
                    observation=observation,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=multi_name,
                    value=multi_value,
                    evidence_text=text,
                )
                if multi_idx is not None:
                    candidate_indexes_all.append(multi_idx)
                    names_all[multi_idx] = multi_name
            if multi_idx is not None:
                self._override_option_value(options[multi_idx], multi_value)
                options[multi_idx].option_name = multi_name
                options[multi_idx].candidate_id = build_candidate_id(multi_name)
                self._refresh_option_identity(option=options[multi_idx], observation=observation)
                if multi_idx not in multi_indexes and multi_idx not in used_indexes:
                    multi_indexes.append(multi_idx)

        if not assigned or not multi_indexes:
            return False

        multi_key = f"multi-{anchor_for_multi or names_all.get(multi_indexes[0]) or '후보'}"
        for idx in multi_indexes:
            row = options[idx]
            row.scenario_key = multi_key
            row.scenario_type = "multi_candidate"
            row.scenario_title = "다자대결"
            self._refresh_option_identity(option=row, observation=observation)
        return True

    def _extract_h2h_pairs(self, text: str) -> list[tuple[str, float, str, float]]:
        pairs: list[tuple[str, float, str, float]] = []
        seen: set[tuple[str, float, str, float]] = set()
        for match in self._SCENARIO_H2H_PAIR_RE.finditer(text):
            left_name = self._scenario_name_token(match.group(1))
            right_name = self._scenario_name_token(match.group(3))
            if not left_name or not right_name or left_name == right_name:
                continue
            try:
                left_value = float(match.group(2))
                right_value = float(match.group(4))
            except (TypeError, ValueError):
                continue
            key = (left_name, left_value, right_name, right_value)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(key)
        return pairs

    def _extract_multi_anchor(self, text: str) -> tuple[str, float] | None:
        match = self._SCENARIO_MULTI_SINGLE_RE.search(text)
        if not match:
            return None
        name = self._scenario_name_token(match.group(1))
        if not name:
            return None
        try:
            value = float(match.group(2))
        except (TypeError, ValueError):
            return None
        return name, value

    def _scenario_name_token(self, value: str | None) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        match = self._SCENARIO_NAME_RE.search(text)
        return match.group(0) if match else text

    def _scenario_value(self, option: PollOption) -> float:
        if option.value_mid is None:
            return float("-inf")
        try:
            return float(option.value_mid)
        except (TypeError, ValueError):
            return float("-inf")

    def _match_candidate_index(
        self,
        *,
        options: list[PollOption],
        candidate_indexes: list[int],
        names_by_index: dict[int, str],
        name: str,
        value: float,
        exclude: set[int],
    ) -> int | None:
        candidates = [idx for idx in candidate_indexes if idx not in exclude and names_by_index.get(idx) == name]
        if not candidates:
            return None
        exact = [idx for idx in candidates if abs(self._scenario_value(options[idx]) - value) <= 0.15]
        if not exact:
            return None
        exact.sort(key=lambda idx: abs(self._scenario_value(options[idx]) - value))
        return exact[0]

    def _clone_candidate_option(
        self,
        *,
        options: list[PollOption],
        observation: PollObservation,
        candidate_indexes: list[int],
        names_by_index: dict[int, str],
        name: str,
        value: float,
        evidence_text: str,
    ) -> int | None:
        template_indexes = [idx for idx in candidate_indexes if names_by_index.get(idx) == name]
        if not template_indexes:
            return None
        template_indexes.sort(key=lambda idx: abs(self._scenario_value(options[idx]) - value))
        template = options[template_indexes[0]]
        cloned = self._build_option(
            observation=observation,
            option_type=template.option_type,
            option_name=name,
            value_raw=f"{value:.1f}%",
            evidence_text=template.evidence_text or evidence_text,
            scenario_key="default",
        )
        options.append(cloned)
        return len(options) - 1

    def _override_option_value(self, option: PollOption, value: float) -> None:
        raw = f"{value:.1f}%"
        normalized = normalize_value(raw)
        option.value_raw = raw
        option.value_min = normalized.value_min
        option.value_max = normalized.value_max
        option.value_mid = normalized.value_mid
        option.is_missing = normalized.is_missing

    def _refresh_option_identity(self, *, option: PollOption, observation: PollObservation) -> None:
        option.id = stable_id(
            "opt",
            observation.id,
            option.candidate_id or "",
            option.value_raw or "",
            option.scenario_key or "default",
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

    def _split_survey_blocks(self, text: str) -> list[str]:
        cleaned = self._cleanup_space(text)
        if not cleaned:
            return []

        pollster_matches = list(self._POLLSTER_RE.finditer(cleaned))
        if len(pollster_matches) < 2:
            return [cleaned]

        blocks: list[str] = []
        prefix = cleaned[: pollster_matches[0].start()].strip()
        for idx, match in enumerate(pollster_matches):
            start = match.start()
            end = pollster_matches[idx + 1].start() if idx + 1 < len(pollster_matches) else len(cleaned)
            segment = self._cleanup_space(cleaned[start:end])
            if idx == 0 and prefix:
                segment = self._cleanup_space(f"{prefix} {segment}")
            if not segment:
                continue
            if blocks and self._extract_pollster(segment) == self._extract_pollster(blocks[-1]):
                blocks[-1] = self._cleanup_space(f"{blocks[-1]} {segment}")
            else:
                blocks.append(segment)

        merged: list[str] = []
        pending_prefix = ""
        for block in blocks:
            merged_block = self._cleanup_space(f"{pending_prefix} {block}") if pending_prefix else block
            has_candidate_signal = bool(self.extract_candidate_pairs(merged_block, title=None, mode="v2"))
            if has_candidate_signal:
                merged.append(merged_block)
                pending_prefix = ""
                continue
            if merged:
                merged[-1] = self._cleanup_space(f"{merged[-1]} {merged_block}")
            else:
                pending_prefix = merged_block

        if pending_prefix:
            if merged:
                merged[0] = self._cleanup_space(f"{pending_prefix} {merged[0]}")
            else:
                merged = [pending_prefix]

        return merged if len(merged) >= 2 else [cleaned]

    def _safe_date(self, year: int, month: int, day: int) -> date | None:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _extract_survey_period(self, text: str, *, article: Article) -> tuple[str | None, str | None]:
        year_anchor = (self._parse_anchor_date(article.published_at) or self._parse_anchor_date(article.collected_at))
        base_year = year_anchor.year if year_anchor else datetime.now(self._DATE_INFERENCE_TZ).year

        ymd_match = self._SURVEY_PERIOD_YMD_RANGE_RE.search(text)
        if ymd_match:
            start_year = int(ymd_match.group(1))
            start_month = int(ymd_match.group(2))
            start_day = int(ymd_match.group(3))
            end_year = int(ymd_match.group(4)) if ymd_match.group(4) else start_year
            end_month = int(ymd_match.group(5))
            end_day = int(ymd_match.group(6))
            start_date = self._safe_date(start_year, start_month, start_day)
            end_date = self._safe_date(end_year, end_month, end_day)
            if start_date and end_date:
                return start_date.isoformat(), end_date.isoformat()
            return None, None

        md_match = self._SURVEY_PERIOD_MD_RANGE_RE.search(text)
        if not md_match:
            return None, None

        start_month = int(md_match.group(1))
        start_day = int(md_match.group(2))
        end_month = int(md_match.group(3)) if md_match.group(3) else start_month
        end_day = int(md_match.group(4))

        start_year = base_year
        end_year = base_year
        if end_month < start_month:
            end_year += 1

        start_date = self._safe_date(start_year, start_month, start_day)
        end_date = self._safe_date(end_year, end_month, end_day)
        if start_date and end_date:
            return start_date.isoformat(), end_date.isoformat()
        return None, None

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

    def _normalize_pollster(self, raw_token: str) -> str:
        token = self._cleanup_space(raw_token)
        return self._POLLSTER_ALIAS_MAP.get(token, token)

    def _extract_pollster_tokens(self, text: str) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()
        for match in self._POLLSTER_RE.finditer(text):
            normalized = self._normalize_pollster(match.group(0))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(normalized)
        return tokens

    def _extract_pollster(self, text: str) -> str | None:
        tokens = self._extract_pollster_tokens(text)
        return tokens[0] if tokens else None

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

    @classmethod
    def _parse_anchor_date(cls, value: str | None) -> date | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            try:
                return date.fromisoformat(text)
            except ValueError:
                pass
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=cls._DATE_INFERENCE_TZ)
        return dt.astimezone(cls._DATE_INFERENCE_TZ).date()

    @classmethod
    def _coerce_date(cls, iso_date_time: str | None) -> str | None:
        parsed = cls._parse_anchor_date(iso_date_time)
        return parsed.isoformat() if parsed else None

    def _parse_date(self, iso_date_time: str | None) -> date | None:
        return self._parse_anchor_date(iso_date_time)

    @staticmethod
    def _shift_months(anchor: date, months: int) -> date:
        zero_based = (anchor.year * 12) + (anchor.month - 1) + months
        year = zero_based // 12
        month = (zero_based % 12) + 1
        day = min(anchor.day, monthrange(year, month)[1])
        return date(year, month, day)

    def _find_relative_date_signal(
        self,
        text: str,
        *,
        anchor_date: date,
    ) -> tuple[date, str, float, str, int] | None:
        compact = re.sub(r"\s+", "", text)

        for pattern, offset_days, resolution, confidence, signal in self._RELATIVE_FIXED_DATE_PATTERNS:
            if pattern.search(compact):
                inferred = anchor_date + timedelta(days=offset_days)
                return inferred, resolution, confidence, signal, offset_days

        m_last_n_days = self._RELATIVE_LAST_N_DAYS_RE.search(compact)
        if m_last_n_days:
            day_count = min(max(int(m_last_n_days.group(1)), 1), 31)
            offset_days = -day_count
            inferred = anchor_date + timedelta(days=offset_days)
            return inferred, "relative_day_range", 0.74, f"지난{day_count}일", offset_days

        m_days = self._RELATIVE_N_DAYS_AGO_RE.search(compact)
        if m_days:
            day_count = min(max(int(m_days.group(1)), 1), 31)
            offset_days = -day_count
            inferred = anchor_date + timedelta(days=offset_days)
            return inferred, "relative_day", 0.9, f"{day_count}일전", offset_days

        m_weeks = self._RELATIVE_N_WEEKS_AGO_RE.search(compact)
        if m_weeks:
            week_count = min(max(int(m_weeks.group(1)), 1), 12)
            offset_days = -7 * week_count
            inferred = anchor_date + timedelta(days=offset_days)
            return inferred, "relative_week", 0.86, f"{week_count}주전", offset_days

        m_months = self._RELATIVE_N_MONTHS_AGO_RE.search(compact)
        if m_months:
            month_count = min(max(int(m_months.group(1)), 1), 12)
            inferred = self._shift_months(anchor_date, -month_count)
            offset_days = (inferred - anchor_date).days
            return inferred, "relative_month", 0.84, f"{month_count}개월전", offset_days

        if self._RELATIVE_LAST_MONTH_RE.search(compact):
            inferred = self._shift_months(anchor_date, -1)
            offset_days = (inferred - anchor_date).days
            return inferred, "relative_month", 0.86, "지난달", offset_days

        return None

    def _resolve_survey_date_inference(
        self,
        article: Article,
    ) -> tuple[str | None, str | None, str | None, float | None, ReviewQueueItem | None]:
        full_text = f"{article.title}\n{article.raw_text}"
        published_date = self._parse_date(article.published_at)
        collected_date = self._parse_date(article.collected_at)
        anchor_date = published_date or collected_date
        relative_signal = self._find_relative_date_signal(full_text, anchor_date=anchor_date) if anchor_date else None

        if relative_signal is None:
            if published_date is None:
                return None, "missing", "published_at_missing", 0.0, None
            return published_date.isoformat(), "exact", "published_at_exact", 1.0, None

        inferred, resolution, confidence, signal, offset_days = relative_signal
        if published_date is not None:
            uncertainty = None
            if confidence < 0.8:
                uncertainty = new_review_queue_item(
                    entity_type="article",
                    entity_id=article.id,
                    issue_type="extract_error",
                    stage="extract",
                    error_code="RELATIVE_DATE_UNCERTAIN",
                    error_message=f"relative date inferred with low confidence={confidence:.2f}",
                    source_url=article.url,
                    payload={
                        "date_inference_mode": "relative_published_at",
                        "date_inference_confidence": confidence,
                        "relative_date_policy": self.relative_date_policy,
                        "relative_signal": signal,
                        "relative_offset_days": offset_days,
                        "anchor_source": "published_at",
                        "anchor_date": published_date.isoformat(),
                        "inferred_survey_end_date": inferred.isoformat(),
                        "published_at": article.published_at,
                        "collected_at": article.collected_at,
                        "timezone": self._DATE_INFERENCE_TZ_NAME,
                    },
                )
            return inferred.isoformat(), resolution, "relative_published_at", confidence, uncertainty

        if self.relative_date_policy == self._DATE_POLICY_ALLOW_ESTIMATED and collected_date is not None:
            estimated_confidence = max(0.35, round(confidence - 0.25, 2))
            estimated_notice = new_review_queue_item(
                entity_type="article",
                entity_id=article.id,
                issue_type="extract_error",
                stage="extract",
                error_code="RELATIVE_DATE_ESTIMATED",
                error_message="published_at missing, used collected_at fallback for relative date inference",
                source_url=article.url,
                payload={
                    "date_inference_mode": "estimated_timestamp",
                    "date_inference_confidence": estimated_confidence,
                    "relative_date_policy": self.relative_date_policy,
                    "relative_signal": signal,
                    "relative_offset_days": offset_days,
                    "anchor_source": "collected_at",
                    "anchor_date": collected_date.isoformat(),
                    "inferred_survey_end_date": inferred.isoformat(),
                    "published_at": article.published_at,
                    "collected_at": article.collected_at,
                    "timezone": self._DATE_INFERENCE_TZ_NAME,
                },
            )
            return inferred.isoformat(), "estimated", "estimated_timestamp", estimated_confidence, estimated_notice

        strict_fail_notice = new_review_queue_item(
            entity_type="article",
            entity_id=article.id,
            issue_type="extract_error",
            stage="extract",
            error_code="RELATIVE_DATE_STRICT_FAIL",
            error_message="published_at missing and relative date inference blocked by strict policy",
            source_url=article.url,
            payload={
                "date_inference_mode": "strict_fail_blocked",
                "date_inference_confidence": 0.0,
                "relative_date_policy": self.relative_date_policy,
                "relative_signal": signal,
                "relative_offset_days": offset_days,
                "anchor_source": "none",
                "anchor_date": None,
                "inferred_survey_end_date": None,
                "published_at": article.published_at,
                "collected_at": article.collected_at,
                "timezone": self._DATE_INFERENCE_TZ_NAME,
            },
        )
        return None, "failed", "strict_fail_blocked", 0.0, strict_fail_notice
