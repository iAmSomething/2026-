from app.services.data_go_common_codes import build_region_rows, normalize_region_code


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
