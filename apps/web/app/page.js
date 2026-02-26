import Link from "next/link";

import { normalizeRegionParam, parseOnFlag, toScenarioBadge } from "./_components/demoParams";
import RegionalMapPanel from "./_components/RegionalMapPanel";
import { formatDate, formatDateTime, formatPercent, joinChannels } from "./_components/format";
import { API_BASE, fetchApi, isFixtureFallbackAllowed, loadJsonFixture } from "./_lib/api";

// 품질 패널 고정 키워드: 운영 품질 / 신선도 / 공식확정 비율 / 검수대기

function sourceTone(item) {
  const channels = Array.isArray(item?.source_channels) ? item.source_channels : [];
  const source = item?.source_channel || channels[0] || "unknown";
  if (source === "nesdc") return "ok";
  if (channels.includes("article") && channels.includes("nesdc")) return "info";
  if (source === "article") return "warn";
  return "info";
}

function sourceLabel(item) {
  const channels = Array.isArray(item?.source_channels) ? item.source_channels : [];
  const source = item?.source_channel || channels[0] || "unknown";
  if (source === "nesdc") return "출처 NESDC";
  if (channels.includes("article") && channels.includes("nesdc")) return "출처 혼합";
  if (source === "article") return "출처 기사";
  return "출처 미확인";
}

function freshnessTone(hours) {
  const value = Number(hours);
  if (!Number.isFinite(value)) return "info";
  if (value <= 48) return "ok";
  if (value <= 96) return "info";
  return "warn";
}

function freshnessLabel(hours) {
  const value = Number(hours);
  if (!Number.isFinite(value)) return "신선도 -";
  return `신선도 ${value.toFixed(1)}h`;
}

function officialTone(confirmed) {
  return confirmed ? "ok" : "warn";
}

function officialLabel(confirmed) {
  return confirmed ? "공식확정" : "공식확정 대기";
}

function needsReview(item) {
  if (item?.needs_manual_review) return true;
  const freshness = Number(item?.freshness_hours);
  return item?.is_official_confirmed === false && Number.isFinite(freshness) && freshness > 48;
}

function summaryDataSourceTone(dataSource) {
  if (dataSource === "official") return "ok";
  if (dataSource === "mixed") return "info";
  return "warn";
}

function summaryDataSourceLabel(dataSource) {
  if (dataSource === "official") return "요약 출처: official";
  if (dataSource === "mixed") return "요약 출처: mixed";
  return "요약 출처: article";
}

function SummaryColumn({ title, description, items, dataSource }) {
  return (
    <article className="panel">
      <header className="panel-header">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
          <div className="badge-row summary-badges">
            <span className={`state-badge ${summaryDataSourceTone(dataSource)}`}>{summaryDataSourceLabel(dataSource)}</span>
          </div>
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
            <div className="badge-row summary-badges">
              <span className={`state-badge ${sourceTone(item)}`}>{sourceLabel(item)}</span>
              <span className={`state-badge ${officialTone(item.is_official_confirmed)}`}>{officialLabel(item.is_official_confirmed)}</span>
              <span className={`state-badge ${freshnessTone(item.freshness_hours)}`}>{freshnessLabel(item.freshness_hours)}</span>
              {needsReview(item) ? <span className="state-badge warn">검수대기</span> : null}
            </div>
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
            <div className="badge-row summary-badges">
              <span className={`state-badge ${sourceTone(item)}`}>{sourceLabel(item)}</span>
              <span className={`state-badge ${officialTone(item.is_official_confirmed)}`}>{officialLabel(item.is_official_confirmed)}</span>
              <span className={`state-badge ${freshnessTone(item.freshness_hours)}`}>{freshnessLabel(item.freshness_hours)}</span>
              {needsReview(item) ? <span className="state-badge warn">검수대기</span> : null}
            </div>
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

function asNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeRatio(value) {
  const numeric = asNumber(value);
  if (numeric === null) return null;
  if (numeric <= 1) return Math.max(0, numeric);
  if (numeric <= 100) return Math.max(0, numeric / 100);
  return null;
}

function readPath(source, path) {
  return path.reduce((acc, key) => {
    if (acc && typeof acc === "object" && key in acc) return acc[key];
    return undefined;
  }, source);
}

function resolveCompletenessRatio(quality) {
  const direct = normalizeRatio(quality?.completeness_ratio);
  if (direct !== null) return direct;

  const nested = normalizeRatio(readPath(quality, ["completeness", "ratio"]));
  if (nested !== null) return nested;

  const legalScore = normalizeRatio(quality?.legal_completeness_score);
  if (legalScore !== null) return legalScore;

  const fallbackConfirmed = normalizeRatio(quality?.official_confirmed_ratio);
  if (fallbackConfirmed !== null) return fallbackConfirmed;

  return null;
}

function resolveOfficialPendingCount(quality) {
  const direct = asNumber(quality?.official_pending_count);
  if (direct !== null) return direct;
  const nested = asNumber(readPath(quality, ["official_confirmation", "unconfirmed_count"]));
  if (nested !== null) return nested;
  return null;
}

function resolveOfficialPendingRatio(quality) {
  const direct = normalizeRatio(quality?.official_pending_ratio);
  if (direct !== null) return direct;

  const nested = normalizeRatio(readPath(quality, ["official_confirmation", "unconfirmed_ratio"]));
  if (nested !== null) return nested;

  const confirmed = normalizeRatio(quality?.official_confirmed_ratio);
  if (confirmed !== null) return Math.max(0, 1 - confirmed);

  return null;
}

function statusFromFreshnessP90(hours) {
  const value = asNumber(hours);
  if (value === null) return "warn";
  if (value <= 48) return "ok";
  if (value <= 96) return "info";
  return "warn";
}

function statusFromCompleteness(ratio) {
  if (ratio === null) return "warn";
  if (ratio >= 0.95) return "ok";
  if (ratio >= 0.75) return "info";
  return "warn";
}

function statusFromOfficialPending({ count, ratio }) {
  if (ratio !== null) {
    if (ratio <= 0.25) return "ok";
    if (ratio <= 0.4) return "info";
    return "warn";
  }
  if (count !== null) {
    if (count <= 5) return "ok";
    if (count <= 20) return "info";
    return "warn";
  }
  return "warn";
}

function overallStatus(statuses) {
  if (statuses.includes("warn")) return "warn";
  if (statuses.includes("info")) return "info";
  return "ok";
}

function QualityPanel({ quality }) {
  if (!quality) {
    return (
      <section className="panel">
        <header className="panel-header">
          <div>
            <h3>운영 품질 패널 v2</h3>
            <p>실데이터 품질 지표를 불러오지 못했습니다.</p>
          </div>
        </header>
        <div className="empty-state">데이터 없음: 품질 API 응답 대기 중입니다.</div>
      </section>
    );
  }

  const freshnessP90Hours = asNumber(quality?.freshness_p90_hours);
  const completenessRatio = resolveCompletenessRatio(quality);
  const officialPendingCount = resolveOfficialPendingCount(quality);
  const officialPendingRatio = resolveOfficialPendingRatio(quality);
  const articleRatio = normalizeRatio(readPath(quality, ["source_channel_mix", "article_ratio"]));
  const nesdcRatio = normalizeRatio(readPath(quality, ["source_channel_mix", "nesdc_ratio"]));

  const freshnessStatus = statusFromFreshnessP90(freshnessP90Hours);
  const completenessStatus = statusFromCompleteness(completenessRatio);
  const pendingStatus = statusFromOfficialPending({
    count: officialPendingCount,
    ratio: officialPendingRatio
  });
  const overall = overallStatus([freshnessStatus, completenessStatus, pendingStatus]);

  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h3>운영 품질 패널 v2</h3>
          <p>신선도 p90, 완전성(completeness), 공식확정 대기 상태를 운영 기준으로 모니터링합니다.</p>
        </div>
        <div className="badge-row">
          <span className={`state-badge ${overall}`}>전체 {overall === "ok" ? "정상" : overall === "info" ? "주의" : "경고"}</span>
        </div>
      </header>
      <div className="quality-grid">
        <article className={`quality-item ${freshnessStatus}`}>
          <p className="quality-label">신선도 p90</p>
          <strong>{formatHours(freshnessP90Hours)}</strong>
          <p className="quality-copy">최근 관측치 상위 90%의 지연 시간 기준입니다.</p>
        </article>
        <article className={`quality-item ${completenessStatus}`}>
          <p className="quality-label">완전성 (completeness)</p>
          <strong>{completenessRatio === null ? "-" : formatPercent(completenessRatio * 100)}</strong>
          <p className="quality-copy">법정 완전성 우선, 미제공 시 공식확정 비율을 임시 대체값으로 사용합니다.</p>
        </article>
        <article className={`quality-item ${pendingStatus}`}>
          <p className="quality-label">공식확정 대기</p>
          <strong>
            {officialPendingCount !== null
              ? `${officialPendingCount}건`
              : officialPendingRatio !== null
                ? formatPercent(officialPendingRatio * 100)
                : "-"}
          </strong>
          <p className="quality-copy">공식 확정 전 대기 상태 항목 규모입니다.</p>
        </article>
      </div>
      <div className="quality-source-mix">
        <p className="quality-label">실데이터 소스 비중 (기사/NESDC)</p>
        <div className="source-mix-row">
          <span>기사</span>
          <div className="source-meter">
            <span className="source-fill article" style={{ width: `${Math.round((articleRatio ?? 0) * 100)}%` }} />
          </div>
          <strong>{articleRatio === null ? "-" : formatPercent(articleRatio * 100)}</strong>
        </div>
        <div className="source-mix-row">
          <span>NESDC</span>
          <div className="source-meter">
            <span className="source-fill nesdc" style={{ width: `${Math.round((nesdcRatio ?? 0) * 100)}%` }} />
          </div>
          <strong>{nesdcRatio === null ? "-" : formatPercent(nesdcRatio * 100)}</strong>
        </div>
      </div>
      <p className="muted-text quality-footnote">
        기준: generated_at {formatDateTime(quality?.generated_at)} · quality_status {quality?.quality_status || "-"}
      </p>
    </section>
  );
}

export default async function HomePage({ searchParams }) {
  const resolved = await searchParams;
  const scopeMixEnabled = parseOnFlag(resolved?.scope_mix || "");
  const regionScenario = normalizeRegionParam(resolved?.selected_region || "");
  const stateDemo = (resolved?.state_demo || "").toLowerCase().trim();

  const [summaryResRaw, mapRes, bigMatchRes, qualityRes] = await Promise.all([
    fetchApi("/api/v1/dashboard/summary"),
    fetchApi("/api/v1/dashboard/map-latest"),
    fetchApi("/api/v1/dashboard/big-matches"),
    fetchApi("/api/v1/dashboard/quality")
  ]);
  let summaryRes = summaryResRaw;
  if (!summaryRes.ok && isFixtureFallbackAllowed()) {
    const fallbackBody = await loadJsonFixture("mock_fixtures_v0.2/dashboard_summary.json");
    if (fallbackBody) {
      summaryRes = { ok: true, status: 200, body: fallbackBody, url: "fixture://dashboard_summary.json" };
    }
  }

  const summaryDataSource =
    summaryRes.ok && typeof summaryRes.body?.data_source === "string" ? summaryRes.body.data_source : "article";

  const partyItems = summaryRes.ok && Array.isArray(summaryRes.body?.party_support) ? summaryRes.body.party_support : [];
  const presidentJobItems =
    summaryRes.ok && Array.isArray(summaryRes.body?.president_job_approval)
      ? summaryRes.body.president_job_approval
      : summaryRes.ok && Array.isArray(summaryRes.body?.presidential_approval)
        ? summaryRes.body.presidential_approval
        : [];
  const electionFrameItems =
    summaryRes.ok && Array.isArray(summaryRes.body?.election_frame) ? summaryRes.body.election_frame : [];
  const mapItems = mapRes.ok && Array.isArray(mapRes.body?.items) ? mapRes.body.items : [];
  const bigMatchItemsRaw = bigMatchRes.ok && Array.isArray(bigMatchRes.body?.items) ? bigMatchRes.body.items : [];
  const qualityMetrics = qualityRes.ok && qualityRes.body ? qualityRes.body : null;
  const bigMatchItems =
    stateDemo === "review"
      ? bigMatchItemsRaw.map((item, index) =>
          index === 0 ? { ...item, needs_manual_review: true, is_official_confirmed: false, freshness_hours: 168 } : item
        )
      : bigMatchItemsRaw;

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
            정당·대통령 직무평가·선거 성격 요약, 지역별 최신 매치업, 빅매치를 한 화면에서 확인할 수 있습니다.
          </p>
        </div>
        <div className="hero-meta">
          <p>운영 API</p>
          <strong>{API_BASE}</strong>
          <span className="state-badge ok">실데이터 LIVE</span>
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
          dataSource={summaryDataSource}
          items={
            stateDemo === "empty"
              ? []
              : stateDemo === "review"
                ? partyItems.map((item, index) =>
                    index === 0 ? { ...item, needs_manual_review: true, is_official_confirmed: false, freshness_hours: 120 } : item
                  )
                : partyItems
          }
        />
        <SummaryColumn
          title="대통령 직무평가"
          description="전국 스코프 기준 긍정/부정 지표"
          dataSource={summaryDataSource}
          items={
            stateDemo === "empty"
              ? []
              : stateDemo === "review"
                ? presidentJobItems.map((item, index) =>
                    index === 0 ? { ...item, needs_manual_review: true, is_official_confirmed: false, freshness_hours: 120 } : item
                  )
                : presidentJobItems
          }
        />
        <SummaryColumn
          title="선거 성격"
          description="전국 스코프 기준 안정/견제 프레이밍"
          dataSource={summaryDataSource}
          items={
            stateDemo === "empty"
              ? []
              : stateDemo === "review"
                ? electionFrameItems.map((item, index) =>
                    index === 0 ? { ...item, needs_manual_review: true, is_official_confirmed: false, freshness_hours: 120 } : item
                  )
                : electionFrameItems
          }
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
