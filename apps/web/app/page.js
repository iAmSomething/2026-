import Link from "next/link";

import RegionalMapPanel from "./_components/RegionalMapPanel";
import { formatDate, formatPercent, joinChannels } from "./_components/format";
import { API_BASE, fetchApi } from "./_lib/api";

function SummaryColumn({ title, description, items }) {
  return (
    <article className="panel">
      <header className="panel-header">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
      </header>

      {items.length === 0 ? <div className="empty-state">표시할 데이터가 없습니다.</div> : null}

      <div className="summary-list">
        {items.map((item) => (
          <div key={`${item.option_name}-${item.survey_end_date}`} className="summary-row">
            <div>
              <strong>{item.option_name}</strong>
              <p className="muted-text">
                {item.pollster} · {formatDate(item.survey_end_date)}
              </p>
            </div>
            <div className="summary-value">{formatPercent(item.value_mid)}</div>
            <p className="summary-meta">채널: {joinChannels(item.source_channels)}</p>
          </div>
        ))}
      </div>
    </article>
  );
}

function BigMatchCards({ items }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h3>이 주의 빅매치</h3>
          <p>격차(spread)가 작아 접전인 매치업을 우선 정렬합니다.</p>
        </div>
        <Link href="/search" className="text-link">
          지역 검색으로 이동
        </Link>
      </header>

      {items.length === 0 ? <div className="empty-state">빅매치 데이터가 없습니다.</div> : null}

      <div className="bigmatch-grid">
        {items.map((item) => (
          <Link
            key={item.matchup_id}
            href={`/matchups/${encodeURIComponent(item.matchup_id)}`}
            className="bigmatch-card"
          >
            <p className="bigmatch-office">{item.audience_scope || "지역 조사"}</p>
            <strong>{item.title}</strong>
            <p>대표값 {formatPercent(item.value_mid)}</p>
            <p>조사 종료 {formatDate(item.survey_end_date)}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default async function HomePage() {
  const [summaryRes, mapRes, bigMatchRes] = await Promise.all([
    fetchApi("/api/v1/dashboard/summary"),
    fetchApi("/api/v1/dashboard/map-latest"),
    fetchApi("/api/v1/dashboard/big-matches")
  ]);

  const partyItems = summaryRes.ok && Array.isArray(summaryRes.body?.party_support) ? summaryRes.body.party_support : [];
  const presidentialItems =
    summaryRes.ok && Array.isArray(summaryRes.body?.presidential_approval) ? summaryRes.body.presidential_approval : [];
  const mapItems = mapRes.ok && Array.isArray(mapRes.body?.items) ? mapRes.body.items : [];
  const bigMatchItems = bigMatchRes.ok && Array.isArray(bigMatchRes.body?.items) ? bigMatchRes.body.items : [];

  return (
    <main className="dashboard-root">
      <section className="hero panel">
        <div>
          <p className="kicker">ELECTION 2026</p>
          <h1>전국 여론조사 대시보드</h1>
          <p>
            정당·대통령 요약, 지역별 최신 매치업, 빅매치를 한 화면에서 확인할 수 있습니다.
          </p>
        </div>
        <div className="hero-meta">
          <p>운영 API</p>
          <strong>{API_BASE}</strong>
          <p className="muted-text">데이터는 운영 API 기준 실시간 조회 결과를 사용합니다.</p>
        </div>
      </section>

      {!summaryRes.ok ? (
        <section className="panel error-panel">
          <h3>요약 데이터 로드 실패</h3>
          <p>status: {summaryRes.status}</p>
        </section>
      ) : null}

      <section className="summary-grid">
        <SummaryColumn
          title="최신 정당 지지도"
          description="전국 스코프 기준 최신 조사"
          items={partyItems}
        />
        <SummaryColumn
          title="대통령 지지율"
          description="전국 스코프 기준 최신 조사"
          items={presidentialItems}
        />
      </section>

      {!mapRes.ok ? (
        <section className="panel error-panel">
          <h3>지도 데이터 로드 실패</h3>
          <p>status: {mapRes.status}</p>
        </section>
      ) : (
        <RegionalMapPanel items={mapItems} apiBase={API_BASE} />
      )}

      {!bigMatchRes.ok ? (
        <section className="panel error-panel">
          <h3>빅매치 데이터 로드 실패</h3>
          <p>status: {bigMatchRes.status}</p>
        </section>
      ) : (
        <BigMatchCards items={bigMatchItems} />
      )}
    </main>
  );
}
