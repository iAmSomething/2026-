import Link from "next/link";

import { formatDate } from "../_components/format";
import { fetchApi } from "../_lib/api";

const OFFICE_TABS = [
  "광역자치단체장",
  "광역의회",
  "교육감",
  "기초자치단체장",
  "기초의회",
  "재보궐"
];

function buildQueryString(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

export default async function SearchPage({ searchParams }) {
  const resolved = await searchParams;
  const q = (resolved?.q || "").trim();
  const selectedRegion = resolved?.region || "";
  const selectedOffice = resolved?.office || "all";

  const regionsRes = q ? await fetchApi(`/api/v1/regions/search?q=${encodeURIComponent(q)}`) : { ok: true, body: [] };
  const regions = regionsRes.ok && Array.isArray(regionsRes.body) ? regionsRes.body : [];
  const regionCode = selectedRegion || regions[0]?.region_code || "";

  const electionsRes = regionCode ? await fetchApi(`/api/v1/regions/${encodeURIComponent(regionCode)}/elections`) : { ok: true, body: [] };
  const elections = electionsRes.ok && Array.isArray(electionsRes.body) ? electionsRes.body : [];

  const filteredElections =
    selectedOffice === "all" ? elections : elections.filter((election) => election.office_type === selectedOffice);

  return (
    <main className="search-root">
      <section className="panel">
        <header className="panel-header">
          <div>
            <h1>지역 검색</h1>
            <p>기초자치단체 단위로 검색하고 선거 타입별 매치업으로 이동합니다.</p>
          </div>
          <Link href="/" className="text-link">
            대시보드로
          </Link>
        </header>

        <form method="GET" className="search-form">
          <input name="q" defaultValue={q} placeholder="예: 서울 강남구, 경기 시흥시" aria-label="지역 검색" />
          <button type="submit">검색</button>
        </form>

        {q && !regionsRes.ok ? <div className="error-chip">검색 API 오류: {regionsRes.status}</div> : null}

        {q && regionsRes.ok ? (
          <div className="search-layout">
            <section className="panel inset-panel">
              <h3>검색 결과 ({regions.length})</h3>
              {regions.length === 0 ? <div className="empty-state">검색 결과가 없습니다.</div> : null}
              <ul className="region-result-list">
                {regions.map((region) => {
                  const href = buildQueryString({ q, region: region.region_code, office: selectedOffice === "all" ? "" : selectedOffice });
                  const active = region.region_code === regionCode;
                  return (
                    <li key={region.region_code}>
                      <Link className={active ? "active" : ""} href={`/search${href}`}>
                        <strong>{region.sido_name}</strong>
                        <span>{region.sigungu_name}</span>
                        <span>{region.region_code}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="panel inset-panel">
              <h3>선거 타입</h3>
              <div className="tab-row">
                <Link
                  href={`/search${buildQueryString({ q, region: regionCode })}`}
                  className={selectedOffice === "all" ? "tab active" : "tab"}
                >
                  전체
                </Link>
                {OFFICE_TABS.map((officeType) => (
                  <Link
                    key={officeType}
                    href={`/search${buildQueryString({ q, region: regionCode, office: officeType })}`}
                    className={selectedOffice === officeType ? "tab active" : "tab"}
                  >
                    {officeType}
                  </Link>
                ))}
              </div>

              {!electionsRes.ok ? <div className="error-chip">선거 목록 API 오류: {electionsRes.status}</div> : null}

              {electionsRes.ok && filteredElections.length === 0 ? <div className="empty-state">조건에 맞는 선거가 없습니다.</div> : null}

              {electionsRes.ok && filteredElections.length > 0 ? (
                <ul className="election-list full">
                  {filteredElections.map((election) => (
                    <li key={election.matchup_id}>
                      <Link href={`/matchups/${encodeURIComponent(election.matchup_id)}`}>
                        <span>{election.office_type}</span>
                        <strong>{election.title}</strong>
                        <span>{election.is_active ? "활성" : "비활성"}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}
