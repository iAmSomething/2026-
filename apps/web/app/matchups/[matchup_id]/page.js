import Link from "next/link";

import { toScenarioBadge } from "../../_components/demoParams";
import { formatDate, formatDateTime, formatPercent, joinChannels } from "../../_components/format";
import { fetchApi } from "../../_lib/api";

const REGIONAL_OFFICE_TYPES = new Set([
  "metro_mayor",
  "metro_council",
  "superintendent",
  "local_mayor",
  "local_council",
  "by_election",
  "광역자치단체장",
  "광역의회",
  "교육감",
  "기초자치단체장",
  "기초의회",
  "재보궐"
]);

const OFFICE_TYPE_LABELS = {
  metro_mayor: "광역자치단체장",
  metro_council: "광역의회",
  superintendent: "교육감",
  local_mayor: "기초자치단체장",
  local_council: "기초의회",
  by_election: "재보궐",
  광역자치단체장: "광역자치단체장",
  광역의회: "광역의회",
  교육감: "교육감",
  기초자치단체장: "기초자치단체장",
  기초의회: "기초의회",
  재보궐: "재보궐"
};

const REGION_PREFIX_LABELS = {
  "KR-11": "서울특별시",
  "KR-21": "부산광역시",
  "KR-22": "대구광역시",
  "KR-23": "인천광역시",
  "KR-24": "광주광역시",
  "KR-25": "대전광역시",
  "KR-26": "울산광역시",
  "KR-29": "세종특별자치시",
  "KR-31": "경기도",
  "KR-32": "강원특별자치도",
  "KR-33": "충청북도",
  "KR-34": "충청남도",
  "KR-35": "전북특별자치도",
  "KR-36": "전라남도",
  "KR-37": "경상북도",
  "KR-38": "경상남도",
  "KR-39": "제주특별자치도"
};

function resolveScope({ audienceScope, officeType, regionCode }) {
  if (audienceScope === "national" || audienceScope === "regional" || audienceScope === "local") {
    return audienceScope;
  }
  if (regionCode === "KR-00-000" || regionCode === "00-000") return "national";
  if (REGIONAL_OFFICE_TYPES.has(officeType)) return "regional";
  return "local";
}

function scopeBadge(scope) {
  if (scope === "national") return { text: "전국 스코프", tone: "ok" };
  if (scope === "regional") return { text: "지역(광역) 스코프", tone: "info" };
  return { text: "기초(시군구) 스코프", tone: "warn" };
}

function sourceTone(matchup) {
  const channels = Array.isArray(matchup?.source_channels) ? matchup.source_channels : [];
  const source = matchup?.source_channel || channels[0] || "unknown";
  if (source === "nesdc") return "ok";
  if (channels.includes("article") && channels.includes("nesdc")) return "info";
  if (source === "article") return "warn";
  return "info";
}

function sourceLabel(matchup) {
  const channels = Array.isArray(matchup?.source_channels) ? matchup.source_channels : [];
  const source = matchup?.source_channel || channels[0] || "unknown";
  if (source === "nesdc") return "출처 NESDC";
  if (channels.includes("article") && channels.includes("nesdc")) return "출처 혼합";
  if (source === "article") return "출처 기사";
  return "출처 미확인";
}

function officialTone(confirmed) {
  return confirmed ? "ok" : "warn";
}

function officialLabel(confirmed) {
  return confirmed ? "공식확정" : "공식확정 대기";
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

function optionNeedsReview(matchup, option) {
  if (option?.needs_manual_review) return true;
  const freshness = Number(matchup?.freshness_hours);
  return matchup?.is_official_confirmed === false && Number.isFinite(freshness) && freshness > 48;
}

function buildCandidateDetailHref(candidateId, matchupId) {
  if (!candidateId) return null;
  const candidatePath = `/candidates/${encodeURIComponent(candidateId)}`;
  const query = `from=matchup&matchup_id=${encodeURIComponent(matchupId)}`;
  return `${candidatePath}?${query}`;
}

function regionPrefix(regionCode) {
  if (!regionCode) return null;
  const krMatch = String(regionCode).match(/^KR-\d{2}/);
  if (krMatch) return krMatch[0];
  const shortMatch = String(regionCode).match(/^(\d{2})/);
  if (shortMatch) return `KR-${shortMatch[1]}`;
  return null;
}

function officeTypeLabel(officeType) {
  if (!officeType) return "선거유형 미상";
  return OFFICE_TYPE_LABELS[officeType] || officeType;
}

function regionLabel(regionCode) {
  const prefix = regionPrefix(regionCode);
  if (prefix && REGION_PREFIX_LABELS[prefix]) return REGION_PREFIX_LABELS[prefix];
  return regionCode || "지역 미상";
}

function canonicalMatchupTitle(matchup) {
  return `${regionLabel(matchup?.region_code)} ${officeTypeLabel(matchup?.office_type)}`;
}

export default async function MatchupPage({ params, searchParams }) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const requestedMatchupId = resolvedParams.matchup_id;

  const confirmDemo = (resolvedSearch?.confirm_demo || "").trim().toLowerCase();
  const sourceDemo = (resolvedSearch?.source_demo || "").trim().toLowerCase();
  const demoState = (resolvedSearch?.demo_state || "").trim().toLowerCase();
  const stateDemo = (resolvedSearch?.state_demo || "").trim().toLowerCase();

  const payload = await fetchApi(`/api/v1/matchups/${encodeURIComponent(requestedMatchupId)}`);

  if (!payload.ok) {
    return (
      <main className="detail-root">
        <section className="panel error-panel">
          <h1>매치업을 불러오지 못했습니다.</h1>
          <p>요청 ID: {requestedMatchupId}</p>
          <p>status: {payload.status}</p>
          <p className="muted-text">{JSON.stringify(payload.body)}</p>
          <Link href="/" className="text-link">
            대시보드로 이동
          </Link>
        </section>
      </main>
    );
  }

  const matchup = payload.body;
  let scenarios = Array.isArray(matchup.scenarios) && matchup.scenarios.length > 0
    ? matchup.scenarios.map((scenario) => ({
        ...scenario,
        options: Array.isArray(scenario.options) ? [...scenario.options] : []
      }))
    : [
        {
          scenario_key: "default",
          scenario_type: "multi_candidate",
          scenario_title: "최신 스냅샷",
          options: Array.isArray(matchup.options) ? [...matchup.options] : []
        }
      ];

  if (stateDemo === "empty") {
    scenarios = scenarios.map((scenario) => ({ ...scenario, options: [] }));
  }
  if (stateDemo === "review") {
    scenarios = scenarios.map((scenario) => ({
      ...scenario,
      options: scenario.options.map((option, index) => (index === 0 ? { ...option, needs_manual_review: true } : option))
    }));
  }

  scenarios = scenarios.map((scenario) => ({
    ...scenario,
    options: [...scenario.options].sort((a, b) => (b.value_mid || 0) - (a.value_mid || 0))
  }));
  const totalOptionCount = scenarios.reduce((acc, scenario) => acc + scenario.options.length, 0);
  const resolvedScope = resolveScope({
    audienceScope: matchup.audience_scope,
    officeType: matchup.office_type,
    regionCode: matchup.region_code
  });
  const scopeInfo = scopeBadge(resolvedScope);
  const compareInfo =
    resolvedScope === "national"
      ? { text: "전국 vs 전국 비교 가능", tone: "ok" }
      : { text: "지역/기초 vs 지역/기초 비교 권장", tone: "warn" };

  const scenarioBadges = [];
  const isOfficialScenario = confirmDemo === "official" || sourceDemo === "nesdc";
  const isArticleScenario = confirmDemo === "article" || sourceDemo === "article";

  if (isOfficialScenario) {
    scenarioBadges.push(toScenarioBadge("공식확정", "ok"));
  } else if (isArticleScenario) {
    scenarioBadges.push(toScenarioBadge("기사 기반 추정", "warn"));
  }

  if (confirmDemo) {
    scenarioBadges.push(
      toScenarioBadge(
        `confirm_demo=${confirmDemo}`,
        confirmDemo === "official" ? "ok" : "warn"
      )
    );
  }
  if (sourceDemo) {
    scenarioBadges.push(
      toScenarioBadge(`source_demo=${sourceDemo}`, sourceDemo === "nesdc" ? "ok" : "info")
    );
  }
  if (demoState) {
    scenarioBadges.push(toScenarioBadge(`demo_state=${demoState}`, demoState === "ready" ? "ok" : "info"));
  }

  let scenarioCopy = "";
  if (isOfficialScenario) {
    scenarioCopy = "공식확정 데이터 기준으로 결과를 노출합니다.";
  } else if (isArticleScenario) {
    scenarioCopy = "기사 기반 추정 데이터 기준으로 결과를 노출합니다.";
  } else if (confirmDemo || sourceDemo || demoState) {
    const confirmLabel =
      confirmDemo === "official"
        ? "공식확정"
        : confirmDemo === "article"
          ? "기사 보강"
          : "기본";
    const sourceLabel =
      sourceDemo === "nesdc" ? "중앙선관위/NESDC" : sourceDemo === "article" ? "기사" : "기본";
    const stateLabel = demoState === "ready" ? "ready(노출 준비 완료)" : demoState || "기본";
    scenarioCopy = `상태 시나리오: ${confirmLabel} · ${sourceLabel} · ${stateLabel}`;
  }

  const canonicalTitle = canonicalMatchupTitle(matchup);
  const articleHeadline = matchup.title || matchup.matchup_id || "기사 제목 미제공";
  const pollsterLabel = matchup.pollster || "조사기관 미상";
  const surveyPeriod = `${formatDate(matchup.survey_start_date)} ~ ${formatDate(matchup.survey_end_date)}`;

  return (
    <main className="detail-root">
      <section className="panel detail-hero">
        <div>
          <p className="kicker">MATCHUP DETAIL</p>
          <h1>{canonicalTitle}</h1>
          <p className="muted-text">기사 제목: {articleHeadline}</p>
          <p>
            {pollsterLabel} · {surveyPeriod}
          </p>
        </div>
        <div className="hero-actions">
          <Link href="/search" className="text-link">
            지역 검색
          </Link>
          <Link href="/" className="text-link">
            대시보드
          </Link>
        </div>
      </section>

      <section className="panel scenario-panel">
        <div className="badge-row">
          <span className="state-badge info">요청 ID(alias): {requestedMatchupId}</span>
          <span className="state-badge ok">표준 ID(canonical): {matchup.matchup_id}</span>
          <span className={`state-badge ${scopeInfo.tone}`}>{scopeInfo.text}</span>
          <span className={`state-badge ${compareInfo.tone}`}>{compareInfo.text}</span>
          <span className={`state-badge ${sourceTone(matchup)}`}>{sourceLabel(matchup)}</span>
          <span className={`state-badge ${officialTone(matchup.is_official_confirmed)}`}>{officialLabel(matchup.is_official_confirmed)}</span>
          <span className={`state-badge ${freshnessTone(matchup.freshness_hours)}`}>{freshnessLabel(matchup.freshness_hours)}</span>
          {matchup.has_data === false ? <span className="state-badge info">데이터 준비 중</span> : null}
          {matchup.needs_manual_review ? <span className="state-badge warn">검수대기</span> : null}
          {scenarioBadges.map((badge) => (
            <span key={badge.text} className={`state-badge ${badge.tone}`}>
              {badge.text}
            </span>
          ))}
        </div>
        <p className="scenario-copy">
          스코프 고정: 지역 상세에서는 조사 스코프를 항상 배지로 노출합니다. 전국 지표와 지역/기초 지표의 직접 비교는 금지합니다.
        </p>
        {scenarioCopy ? <p className="scenario-copy">{scenarioCopy}</p> : null}
      </section>

      <section className="detail-grid">
        <article className="panel">
          <h3>후보별 최신 지표</h3>
          {totalOptionCount === 0 ? (
            <div className="empty-state">
              {matchup.has_data === false
                ? "데이터 준비 중: 관측치 수집 전이며 매치업 메타데이터만 먼저 노출됩니다."
                : "데이터 없음: 후보별 지표가 아직 수집되지 않았습니다."}
            </div>
          ) : (
            <div className="stack">
              {scenarios.map((scenario, scenarioIndex) => {
                const maxValue = Math.max(...scenario.options.map((option) => option.value_mid || 0), 1);
                const scenarioTypeLabel = scenario.scenario_type === "head_to_head" ? "양자대결" : "다자대결";
                return (
                  <section key={`${scenario.scenario_key}-${scenarioIndex}`}>
                    <div className="badge-row option-row-meta">
                      <span className="state-badge info">{scenarioTypeLabel}</span>
                      <span className="state-badge ok">{scenario.scenario_title || "시나리오"}</span>
                    </div>
                    <ul className="option-bars">
                      {scenario.options.map((option, optionIndex) => {
                        const width = Math.max(6, Math.round(((option.value_mid || 0) / maxValue) * 100));
                        const review = optionNeedsReview(matchup, option);
                        const candidateHref = buildCandidateDetailHref(option.candidate_id, matchup.matchup_id);
                        return (
                          <li key={`${scenario.scenario_key}-${option.candidate_id || option.option_name}-${optionIndex}`}>
                            <div className="option-row-head">
                              <strong>
                                {candidateHref ? (
                                  <Link href={candidateHref} className="text-link small">
                                    {option.option_name}
                                  </Link>
                                ) : (
                                  option.option_name
                                )}
                              </strong>
                              <span>{formatPercent(option.value_mid)}</span>
                            </div>
                            <div className="bar-track">
                              <span className="bar-fill" style={{ width: `${width}%` }} />
                            </div>
                            <div className="badge-row option-row-meta">
                              <span className={`state-badge ${sourceTone(matchup)}`}>{sourceLabel(matchup)}</span>
                              <span className={`state-badge ${officialTone(matchup.is_official_confirmed)}`}>{officialLabel(matchup.is_official_confirmed)}</span>
                              {review ? <span className="state-badge warn">검수대기</span> : null}
                              {!option.candidate_id ? <span className="state-badge warn">candidate_id 누락</span> : null}
                            </div>
                            <p className="muted-text">정당: {option.party_name || "미확정(검수대기)"}</p>
                            <p className="muted-text">원문: {option.value_raw || "-"}</p>
                            {candidateHref ? (
                              <Link href={candidateHref} className="text-link small">
                                프로필
                              </Link>
                            ) : (
                              <button type="button" className="text-link small" disabled title="candidate_id가 없어 이동할 수 없습니다.">
                                프로필
                              </button>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
            </div>
          )}
        </article>

        <article className="panel">
          <h3>조사 메타데이터</h3>
          <dl className="meta-grid">
            <dt>matchup_id</dt>
            <dd>{matchup.matchup_id}</dd>
            <dt>region_code</dt>
            <dd>{matchup.region_code || "-"}</dd>
            <dt>office_type</dt>
            <dd>{matchup.office_type || "-"}</dd>
            <dt>표본수</dt>
            <dd>{matchup.sample_size || "-"}</dd>
            <dt>응답률</dt>
            <dd>{matchup.response_rate ? `${matchup.response_rate}%` : "-"}</dd>
            <dt>오차범위</dt>
            <dd>{matchup.margin_of_error ? `±${matchup.margin_of_error}%p` : "-"}</dd>
            <dt>신뢰수준</dt>
            <dd>{matchup.confidence_level ? `${matchup.confidence_level}%` : "-"}</dd>
            <dt>source_grade</dt>
            <dd>{matchup.source_grade || "-"}</dd>
            <dt>업데이트</dt>
            <dd>{formatDateTime(matchup.article_published_at || matchup.official_release_at)}</dd>
            <dt>source_channels</dt>
            <dd>{joinChannels(matchup.source_channels)}</dd>
          </dl>
        </article>
      </section>
    </main>
  );
}
