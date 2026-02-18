from __future__ import annotations

from app.services.data_go_candidate import DataGoCandidateConfig, DataGoCandidateService


class _FakeHeaders:
    @staticmethod
    def get_content_charset() -> str:
        return "utf-8"


class _FakeResponse:
    def __init__(self, body: str):
        self._body = body
        self.headers = _FakeHeaders()

    def read(self) -> bytes:
        return self._body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return None


def _xml_with_single_item() -> str:
    return """
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>NORMAL SERVICE.</resultMsg>
  </header>
  <body>
    <items>
      <item>
        <name>정원오</name>
        <jdName>더불어민주당</jdName>
        <gender>남</gender>
        <birthday>19680812</birthday>
        <job>정치인</job>
        <career1>성동구청장</career1>
      </item>
    </items>
  </body>
</response>
""".strip()


def _configured_service(**kwargs) -> DataGoCandidateService:
    defaults = {
        "endpoint_url": "https://apis.data.go.kr/9760000/PofelcddInfoInqireService/getPoelpcddRegistSttusInfoInqire",
        "service_key": "test-key",
        "sg_id": "20240410",
        "sg_typecode": "2",
        "cache_ttl_sec": 120,
        "max_retries": 2,
        "timeout_sec": 1.0,
        "requests_per_sec": 100.0,
        "num_of_rows": 100,
    }
    defaults.update(kwargs)
    cfg = DataGoCandidateConfig(
        **defaults,
    )
    return DataGoCandidateService(cfg)


def test_enrich_candidate_noop_when_not_configured():
    service = DataGoCandidateService(
        DataGoCandidateConfig(endpoint_url="", service_key=None, sg_id=None, sg_typecode=None)
    )
    candidate = {"candidate_id": "cand-jwo", "name_ko": "정원오", "party_name": "원본정당"}
    out = service.enrich_candidate(candidate)
    assert out == candidate


def test_enrich_candidate_merges_public_fields(monkeypatch):
    service = _configured_service()
    monkeypatch.setattr(
        "app.services.data_go_candidate.urlopen",
        lambda *args, **kwargs: _FakeResponse(_xml_with_single_item()),  # noqa: ARG005
    )
    candidate = {
        "candidate_id": "cand-jwo",
        "name_ko": "정원오",
        "party_name": None,
        "gender": None,
        "birth_date": None,
        "job": None,
        "career_summary": None,
    }
    out = service.enrich_candidate(candidate)
    assert out["party_name"] == "더불어민주당"
    assert out["gender"] == "M"
    assert str(out["birth_date"]) == "1968-08-12"
    assert out["job"] == "정치인"
    assert out["career_summary"] == "성동구청장"


def test_fetch_retry_and_cache(monkeypatch):
    service = _configured_service()
    state = {"calls": 0}

    def fake_urlopen(*args, **kwargs):  # noqa: ANN002, ARG001
        state["calls"] += 1
        if state["calls"] == 1:
            raise TimeoutError("first timeout")
        return _FakeResponse(_xml_with_single_item())

    monkeypatch.setattr("app.services.data_go_candidate.urlopen", fake_urlopen)

    candidate = {"candidate_id": "cand-jwo", "name_ko": "정원오"}
    out1 = service.enrich_candidate(candidate)
    out2 = service.enrich_candidate(candidate)
    assert out1["name_ko"] == "정원오"
    assert out2["name_ko"] == "정원오"
    assert state["calls"] == 2


def test_enrich_candidate_graceful_fallback_on_error(monkeypatch):
    service = _configured_service(max_retries=1)
    monkeypatch.setattr("app.services.data_go_candidate.urlopen", lambda *args, **kwargs: 1 / 0)  # noqa: ARG005

    candidate = {"candidate_id": "cand-jwo", "name_ko": "정원오", "party_name": "원본정당"}
    out = service.enrich_candidate(candidate)
    assert out["party_name"] == "원본정당"


def test_info03_error_is_not_retried(monkeypatch):
    service = _configured_service(max_retries=3)
    state = {"calls": 0}
    error_xml = """
<response>
  <header>
    <resultCode>INFO-03</resultCode>
    <resultMsg>데이터 정보가 없습니다.</resultMsg>
  </header>
</response>
""".strip()

    def fake_urlopen(*args, **kwargs):  # noqa: ANN002, ARG001
        state["calls"] += 1
        return _FakeResponse(error_xml)

    monkeypatch.setattr("app.services.data_go_candidate.urlopen", fake_urlopen)
    candidate = {"candidate_id": "cand-jwo", "name_ko": "정원오", "party_name": "원본정당"}
    out = service.enrich_candidate(candidate)
    assert out["party_name"] == "원본정당"
    assert state["calls"] == 1
