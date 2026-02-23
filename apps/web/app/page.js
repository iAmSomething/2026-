import Link from "next/link";

import { normalizeRegionParam, parseOnFlag, toScenarioBadge } from "./_components/demoParams";
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

function formatHours(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(1)}h`;
}

function QualityPanel({ quality }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h3>운영 품질 패널</h3>
          <p>신선도/공식확정 비율/검수대기 지표를 운영 기준으로 모니터링합니다.</p>
        </div>
      </header>
      <div className="quality-grid">
        <article className="quality-item">
          <p className="quality-label">운영 품질</p>
          <strong>{quality?.quality_status || "-"}</strong>
        </article>
        <article className="quality-item">
          <p className="quality-label">신선도</p>
          <strong>
            P50 {formatHours(quality?.freshness_p50_hours)} / P90 {formatHours(quality?.freshness_p90_hours)}
          </strong>
        </article>
        <article className="quality-item">
          <p className="quality-label">공식확정 비율</p>
          <strong>{formatPercent((quality?.official_confirmed_ratio ?? 0) * 100)}</strong>
        </article>
        <article className="quality-item">
          <p className="quality-label">검수대기</p>
          <strong>{quality?.needs_manual_review_count ?? 0}건</strong>
        </article>
      </div>
    </section>
  );
}

export default async function HomePage({ searchParams }) {
  const resolved = await searchParams;
  const scopeMixEnabled = parseOnFlag(resolved?.scope_mix || "");
  const regionScenario = normalizeRegionParam(resolved?.selected_region || "");

  const [summaryRes, mapRes, bigMatchRes, qualityRes] = await Promise.all([
    fetchApi("/api/v1/dashboard/summary"),
    fetchApi("/api/v1/dashboard/map-latest"),
    fetchApi("/api/v1/dashboard/big-matches"),
    fetchApi("/api/v1/dashboard/quality")
  ]);

  const partyItems = summaryRes.ok && Array.isArray(summaryRes.body?.party_support) ? summaryRes.body.party_support : [];
  const presidentialItems =
    summaryRes.ok && Array.isArray(summaryRes.body?.presidential_approval) ? summaryRes.body.presidential_approval : [];
  const mapItems = mapRes.ok && Array.isArray(mapRes.body?.items) ? mapRes.body.items : [];
  const bigMatchItems = bigMatchRes.ok && Array.isArray(bigMatchRes.body?.items) ? bigMatchRes.body.items : [];
  const qualityMetrics = qualityRes.ok && qualityRes.body ? qualityRes.body : null;

  const scenarioBadges = [];
  if (scopeMixEnabled) {
    scenarioBadges.push(toScenarioBadge("scope_mix=1", "warn"));
  }
  if (regionScenario.input) {
    scenarioBadges.push(
      toScenarioBadge(
        `selected_region=${regionScenario.input}${regionScenario.corrected ? ` -> ${regionScenario.normalized}` : ""}`,
        "info"
      )
    );
  }

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

      {scenarioBadges.length > 0 ? (
        <section className="panel scenario-panel">
          <div className="badge-row">
            {scenarioBadges.map((badge) => (
              <span key={badge.text} className={`state-badge ${badge.tone}`}>
                {badge.text}
              </span>
            ))}
          </div>
          {scopeMixEnabled ? (
            <p className="scenario-copy">스코프 혼재 경고: 전국/지역 스코프 데이터가 동시에 노출될 수 있는 baseline 시나리오입니다.</p>
          ) : null}
        </section>
      ) : null}

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
        <RegionalMapPanel
          items={mapItems}
          apiBase={API_BASE}
          initialSelectedRegionCode={regionScenario.normalized}
          selectedRegionHint={regionScenario.input}
        />
      )}

      {!bigMatchRes.ok ? (
        <section className="panel error-panel">
          <h3>빅매치 데이터 로드 실패</h3>
          <p>status: {bigMatchRes.status}</p>
        </section>
      ) : (
        <BigMatchCards items={bigMatchItems} />
      )}

      {!qualityRes.ok ? (
        <section className="panel error-panel">
          <h3>품질 데이터 로드 실패</h3>
          <p>status: {qualityRes.status}</p>
        </section>
      ) : null}
      <QualityPanel quality={qualityMetrics} />
    </main>
  );
}
