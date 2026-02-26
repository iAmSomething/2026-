import Link from "next/link";

import { normalizeDemoQuery } from "../_components/demoParams";
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
  const rawQ = (resolved?.q || "").trim();
  const demoQueryParam = (resolved?.demo_query || "").trim();
  const topology = (resolved?.topology || "official").trim().toLowerCase() === "scenario" ? "scenario" : "official";
  const versionId = (resolved?.version_id || "").trim();

  const queryFromScenario = rawQ || demoQueryParam;
  const normalizedQuery = normalizeDemoQuery(queryFromScenario);

  const selectedRegion = resolved?.region || "";
  const selectedOffice = resolved?.office || "all";

  const regionsRes = normalizedQuery.normalized
    ? await fetchApi(`/api/v1/regions/search?q=${encodeURIComponent(normalizedQuery.normalized)}`)
    : { ok: true, body: [] };

  const regions = regionsRes.ok && Array.isArray(regionsRes.body) ? regionsRes.body : [];
  const regionCode = selectedRegion || regions[0]?.region_code || "";
  const electionQuery = new URLSearchParams({ topology });
  if (versionId) electionQuery.set("version_id", versionId);

  const electionsRes = regionCode
    ? await fetchApi(`/api/v1/regions/${encodeURIComponent(regionCode)}/elections?${electionQuery.toString()}`)
    : { ok: true, body: [] };
  const elections = electionsRes.ok && Array.isArray(electionsRes.body) ? electionsRes.body : [];

  const filteredElections =
    selectedOffice === "all" ? elections : elections.filter((election) => election.office_type === selectedOffice);

  const scenarioFixed = Boolean(demoQueryParam);
  const isScenarioEmptyCase = demoQueryParam === "없는지역명";

  const scenarioBaseParams = {
    demo_query: demoQueryParam,
    topology,
    version_id: versionId
  };
  const topologyParams = {
    topology,
    version_id: versionId
  };

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

        {scenarioFixed ? (
          <div className="param-callout">
            baseline demo_query 적용: <strong>{demoQueryParam}</strong>
            {normalizedQuery.corrected ? (
              <span>
                {" -> 자동 보정 "}
                <strong>{normalizedQuery.normalized}</strong>
              </span>
            ) : null}
          </div>
        ) : null}

        <form method="GET" className="search-form">
          <input
            name="q"
            defaultValue={rawQ || demoQueryParam}
            placeholder="예: 서울 강남구, 경기 시흥시"
            aria-label="지역 검색"
            readOnly={scenarioFixed}
          />
          {demoQueryParam ? <input type="hidden" name="demo_query" value={demoQueryParam} /> : null}
          {topology !== "official" ? <input type="hidden" name="topology" value={topology} /> : null}
          {versionId ? <input type="hidden" name="version_id" value={versionId} /> : null}
          <button type="submit">검색</button>
        </form>

        {normalizedQuery.normalized && !regionsRes.ok ? <div className="error-chip">검색 API 오류: {regionsRes.status}</div> : null}

        {normalizedQuery.normalized && regionsRes.ok ? (
          <div className="search-layout">
            <section className="panel inset-panel">
              <h3>검색 결과 ({regions.length})</h3>
              {regions.length === 0 ? <div className="empty-state">검색 결과가 없습니다.</div> : null}
              {isScenarioEmptyCase && regions.length === 0 ? (
                <div className="empty-actions">
                  <p>대체 액션</p>
                  <div className="empty-actions-links">
                    <Link href="/search?q=서울">예시 검색어 적용</Link>
                    <Link href="/">최근 업데이트</Link>
                  </div>
                </div>
              ) : null}
              <ul className="region-result-list">
                {regions.map((region) => {
                  const href = buildQueryString({
                    ...(scenarioFixed ? scenarioBaseParams : {}),
                    ...(!scenarioFixed ? topologyParams : {}),
                    q: rawQ || normalizedQuery.input,
                    region: region.region_code,
                    office: selectedOffice === "all" ? "" : selectedOffice
                  });
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
                  href={`/search${buildQueryString({
                    ...(scenarioFixed ? scenarioBaseParams : {}),
                    ...(!scenarioFixed ? topologyParams : {}),
                    q: rawQ || normalizedQuery.input,
                    region: regionCode
                  })}`}
                  className={selectedOffice === "all" ? "tab active" : "tab"}
                >
                  전체
                </Link>
                {OFFICE_TABS.map((officeType) => (
                  <Link
                    key={officeType}
                    href={`/search${buildQueryString({
                      ...(scenarioFixed ? scenarioBaseParams : {}),
                      ...(!scenarioFixed ? topologyParams : {}),
                      q: rawQ || normalizedQuery.input,
                      region: regionCode,
                      office: officeType
                    })}`}
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
                  {filteredElections.map((election) => {
                    const navigationMatchupId =
                      election.latest_matchup_id || (election.is_placeholder ? "" : election.matchup_id);
                    const canNavigate = Boolean(navigationMatchupId);
                    const statusText =
                      election.status ||
                      (election.has_poll_data ? "데이터 준비 완료" : "조사 데이터 없음");

                    return (
                      <li key={election.matchup_id}>
                        {canNavigate ? (
                          <Link href={`/matchups/${encodeURIComponent(navigationMatchupId)}`}>
                            <span>{election.office_type}</span>
                            <strong>{election.title}</strong>
                            <span>{statusText}</span>
                            <span>{election.latest_survey_end_date || "-"}</span>
                          </Link>
                        ) : (
                          <div>
                            <span>{election.office_type}</span>
                            <strong>{election.title}</strong>
                            <span>{statusText}</span>
                            <span>매치업 준비중</span>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : null}
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}
