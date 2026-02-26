from datetime import date

from app.services.repository import PostgresRepository


class _Cursor:
    def __init__(self, *, region_row, election_rows, matchup_rows, poll_meta_rows):
        self._region_row = region_row
        self._election_rows = election_rows
        self._matchup_rows = matchup_rows
        self._poll_meta_rows = poll_meta_rows
        self._step = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def execute(self, query, params=None):  # noqa: ARG002
        return None

    def fetchone(self):
        if self._step == 0:
            self._step += 1
            return self._region_row
        return None

    def fetchall(self):
        if self._step == 1:
            self._step += 1
            return self._election_rows
        if self._step == 2:
            self._step += 1
            return self._matchup_rows
        if self._step == 3:
            self._step += 1
            return self._poll_meta_rows
        return []


class _Conn:
    def __init__(self, *, region_row, election_rows, matchup_rows, poll_meta_rows):
        self._cursor = _Cursor(
            region_row=region_row,
            election_rows=election_rows,
            matchup_rows=matchup_rows,
            poll_meta_rows=poll_meta_rows,
        )

    def cursor(self):
        return self._cursor


def test_region_elections_returns_master_slots_for_sido_even_without_poll_data():
    conn = _Conn(
        region_row={
            "region_code": "32-000",
            "sido_name": "강원특별자치도",
            "sigungu_name": "전체",
            "admin_level": "sido",
        },
        election_rows=[],
        matchup_rows=[],
        poll_meta_rows=[],
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("32-000")

    assert [row["office_type"] for row in rows] == ["광역자치단체장", "광역의회", "교육감"]
    assert [row["title"] for row in rows] == ["강원도지사", "강원도의회", "강원교육감"]
    assert all(row["has_poll_data"] is False for row in rows)
    assert all(row["status"] == "조사 데이터 없음" for row in rows)


def test_region_elections_adds_sigungu_slots_and_status_metadata():
    conn = _Conn(
        region_row={
            "region_code": "26-710",
            "sido_name": "부산광역시",
            "sigungu_name": "중구",
            "admin_level": "sigungu",
        },
        election_rows=[],
        matchup_rows=[],
        poll_meta_rows=[
            {
                "office_type": "기초자치단체장",
                "has_poll_data": True,
                "latest_survey_end_date": date(2026, 2, 19),
                "latest_matchup_id": "20260603|기초자치단체장|26-710",
                "has_candidate_data": False,
            }
        ],
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("26-710")

    office_types = [row["office_type"] for row in rows]
    assert office_types[:5] == ["광역자치단체장", "광역의회", "교육감", "기초자치단체장", "기초의회"]

    mayor = next(row for row in rows if row["office_type"] == "기초자치단체장")
    assert mayor["has_poll_data"] is True
    assert mayor["has_candidate_data"] is False
    assert mayor["latest_survey_end_date"] == date(2026, 2, 19)
    assert mayor["latest_matchup_id"] == "20260603|기초자치단체장|26-710"
    assert mayor["status"] == "후보 정보 준비중"
