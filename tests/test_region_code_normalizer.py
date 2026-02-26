import pytest

from app.services.region_code_normalizer import normalize_region_code_input


@pytest.mark.parametrize(
    ("raw", "canonical", "is_code_like", "was_aliased"),
    [
        ("KR-32", "42-000", True, True),
        ("KR-42", "42-000", True, True),
        ("32-000", "42-000", True, True),
        ("32_000", "42-000", True, True),
        ("42000", "42-000", True, True),
        ("42-000", "42-000", True, False),
        ("29-46-000", "29-46-000", True, False),
        ("서울특별시", None, False, False),
        ("", None, False, False),
    ],
)
def test_normalize_region_code_input(raw, canonical, is_code_like, was_aliased):
    normalized = normalize_region_code_input(raw)
    assert normalized.canonical == canonical
    assert normalized.is_code_like is is_code_like
    assert normalized.was_aliased is was_aliased
