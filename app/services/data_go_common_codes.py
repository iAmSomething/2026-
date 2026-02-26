from __future__ import annotations

import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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


def _pick(item: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        if key not in item:
            continue
        value = _norm_text(item.get(key))
        if value:
            return value
    return None


def normalize_region_code(value: Any) -> str | None:
    text = _norm_text(value)
    if not text:
        return None

    if re.fullmatch(r"\d{2}-\d{3}", text):
        return text

    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 5:
        digits = digits[:5]
        return f"{digits[:2]}-{digits[2:]}"
    if len(digits) == 2:
        return f"{digits}-000"
    return None


@dataclass(frozen=True)
class DataGoCommonCodeConfig:
    endpoint_url: str
    service_key: str | None
    timeout_sec: float = 6.0
    max_retries: int = 2
    cache_ttl_sec: int = 900
    requests_per_sec: float = 3.0
    num_of_rows: int = 1000


class DataGoCommonCodeService:
    def __init__(self, config: DataGoCommonCodeConfig):
        self.config = config
        self._lock = threading.Lock()
        self._cache: tuple[float, list[dict[str, Any]]] | None = None
        self._next_allowed_at = 0.0

    def is_configured(self) -> bool:
        return bool(self.config.endpoint_url and self.config.service_key)

    def fetch_items(self) -> list[dict[str, Any]]:
        now = time.time()
        with self._lock:
            if self._cache and self._cache[0] > now:
                return self._cache[1]
        items = self._fetch_items_with_retry()
        with self._lock:
            self._cache = (time.time() + max(60, self.config.cache_ttl_sec), items)
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
                time.sleep(min(2.5, 0.4 * (2**attempt)))
        raise RuntimeError(f"common code fetch failed: {last_exc}") from last_exc

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
        }
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


def build_region_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    region_code_keys = [
        "sggCd",
        "signguCd",
        "regionCode",
        "region_code",
        "code",
        "codeId",
        "locCode",
        "ctprvnCd",
        "sdCd",
        "sidoCd",
    ]
    name_keys = ["name", "codeNm", "regionName", "locNm", "ctpvnNm", "sdNm", "sggNm", "signguNm"]
    sido_name_keys = ["sidoName", "sidoNm", "ctprvnNm", "sdNm"]
    sigungu_name_keys = ["sigunguName", "sigunguNm", "sggNm", "signguNm"]
    parent_code_keys = ["parentCode", "parent_region_code", "upperCode", "ctprvnCd", "sdCd", "sidoCd"]
    admin_level_keys = ["adminLevel", "level", "regionLevel", "codeLevel"]

    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        region_code = normalize_region_code(_pick(item, region_code_keys))
        if not region_code:
            continue

        explicit_level = (_pick(item, admin_level_keys) or "").lower()
        if explicit_level in {"sido", "province", "ctprvn"}:
            admin_level = "sido"
        elif explicit_level in {"sigungu", "sgg", "city_county"}:
            admin_level = "sigungu"
        elif region_code.endswith("-000"):
            admin_level = "sido"
        else:
            admin_level = "sigungu"

        generic_name = _pick(item, name_keys)
        sido_name = _pick(item, sido_name_keys)
        sigungu_name = _pick(item, sigungu_name_keys)

        if admin_level == "sido":
            sido_name = sido_name or generic_name
            sigungu_name = "전체"
            parent_region_code = None
        else:
            sigungu_name = sigungu_name or generic_name
            parent_region_code = normalize_region_code(_pick(item, parent_code_keys))
            if not parent_region_code:
                parent_region_code = f"{region_code[:2]}-000"

        if not sido_name and admin_level == "sigungu":
            parent_candidate = f"{region_code[:2]}-000"
            parent_row = merged.get(parent_candidate)
            if parent_row:
                sido_name = parent_row.get("sido_name")

        if not sido_name or not sigungu_name:
            continue

        candidate_row = {
            "region_code": region_code,
            "sido_name": sido_name,
            "sigungu_name": sigungu_name,
            "admin_level": admin_level,
            "parent_region_code": parent_region_code if admin_level == "sigungu" else None,
        }
        existing = merged.get(region_code)
        if not existing:
            merged[region_code] = candidate_row
            continue
        # Keep the richer row if duplicate entries are present.
        if existing.get("sido_name") and existing.get("sigungu_name") and existing.get("admin_level") == admin_level:
            continue
        merged[region_code] = candidate_row

    for row in list(merged.values()):
        if row["admin_level"] != "sigungu":
            continue
        if row.get("sido_name"):
            continue
        parent = row.get("parent_region_code")
        if parent and merged.get(parent):
            row["sido_name"] = merged[parent]["sido_name"]

    return sorted(
        merged.values(),
        key=lambda x: (
            0 if x["admin_level"] == "sido" else 1,
            x["sido_name"],
            x["sigungu_name"],
            x["region_code"],
        ),
    )
