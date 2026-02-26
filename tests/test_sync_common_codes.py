from app.services.data_go_common_codes import (
    DataGoCommonCodeConfig,
    DataGoCommonCodeService,
    build_region_rows,
    normalize_region_code,
)


def test_normalize_region_code_accepts_major_formats():
    assert normalize_region_code("11-110") == "11-110"
    assert normalize_region_code("11110") == "11-110"
    assert normalize_region_code("11") == "11-000"
    assert normalize_region_code("  26-710 ") == "26-710"
    assert normalize_region_code("n/a") is None


def test_build_region_rows_parses_sido_and_sigungu_with_parent_link():
    rows = build_region_rows(
        [
            {"ctprvnCd": "11", "ctprvnNm": "서울특별시"},
            {"sdCd": "26", "sdNm": "부산광역시"},
            {"sggCd": "11110", "sggNm": "종로구", "sdCd": "11"},
            {"sggCd": "26710", "sggNm": "중구", "sdCd": "26"},
        ]
    )

    as_map = {row["region_code"]: row for row in rows}
    assert as_map["11-000"]["admin_level"] == "sido"
    assert as_map["11-000"]["sido_name"] == "서울특별시"
    assert as_map["11-000"]["sigungu_name"] == "전체"
    assert as_map["11-110"]["admin_level"] == "sigungu"
    assert as_map["11-110"]["sido_name"] == "서울특별시"
    assert as_map["11-110"]["sigungu_name"] == "종로구"
    assert as_map["11-110"]["parent_region_code"] == "11-000"
    assert as_map["26-710"]["sido_name"] == "부산광역시"
    assert as_map["26-710"]["parent_region_code"] == "26-000"


def test_service_fetch_items_uses_total_count_for_pagination():
    class _FakeService(DataGoCommonCodeService):
        def __init__(self):
            super().__init__(
                DataGoCommonCodeConfig(
                    endpoint_url="https://example.com/api",
                    service_key="k",
                    num_of_rows=2,
                )
            )
            self.calls: list[int] = []

        def _wait_for_rate_limit(self) -> None:
            return None

        def _fetch_once(self, *, page_no: int):  # type: ignore[override]
            self.calls.append(page_no)
            if page_no == 1:
                return ([{"regionCode": "11-000"}, {"regionCode": "26-000"}], 3)
            if page_no == 2:
                return ([{"regionCode": "11-110"}], 3)
            return ([], 3)

    service = _FakeService()
    out = service.fetch_items()

    assert service.calls == [1, 2]
    assert len(out) == 3


def test_parse_xml_items_reads_total_count():
    service = DataGoCommonCodeService(
        DataGoCommonCodeConfig(
            endpoint_url="https://example.com/api",
            service_key="k",
        )
    )
    xml = """
    <response>
      <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
      <body>
        <totalCount>2</totalCount>
        <items>
          <item><ctprvnCd>11</ctprvnCd><ctprvnNm>서울특별시</ctprvnNm></item>
          <item><ctprvnCd>26</ctprvnCd><ctprvnNm>부산광역시</ctprvnNm></item>
        </items>
      </body>
    </response>
    """
    items, total_count = service._parse_xml_items(xml)

    assert len(items) == 2
    assert total_count == 2
