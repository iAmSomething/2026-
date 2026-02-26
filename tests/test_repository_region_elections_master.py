from datetime import date

from app.services.repository import PostgresRepository


class _Cursor:
    def __init__(
        self,
        *,
        topology_rows,
        parent_by_child,
        region_rows,
        election_rows,
        matchup_rows,
        poll_meta_rows,
        scenario_children,
    ):
        self.topology_rows = topology_rows
        self.parent_by_child = parent_by_child
        self.region_rows = region_rows
        self.election_rows = election_rows
        self.matchup_rows = matchup_rows
        self.poll_meta_rows = poll_meta_rows
        self.scenario_children = scenario_children
        self._query = ""
        self._params = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def execute(self, query, params=None):
        self._query = query
        self._params = params or ()

    def fetchone(self):
        if "FROM region_topology_versions" in self._query:
            if len(self._params) == 2:
                version_id, mode = self._params
                row = self.topology_rows.get(mode)
                if row and row.get("version_id") == version_id:
                    return row
                return None
            mode = self._params[0]
            return self.topology_rows.get(mode)

        if "FROM region_topology_edges" in self._query and "child_region_code" in self._query:
            version_id, child_region_code = self._params
            parent_region_code = self.parent_by_child.get((version_id, child_region_code))
            return {"parent_region_code": parent_region_code} if parent_region_code else None

        if "FROM regions" in self._query and "WHERE region_code" in self._query:
            region_code = self._params[0]
            return self.region_rows.get(region_code)

        return None

    def fetchall(self):
        if "FROM elections" in self._query:
            region_code = self._params[0]
            return self.election_rows.get(region_code, [])

        if "FROM matchups" in self._query:
            region_code = self._params[0]
            return self.matchup_rows.get(region_code, [])

        if "FROM ranked r" in self._query:
            region_code = self._params[0]
            return self.poll_meta_rows.get(region_code, [])

        if "JOIN regions r ON r.region_code = e.child_region_code" in self._query:
            version_id, parent_region_code = self._params
            return self.scenario_children.get((version_id, parent_region_code), [])

        return []


class _Conn:
    def __init__(
        self,
        *,
        topology_rows,
        parent_by_child,
        region_rows,
        election_rows,
        matchup_rows,
        poll_meta_rows,
        scenario_children,
    ):
        self._cursor = _Cursor(
            topology_rows=topology_rows,
            parent_by_child=parent_by_child,
            region_rows=region_rows,
            election_rows=election_rows,
            matchup_rows=matchup_rows,
            poll_meta_rows=poll_meta_rows,
            scenario_children=scenario_children,
        )

    def cursor(self):
        return self._cursor


def _base_conn(
    *,
    region_rows,
    election_rows=None,
    matchup_rows,
    poll_meta_rows,
    parent_by_child=None,
    scenario_children=None,
):
    return _Conn(
        topology_rows={
            "official": {"version_id": "official-v1", "mode": "official", "status": "effective"},
            "scenario": {
                "version_id": "scenario-gj-jn-merge-v1",
                "mode": "scenario",
                "status": "draft",
            },
        },
        parent_by_child=parent_by_child or {},
        region_rows=region_rows,
        election_rows=election_rows or {},
        matchup_rows=matchup_rows,
        poll_meta_rows=poll_meta_rows,
        scenario_children=scenario_children or {},
    )


def test_region_elections_returns_master_slots_for_sido_even_without_poll_data():
    conn = _base_conn(
        region_rows={
            "32-000": {
                "region_code": "32-000",
                "sido_name": "강원특별자치도",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        },
        matchup_rows={"32-000": []},
        poll_meta_rows={"32-000": []},
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("32-000")

    assert [row["office_type"] for row in rows] == ["광역자치단체장", "광역의회", "교육감"]
    assert [row["title"] for row in rows] == ["강원도지사", "강원도의회", "강원교육감"]
    assert all(row["has_poll_data"] is False for row in rows)
    assert all(row["status"] == "조사 데이터 없음" for row in rows)
    assert all(row["is_fallback"] is True for row in rows)
    assert all(row["source"] == "generated" for row in rows)
    assert all(row["topology"] == "official" for row in rows)


def test_region_elections_official_overrides_29_code_to_sejong_titles():
    conn = _base_conn(
        region_rows={
            "29-000": {
                "region_code": "29-000",
                "sido_name": "광주광역시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        },
        matchup_rows={"29-000": []},
        poll_meta_rows={"29-000": []},
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("29-000")

    assert [row["office_type"] for row in rows] == ["광역자치단체장", "광역의회", "교육감"]
    assert [row["title"] for row in rows] == ["세종시장", "세종시의회", "세종교육감"]
    assert all(row["region_code"] == "29-000" for row in rows)
    assert all(row["topology"] == "official" for row in rows)


def test_region_elections_official_rewrites_legacy_gwangju_title_from_master_rows():
    conn = _base_conn(
        region_rows={
            "29-000": {
                "region_code": "29-000",
                "sido_name": "광주광역시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        },
        election_rows={
            "29-000": [
                {
                    "region_code": "29-000",
                    "office_type": "광역자치단체장",
                    "slot_matchup_id": "master|광역자치단체장|29-000",
                    "title": "광주광역시 광역자치단체장",
                    "source": "master_sync",
                    "has_poll_data": False,
                    "latest_matchup_id": None,
                    "is_active": True,
                }
            ]
        },
        matchup_rows={"29-000": []},
        poll_meta_rows={"29-000": []},
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("29-000")

    assert len(rows) == 1
    assert rows[0]["office_type"] == "광역자치단체장"
    assert rows[0]["title"] == "세종시장"
    assert rows[0]["source"] == "master_sync"


def test_region_elections_official_rewrites_legacy_gwangju_title_from_matchup_rows():
    conn = _base_conn(
        region_rows={
            "29-000": {
                "region_code": "29-000",
                "sido_name": "광주광역시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        },
        matchup_rows={
            "29-000": [
                {
                    "matchup_id": "20260603|광역자치단체장|29-000",
                    "region_code": "29-000",
                    "office_type": "광역자치단체장",
                    "title": "광주광역시 광역자치단체장",
                    "is_active": True,
                    "updated_at": "2026-02-26T10:00:00+00:00",
                }
            ]
        },
        poll_meta_rows={"29-000": []},
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("29-000")
    mayor = next(row for row in rows if row["office_type"] == "광역자치단체장")

    assert mayor["title"] == "세종시장"
    assert mayor["region_code"] == "29-000"
    assert mayor["topology"] == "official"


def test_region_elections_returns_three_metro_slots_for_17_sido_codes_even_if_admin_level_corrupted():
    metro_codes = [f"{idx:02d}-000" for idx in range(11, 28)]
    region_rows = {
        code: {
            "region_code": code,
            "sido_name": f"테스트{code[:2]}광역시",
            "sigungu_name": "전체",
            "admin_level": "sigungu",
        }
        for code in metro_codes
    }

    conn = _base_conn(
        region_rows=region_rows,
        matchup_rows={code: [] for code in metro_codes},
        poll_meta_rows={code: [] for code in metro_codes},
    )
    repo = PostgresRepository(conn)

    for code in metro_codes:
        rows = repo.fetch_region_elections(code)
        assert [row["office_type"] for row in rows] == ["광역자치단체장", "광역의회", "교육감"]


def test_region_elections_adds_sigungu_slots_and_status_metadata():
    conn = _base_conn(
        region_rows={
            "26-710": {
                "region_code": "26-710",
                "sido_name": "부산광역시",
                "sigungu_name": "중구",
                "admin_level": "sigungu",
            }
        },
        matchup_rows={"26-710": []},
        poll_meta_rows={
            "26-710": [
                {
                    "office_type": "기초자치단체장",
                    "has_poll_data": True,
                    "latest_survey_end_date": date(2026, 2, 19),
                    "latest_matchup_id": "20260603|기초자치단체장|26-710",
                    "has_candidate_data": False,
                }
            ]
        },
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("26-710")

    office_types = [row["office_type"] for row in rows]
    assert office_types == ["기초자치단체장", "기초의회"]

    mayor = next(row for row in rows if row["office_type"] == "기초자치단체장")
    assert mayor["has_poll_data"] is True
    assert mayor["has_candidate_data"] is False
    assert mayor["latest_survey_end_date"] == date(2026, 2, 19)
    assert mayor["latest_matchup_id"] == "20260603|기초자치단체장|26-710"
    assert mayor["status"] == "후보 정보 준비중"
    assert all(row["is_fallback"] is True for row in rows)
    assert all(row["source"] == "generated" for row in rows)


def test_region_elections_supports_scenario_topology_merge_slots():
    conn = _base_conn(
        region_rows={
            "29-000": {
                "region_code": "29-000",
                "sido_name": "광주광역시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            },
            "46-000": {
                "region_code": "46-000",
                "sido_name": "전라남도",
                "sigungu_name": "전체",
                "admin_level": "sido",
            },
        },
        matchup_rows={"29-46-000": []},
        poll_meta_rows={"29-46-000": []},
        parent_by_child={
            ("scenario-gj-jn-merge-v1", "29-000"): "29-46-000",
            ("scenario-gj-jn-merge-v1", "46-000"): "29-46-000",
        },
        scenario_children={
            (
                "scenario-gj-jn-merge-v1",
                "29-46-000",
            ): [
                {"sido_name": "광주광역시", "sigungu_name": "전체"},
                {"sido_name": "전라남도", "sigungu_name": "전체"},
            ]
        },
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("29-000", topology="scenario", version_id="scenario-gj-jn-merge-v1")

    assert [row["office_type"] for row in rows] == ["광역자치단체장", "광역의회", "교육감"]
    assert [row["title"] for row in rows] == ["광주·전남 통합시장", "광주·전남 통합시의회", "광주·전남 통합교육감"]
    assert all(row["region_code"] == "29-46-000" for row in rows)
    assert all(row["is_fallback"] is True for row in rows)
    assert all(row["source"] == "generated" for row in rows)
    assert all(row["topology"] == "scenario" for row in rows)
    assert all(row["topology_version_id"] == "scenario-gj-jn-merge-v1" for row in rows)


def test_region_elections_uses_master_rows_when_present():
    conn = _base_conn(
        region_rows={
            "42-000": {
                "region_code": "42-000",
                "sido_name": "강원특별자치도",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        },
        election_rows={
            "42-000": [
                {
                    "region_code": "42-000",
                    "office_type": "광역자치단체장",
                    "slot_matchup_id": "master|광역자치단체장|42-000",
                    "title": "강원도지사",
                    "source": "master_sync",
                    "has_poll_data": False,
                    "latest_matchup_id": None,
                    "is_active": True,
                }
            ]
        },
        matchup_rows={"42-000": []},
        poll_meta_rows={"42-000": []},
    )

    repo = PostgresRepository(conn)
    rows = repo.fetch_region_elections("42-000")

    assert len(rows) == 1
    assert rows[0]["office_type"] == "광역자치단체장"
    assert rows[0]["is_fallback"] is False
    assert rows[0]["source"] == "master_sync"
