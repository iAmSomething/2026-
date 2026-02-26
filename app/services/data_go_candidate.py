from __future__ import annotations

import json
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import urlopen


def _append_params(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    query = parsed.query
    extra = urlencode(params)
    query = f"{query}&{extra}" if query else extra
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))


def _norm_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _norm_name(value: Any) -> str:
    text = _norm_text(value) or ""
    return text.replace(" ", "").replace("·", "").replace(".", "").lower()


def _parse_date(value: Any) -> date | None:
    text = (_norm_text(value) or "").replace(".", "-").replace("/", "-")
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        text = f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _normalize_gender(value: Any) -> str | None:
    text = (_norm_text(value) or "").lower()
    if not text:
        return None
    if text in {"m", "male", "남", "남자"}:
        return "M"
    if text in {"f", "female", "여", "여자"}:
        return "F"
    return _norm_text(value)


@dataclass(frozen=True)
class DataGoCandidateConfig:
    endpoint_url: str
    service_key: str | None
    sg_id: str | None
    sg_typecode: str | None
    sd_name: str | None = None
    sgg_name: str | None = None
    timeout_sec: float = 4.0
    max_retries: int = 2
    cache_ttl_sec: int = 300
    requests_per_sec: float = 5.0
    num_of_rows: int = 300


class DataGoCandidateService:
    def __init__(self, config: DataGoCandidateConfig):
        self.config = config
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._next_allowed_at = 0.0

    def enrich_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        merged = dict(candidate)
        if not self.is_configured():
            return merged

        try:
            items = self.fetch_items()
        except Exception:  # noqa: BLE001
            return merged

        item = self._match_item(items, merged)
        if not item:
            return merged

        public_party = _norm_text(item.get("jdName"))
        public_gender = _normalize_gender(item.get("gender"))
        public_birth_date = _parse_date(item.get("birthday"))
        public_job = _norm_text(item.get("job"))
        public_career = " / ".join(x for x in [_norm_text(item.get("career1")), _norm_text(item.get("career2"))] if x) or None

        if public_party:
            merged["party_name"] = public_party
        if public_gender:
            merged["gender"] = public_gender
        if public_birth_date:
            merged["birth_date"] = public_birth_date
        if public_job:
            merged["job"] = public_job
        if public_career and not _norm_text(merged.get("career_summary")):
            merged["career_summary"] = public_career
        return merged

    def verify_candidate(
        self,
        *,
        candidate_name: str | None,
        party_name: str | None = None,
    ) -> tuple[bool, float]:
        if not self.is_configured():
            return False, 0.0
        if not _norm_name(candidate_name):
            return False, 0.0

        try:
            items = self.fetch_items()
        except Exception:  # noqa: BLE001
            return False, 0.0

        matched = self._match_item(
            items,
            {
                "name_ko": candidate_name,
                "party_name": party_name,
            },
        )
        if not matched:
            return False, 0.0

        target_party = _norm_name(party_name)
        matched_party = _norm_name(matched.get("jdName"))
        if target_party and matched_party and target_party == matched_party:
            return True, 0.98
        if target_party and matched_party and target_party != matched_party:
            return True, 0.82
        return True, 0.9

    def is_configured(self) -> bool:
        cfg = self.config
        return bool(cfg.endpoint_url and cfg.service_key and cfg.sg_id and cfg.sg_typecode)

    def fetch_items(self) -> list[dict[str, Any]]:
        cache_key = "|".join(
            [
                self.config.sg_id or "",
                self.config.sg_typecode or "",
                self.config.sd_name or "",
                self.config.sgg_name or "",
                str(self.config.num_of_rows),
            ]
        )
        now = time.time()
        with self._lock:
            hit = self._cache.get(cache_key)
            if hit and hit[0] > now:
                return hit[1]

        items = self._fetch_items_with_retry()
        with self._lock:
            self._cache[cache_key] = (time.time() + max(1, self.config.cache_ttl_sec), items)
        return items

    def _fetch_items_with_retry(self) -> list[dict[str, Any]]:
        attempts = max(1, self.config.max_retries + 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._fetch_once()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt + 1 >= attempts or not self._is_retryable(exc):
                    break
                time.sleep(min(2.0, 0.35 * (2**attempt)))
        raise RuntimeError(f"data.go candidate fetch failed: {last_exc}") from last_exc

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        msg = str(exc).lower()
        if "http error 5" in msg or "timed out" in msg or "temporary failure" in msg:
            return True
        return isinstance(exc, TimeoutError)

    def _fetch_once(self) -> list[dict[str, Any]]:
        self._wait_for_rate_limit()
        params = {
            "serviceKey": self.config.service_key or "",
            "pageNo": "1",
            "numOfRows": str(self.config.num_of_rows),
            "sgId": self.config.sg_id or "",
            "sgTypecode": self.config.sg_typecode or "",
        }
        if self.config.sd_name:
            params["sdName"] = self.config.sd_name
        if self.config.sgg_name:
            params["sggName"] = self.config.sgg_name

        url = _append_params(self.config.endpoint_url, params)
        with urlopen(url, timeout=self.config.timeout_sec) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw_text = resp.read().decode(charset, "replace")
        return self._parse_items(raw_text)

    def _wait_for_rate_limit(self) -> None:
        min_interval = 1.0 / max(self.config.requests_per_sec, 0.1)
        with self._lock:
            now = time.monotonic()
            wait_for = max(0.0, self._next_allowed_at - now)
            self._next_allowed_at = max(now, self._next_allowed_at) + min_interval
        if wait_for > 0:
            time.sleep(wait_for)

    def _parse_items(self, raw_text: str) -> list[dict[str, Any]]:
        text = raw_text.lstrip()
        if text.startswith("{") or text.startswith("["):
            return self._parse_json_items(raw_text)
        return self._parse_xml_items(raw_text)

    def _parse_xml_items(self, raw_text: str) -> list[dict[str, Any]]:
        root = ET.fromstring(raw_text)
        result_code = _norm_text(root.findtext(".//header/resultCode")) or _norm_text(root.findtext(".//resultCode"))
        result_msg = _norm_text(root.findtext(".//header/resultMsg")) or _norm_text(root.findtext(".//resultMsg"))
        if result_code and result_code not in {"00", "INFO-00"}:
            raise RuntimeError(f"data.go response error: {result_code} {result_msg or ''}".strip())

        items: list[dict[str, Any]] = []
        for elem in root.findall(".//item"):
            row: dict[str, Any] = {}
            for child in list(elem):
                if child.text is not None:
                    row[child.tag] = child.text.strip()
            if row:
                items.append(row)
        return items

    def _parse_json_items(self, raw_text: str) -> list[dict[str, Any]]:
        payload = json.loads(raw_text)
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if not isinstance(payload, dict):
            return []

        header = payload.get("response", {}).get("header", {})
        if isinstance(header, dict):
            result_code = _norm_text(header.get("resultCode"))
            result_msg = _norm_text(header.get("resultMsg"))
            if result_code and result_code not in {"00", "INFO-00"}:
                raise RuntimeError(f"data.go response error: {result_code} {result_msg or ''}".strip())

        cur: Any = payload
        for key in ("response", "body", "items"):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
        if isinstance(cur, dict) and "item" in cur:
            cur = cur["item"]
        if isinstance(cur, list):
            return [x for x in cur if isinstance(x, dict)]
        if isinstance(cur, dict):
            return [cur]
        return []

    def _match_item(self, items: list[dict[str, Any]], candidate: dict[str, Any]) -> dict[str, Any] | None:
        target_name = _norm_name(candidate.get("name_ko"))
        if not target_name:
            return None
        target_party = _norm_name(candidate.get("party_name"))

        for item in items:
            if _norm_name(item.get("name")) == target_name and (
                not target_party or _norm_name(item.get("jdName")) == target_party
            ):
                return item
        for item in items:
            if _norm_name(item.get("name")) == target_name:
                return item
        return None
