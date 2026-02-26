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

function qualitySignalTone(item) {
  const freshness = Number(item?.freshness_hours);
  if (needsReview(item)) return "warn";
  if (item?.is_official_confirmed === true && Number.isFinite(freshness) && freshness <= 48) return "ok";
  if (item?.is_official_confirmed === false && Number.isFinite(freshness) && freshness > 96) return "warn";
  return "info";
}

function qualitySignalLabel(item) {
  if (needsReview(item)) return "품질 검수대기";
  if (item?.is_official_confirmed === true) return "품질 확인됨";
  return "품질 확인중";
}

function qualitySignalHelp(item) {
  if (needsReview(item)) return "수동 검수 큐에 포함된 항목입니다.";
  if (item?.is_official_confirmed === true) return "공식 확정되었고 품질 기준을 충족한 항목입니다.";
  return "공식 확정 전 또는 신선도 경계 상태로 추가 확인이 필요합니다.";
}

function sourceHelp(item) {
  const channels = Array.isArray(item?.source_channels) ? item.source_channels : [];
  if (channels.includes("article") && channels.includes("nesdc")) {
    return "기사와 NESDC 소스를 함께 사용한 혼합 소스입니다.";
  }
  if (item?.source_channel === "nesdc" || channels[0] === "nesdc") {
    return "중앙선관위/NESDC 기준 소스입니다.";
  }
  if (item?.source_channel === "article" || channels[0] === "article") {
    return "기사 기반 추정 소스입니다.";
  }
  return "출처 채널 정보가 명확하지 않습니다.";
}

function freshnessHelp(hours) {
  const value = Number(hours);
  if (!Number.isFinite(value)) return "신선도 데이터를 계산할 수 없습니다.";
  if (value <= 48) return "최근 48시간 내 관측입니다.";
  if (value <= 96) return "48시간 초과 관측으로 주의가 필요합니다.";
  return "96시간 초과 관측으로 검수가 필요한 상태입니다.";
}

function officialHelp(confirmed) {
  return confirmed ? "공식 출처로 확정된 상태입니다." : "공식 확정 대기 상태입니다.";
}

function prioritizedBadges(item) {
  return [
    {
      key: "quality",
      tone: qualitySignalTone(item),
      text: qualitySignalLabel(item),
      help: qualitySignalHelp(item),
      optional: false
    },
    {
      key: "source",
      tone: sourceTone(item),
      text: sourceLabel(item),
      help: sourceHelp(item),
      optional: false
    },
    {
      key: "freshness",
      tone: freshnessTone(item),
      text: freshnessLabel(item),
      help: freshnessHelp(item?.freshness_hours),
      optional: false
    },
    {
      key: "official",
      tone: officialTone(item?.is_official_confirmed),
      text: officialLabel(item?.is_official_confirmed),
      help: officialHelp(item?.is_official_confirmed),
      optional: true
    }
  ];
}

function StatusBadge({ tone, text, help, optional = false }) {
  return (
    <span
      className={`state-badge ${tone} ${optional ? "badge-optional" : "badge-core"}`}
      title={help}
      aria-label={`${text}: ${help}`}
    >
      {text}
      <span className="badge-help" aria-hidden="true">
        i
      </span>
    </span>
  );
}

function SummaryColumn({ title, description, items, dataSource }) {
  return (
    <article className="panel">
      <header className="panel-header">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
          <p className="muted-text">핵심 배지 우선순위: 품질 → 출처 → 신선도 (공식확정은 보조 배지)</p>
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
              {prioritizedBadges(item).map((badge) => (
                <StatusBadge key={`${item.option_name}-${badge.key}`} tone={badge.tone} text={badge.text} help={badge.help} optional={badge.optional} />
              ))}
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
              {prioritizedBadges(item).map((badge) => (
                <StatusBadge key={`${item.matchup_id}-${badge.key}`} tone={badge.tone} text={badge.text} help={badge.help} optional={badge.optional} />
              ))}
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

function statusPriority(status) {
  if (status === "warn") return 2;
  if (status === "info") return 1;
  return 0;
}

function statusKorean(status) {
  if (status === "warn") return "경고";
  if (status === "info") return "주의";
  return "정상";
}

function sourceBiasStatus(articleRatio) {
  if (articleRatio === null) return "info";
  if (articleRatio >= 0.7) return "warn";
  if (articleRatio >= 0.5) return "info";
  return "ok";
}

function reviewQueueStatus({ pendingCount, pendingOver24hCount }) {
  if (pendingOver24hCount !== null) {
    if (pendingOver24hCount > 0) return "warn";
    if (pendingCount !== null && pendingCount > 0) return "info";
    return "ok";
  }
  if (pendingCount !== null) {
    if (pendingCount > 50) return "warn";
    if (pendingCount > 0) return "info";
    return "ok";
  }
  return "info";
}

function makeQualitySignals({
  freshnessP90Hours,
  freshnessStatus,
  completenessRatio,
  completenessStatus,
  officialPendingCount,
  officialPendingRatio,
  pendingStatus,
  articleRatio,
  reviewPendingCount,
  reviewPendingOver24hCount
}) {
  const reviewStatus = reviewQueueStatus({
    pendingCount: reviewPendingCount,
    pendingOver24hCount: reviewPendingOver24hCount
  });
  const sourceStatus = sourceBiasStatus(articleRatio);

  const signals = [
    {
      key: "freshness",
      status: freshnessStatus,
      label: "신선도 지연",
      value: formatHours(freshnessP90Hours),
      copy: "최근 수집 시점 기준 상위 90% 지연 시간입니다.",
      action:
        freshnessStatus === "warn"
          ? "최근 48시간 내 조사 수집 누락 여부를 확인하고 수집 작업을 재실행하세요."
          : "지연 시간 추이를 모니터링하고 급증 시 수집 로그를 점검하세요."
    },
    {
      key: "official_pending",
      status: pendingStatus,
      label: "공식확정 대기",
      value:
        officialPendingCount !== null
          ? `${officialPendingCount}건`
          : officialPendingRatio !== null
            ? formatPercent(officialPendingRatio * 100)
            : "-",
      copy: "공식 출처 확정 전 대기 항목 규모입니다.",
      action:
        pendingStatus === "warn"
          ? "상위 영향 항목부터 공식 출처 링크를 우선 보강하세요."
          : "대기 항목의 출처 우선순위를 확인해 순차 검수하세요."
    },
    {
      key: "review_queue",
      status: reviewStatus,
      label: "검수 대기열",
      value: reviewPendingCount !== null ? `${reviewPendingCount}건` : "-",
      copy: "수동 검수 대기 중인 항목 수입니다.",
      action:
        reviewStatus === "warn"
          ? "24시간 초과 대기 항목부터 처리하고 담당자 할당을 갱신하세요."
          : "대기열 증가 추세를 확인하고 필요 시 일괄 처리 계획을 적용하세요."
    },
    {
      key: "completeness",
      status: completenessStatus,
      label: "완전성 지표",
      value: completenessRatio === null ? "-" : formatPercent(completenessRatio * 100),
      copy: "법정 완전성 우선, 미제공 시 공식확정 비율을 대체값으로 사용합니다.",
      action:
        completenessStatus === "warn"
          ? "누락 필드가 많은 항목을 우선 보강하고 수집 스키마 매핑을 재검토하세요."
          : "완전성 추세를 모니터링하고 임계치 하락 시 누락 필드를 점검하세요."
    },
    {
      key: "source_bias",
      status: sourceStatus,
      label: "출처 편중(기사 비율)",
      value: articleRatio === null ? "-" : formatPercent(articleRatio * 100),
      copy: "기사 채널 비중이 높으면 공신력 변동성이 커질 수 있습니다.",
      action:
        sourceStatus === "warn"
          ? "NESDC/공식 채널 보강을 우선 배치해 출처 편중을 완화하세요."
          : "채널 믹스를 주기적으로 확인해 편중이 심화되지 않도록 관리하세요."
    }
  ];

  return signals.sort((a, b) => statusPriority(b.status) - statusPriority(a.status));
}

function QualityPanel({ quality }) {
  if (!quality) {
    return (
      <section className="panel">
        <header className="panel-header">
          <div>
            <h3>운영 품질 패널 v3</h3>
            <p>실데이터 품질 지표를 불러오지 못했습니다.</p>
          </div>
        </header>
        <div className="empty-state">데이터 없음: 품질 API 응답을 기다리는 중입니다. 잠시 후 다시 확인해 주세요.</div>
      </section>
    );
  }

  const freshnessP90Hours = asNumber(quality?.freshness_p90_hours);
  const completenessRatio = resolveCompletenessRatio(quality);
  const officialPendingCount = resolveOfficialPendingCount(quality);
  const officialPendingRatio = resolveOfficialPendingRatio(quality);
  const reviewPendingCount = asNumber(readPath(quality, ["review_queue", "pending_count"]));
  const reviewPendingOver24hCount = asNumber(readPath(quality, ["review_queue", "pending_over_24h_count"]));
  const articleRatio = normalizeRatio(readPath(quality, ["source_channel_mix", "article_ratio"]));
  const nesdcRatio = normalizeRatio(readPath(quality, ["source_channel_mix", "nesdc_ratio"]));

  const freshnessStatus = statusFromFreshnessP90(freshnessP90Hours);
  const completenessStatus = statusFromCompleteness(completenessRatio);
  const pendingStatus = statusFromOfficialPending({
    count: officialPendingCount,
    ratio: officialPendingRatio
  });
  const signals = makeQualitySignals({
    freshnessP90Hours,
    freshnessStatus,
    completenessRatio,
    completenessStatus,
    officialPendingCount,
    officialPendingRatio,
    pendingStatus,
    articleRatio,
    reviewPendingCount,
    reviewPendingOver24hCount
  });
  const overall = overallStatus(signals.map((signal) => signal.status));
  const warningCount = signals.filter((signal) => signal.status === "warn").length;

  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h3>운영 품질 패널 v3</h3>
          <p>경고 항목을 먼저 보여주고, 각 신호마다 바로 실행할 확인 액션을 제공합니다.</p>
        </div>
        <div className="badge-row">
          <span className={`state-badge ${overall}`}>전체 {statusKorean(overall)}</span>
          <span className={`state-badge ${warningCount > 0 ? "warn" : "ok"}`}>경고 항목 {warningCount}건</span>
        </div>
      </header>

      <div className={`quality-priority-banner ${warningCount > 0 ? "warn" : "ok"}`}>
        {warningCount > 0
          ? "우선 확인: 경고 항목을 먼저 처리하세요. 각 카드의 확인 액션을 순서대로 수행하면 원인 추적 시간을 줄일 수 있습니다."
          : "안정 상태: 경고 항목은 없습니다. 주의 항목 중심으로 추세 모니터링을 유지하세요."}
      </div>

      <div className="quality-grid">
        {signals.map((signal) => (
          <article key={signal.key} className={`quality-item ${signal.status}`}>
            <div className="quality-item-top">
              <p className="quality-label">{signal.label}</p>
              <span className={`state-badge ${signal.status}`}>{statusKorean(signal.status)}</span>
            </div>
            <strong>{signal.value}</strong>
            <p className="quality-copy">{signal.copy}</p>
            <p className="quality-action">
              <strong>확인 액션:</strong> {signal.action}
            </p>
          </article>
        ))}
      </div>

      <div className="quality-source-mix">
        <p className="quality-label">실데이터 소스 비중</p>
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
        기준 시각: {formatDateTime(quality?.generated_at)} · 상태 코드: {quality?.quality_status || "-"}
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
