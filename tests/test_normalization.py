from app.services.normalization import normalize_percentage


def test_normalize_range_value():
    normalized = normalize_percentage("53~55%")
    assert normalized.value_min == 53.0
    assert normalized.value_max == 55.0
    assert normalized.value_mid == 54.0
    assert normalized.is_missing is False


def test_normalize_missing_value():
    normalized = normalize_percentage("언급 없음")
    assert normalized.value_min is None
    assert normalized.value_max is None
    assert normalized.value_mid is None
    assert normalized.is_missing is True
