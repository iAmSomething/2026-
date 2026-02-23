from pathlib import Path


def test_home_page_contains_quality_panel_keywords() -> None:
    page = Path("apps/web/app/page.js").read_text(encoding="utf-8")
    for keyword in ("운영 품질", "신선도", "공식확정 비율", "검수대기"):
        assert keyword in page
