import Link from "next/link";

import { toScenarioBadge } from "../../_components/demoParams";
import { formatDate, formatDateTime, formatPercent, joinChannels } from "../../_components/format";
import { fetchApi } from "../../_lib/api";

const REGIONAL_OFFICE_TYPES = new Set([
  "광역자치단체장",
  "광역의회",
  "교육감",
  "기초자치단체장",
  "기초의회",
  "재보궐"
]);

const REGION_PREFIX_LABELS = {
  "11": "서울특별시",
  "21": "부산광역시",
  "22": "대구광역시",
  "23": "인천광역시",
  "24": "광주광역시",
  "25": "대전광역시",
  "26": "울산광역시",
  "29": "세종특별자치시",
  "31": "경기도",
  "32": "강원특별자치도",
  "33": "충청북도",
  "34": "충청남도",
  "35": "전북특별자치도",
  "36": "전라남도",
  "37": "경상북도",
  "38": "경상남도",
  "39": "제주특별자치도"
};

function regionPrefix(value) {
  if (!value) return null;
  const match = String(value).trim().match(/(?:KR-)?(\d{2})/i);
  return match ? match[1] : null;
}

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

function scenarioGroupKey(scenario) {
  const type = (scenario?.scenario_type || "").toLowerCase();
  if (type === "head_to_head" || type === "two_candidate" || type === "binary") {
    return "head_to_head";
  }
  if (type === "multi_candidate" || type === "multi") {
    return "multi_candidate";
  }
  const optionCount = Array.isArray(scenario?.options) ? scenario.options.length : 0;
  return optionCount <= 2 ? "head_to_head" : "multi_candidate";
}

function scenarioGroupLabel(groupKey) {
  return groupKey === "head_to_head" ? "양자 시나리오" : "다자 시나리오";
}

function scenarioTypeLabel(scenario) {
  const groupKey = scenarioGroupKey(scenario);
  return groupKey === "head_to_head" ? "양자대결" : "다자대결";
}

function cloneOption(option, nextValueMid) {
  if (!option) return null;
  return {
    ...option,
    value_mid: nextValueMid,
    value_min: nextValueMid,
    value_max: nextValueMid,
    value_raw: `${nextValueMid}%`
  };
}

function inferRegionLabel(matchup) {
  const directCandidates = [
    matchup?.region_name,
    matchup?.audience_region_name,
    matchup?.region_label,
    matchup?.sido_name
  ];
  const direct = directCandidates.find((value) => typeof value === "string" && value.trim().length > 0);
  if (direct) return direct.trim();
  const prefix = regionPrefix(matchup?.region_code);
  return prefix ? REGION_PREFIX_LABELS[prefix] || null : null;
}

function metroMayorTitle(regionLabel) {
  if (!regionLabel) return "광역자치단체장 선거";
  if (regionLabel.endsWith("특별시")) return `${regionLabel.replace("특별시", "")}시장`;
  if (regionLabel.endsWith("광역시")) return `${regionLabel.replace("광역시", "")}시장`;
  if (regionLabel.endsWith("특별자치시")) return `${regionLabel.replace("특별자치시", "")}시장`;
  if (regionLabel.endsWith("특별자치도")) return `${regionLabel.replace("특별자치도", "")}도지사`;
  if (regionLabel.endsWith("도")) return `${regionLabel.replace("도", "")}도지사`;
  return `${regionLabel} 단체장 선거`;
}

function officeElectionLabel(officeType, regionLabel) {
  if (officeType === "광역자치단체장") return metroMayorTitle(regionLabel);
  if (officeType === "광역의회") return regionLabel ? `${regionLabel} 광역의회` : "광역의회 선거";
  if (officeType === "교육감") return regionLabel ? `${regionLabel} 교육감` : "교육감 선거";
  if (officeType === "기초자치단체장") return regionLabel ? `${regionLabel} 기초자치단체장` : "기초자치단체장 선거";
  if (officeType === "기초의회") return regionLabel ? `${regionLabel} 기초의회` : "기초의회 선거";
  if (officeType === "재보궐") return regionLabel ? `${regionLabel} 재보궐` : "재보궐 선거";
  return officeType || "선거";
}

function buildSurveySubtitle(matchup, articleSubtitle) {
  const parts = [];
  if (articleSubtitle) parts.push(`기사: ${articleSubtitle}`);
  const pollster = matchup?.pollster || "조사기관 미상";
  const period = `${formatDate(matchup?.survey_start_date)} ~ ${formatDate(matchup?.survey_end_date)}`;
  parts.push(`${pollster} · ${period}`);
  return parts.join(" / ");
}

export default async function MatchupPage({ params, searchParams }) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const requestedMatchupId = resolvedParams.matchup_id;

  const confirmDemo = (resolvedSearch?.confirm_demo || "").trim().toLowerCase();
  const sourceDemo = (resolvedSearch?.source_demo || "").trim().toLowerCase();
  const demoState = (resolvedSearch?.demo_state || "").trim().toLowerCase();
  const stateDemo = (resolvedSearch?.state_demo || "").trim().toLowerCase();
  const scenarioDemo = (resolvedSearch?.scenario_demo || "").trim().toLowerCase();

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
  const canonicalTitle = matchup.canonical_title || matchup.title || matchup.matchup_id;
  const articleSubtitle =
    matchup.article_title && matchup.article_title !== canonicalTitle ? matchup.article_title : null;
  const regionLabel = inferRegionLabel(matchup);
  const electionTitle = officeElectionLabel(matchup.office_type, regionLabel);
  const surveySubtitle = buildSurveySubtitle(matchup, articleSubtitle);
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

  if (scenarioDemo === "triad") {
    const baseOptions = scenarios.flatMap((scenario) => scenario.options).filter(Boolean);
    const uniqueOptions = [];
    const seen = new Set();
    for (const option of baseOptions) {
      const key = option.candidate_id || option.option_name;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      uniqueOptions.push(option);
    }
    let ranked = uniqueOptions.sort((a, b) => (b.value_mid || 0) - (a.value_mid || 0));
    if (ranked.length < 2) {
      ranked = [
        {
          candidate_id: "cand_demo_a",
          option_name: "후보A",
          party_name: "가상정당A",
          value_mid: 44,
          value_raw: "44%"
        },
        {
          candidate_id: "cand_demo_b",
          option_name: "후보B",
          party_name: "가상정당B",
          value_mid: 41,
          value_raw: "41%"
        },
        {
          candidate_id: "cand_demo_c",
          option_name: "후보C",
          party_name: "가상정당C",
          value_mid: 33,
          value_raw: "33%"
        },
        {
          candidate_id: "cand_demo_d",
          option_name: "후보D",
          party_name: "가상정당D",
          value_mid: 29,
          value_raw: "29%"
        }
      ];
    }
    if (ranked.length >= 2) {
      const first = ranked[0];
      const second = ranked[1];
      const third = ranked[2] || ranked[1];
      const fourth = ranked[3] || ranked[0];
      scenarios = [
        {
          scenario_key: "head_to_head_primary",
          scenario_type: "head_to_head",
          scenario_title: "양자 가상대결 A",
          options: [cloneOption(first, first.value_mid || 44), cloneOption(second, second.value_mid || 41)].filter(Boolean)
        },
        {
          scenario_key: "head_to_head_secondary",
          scenario_type: "head_to_head",
          scenario_title: "양자 가상대결 B",
          options: [cloneOption(first, Math.max(0, (first.value_mid || 44) - 2)), cloneOption(second, Math.max(0, (second.value_mid || 41) + 2))].filter(Boolean)
        },
        {
          scenario_key: "multi_candidate_primary",
          scenario_type: "multi_candidate",
          scenario_title: "다자 구도",
          options: [
            cloneOption(first, Math.max(0, first.value_mid || 44)),
            cloneOption(second, Math.max(0, second.value_mid || 41)),
            cloneOption(third, Math.max(0, (third.value_mid || 33) - 1)),
            cloneOption(fourth, Math.max(0, (fourth.value_mid || 31) - 2))
          ].filter(Boolean)
        }
      ];
    }
  }

  scenarios = scenarios.map((scenario) => ({
    ...scenario,
    options: [...scenario.options].sort((a, b) => (b.value_mid || 0) - (a.value_mid || 0))
  }));
  const rawOptionCount = Array.isArray(matchup.options) ? matchup.options.length : 0;
  const rawScenarioOptionCount = Array.isArray(matchup.scenarios)
    ? matchup.scenarios.reduce((acc, scenario) => acc + (Array.isArray(scenario?.options) ? scenario.options.length : 0), 0)
    : 0;
  const hasPollPayload = rawOptionCount + rawScenarioOptionCount > 0;
  const isIncumbentFallback = matchup.fallback_mode === "incumbent" && !hasPollPayload;
  const fallbackCandidates = isIncumbentFallback && Array.isArray(matchup.incumbent_candidates)
    ? matchup.incumbent_candidates
    : [];
  const groupedScenarios = ["head_to_head", "multi_candidate"]
    .map((groupKey) => ({
      groupKey,
      groupLabel: scenarioGroupLabel(groupKey),
      items: scenarios.filter((scenario) => scenarioGroupKey(scenario) === groupKey)
    }))
    .filter((group) => group.items.length > 0);
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
  if (scenarioDemo) {
    scenarioBadges.push(toScenarioBadge(`scenario_demo=${scenarioDemo}`, scenarioDemo === "triad" ? "ok" : "info"));
  }
  if (isIncumbentFallback) {
    scenarioBadges.push(toScenarioBadge("추정(현직 기반)", "warn"));
    scenarioBadges.push(toScenarioBadge("여론조사 아님", "warn"));
  }

  let scenarioCopy = "";
  if (isIncumbentFallback) {
    scenarioCopy = "해당 매치업은 여론조사 관측치가 없어 현직자 문맥 기반 추정 후보만 제공합니다.";
  } else if (isOfficialScenario) {
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
  if (scenarioDemo === "triad") {
    scenarioCopy = scenarioCopy
      ? `${scenarioCopy} · 시나리오 블록: 양자2 + 다자1`
      : "시나리오 블록 데모: 양자 2개 + 다자 1개";
  }

  return (
    <main className="detail-root">
      <section className="panel detail-hero">
        <div>
          <p className="kicker">MATCHUP DETAIL</p>
          <h1>{electionTitle}</h1>
          <p>{surveySubtitle}</p>
          {canonicalTitle && canonicalTitle !== electionTitle ? (
            <p className="muted-text">표준 제목(canonical): {canonicalTitle}</p>
          ) : null}
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

      {isIncumbentFallback ? (
        <section className="panel fallback-panel">
          <header className="panel-header">
            <div>
              <h3>현직자 fallback 후보</h3>
              <p>여론조사 데이터가 없어 현직자 문맥 기반 후보를 별도 블록으로 제공합니다.</p>
            </div>
          </header>
          <div className="badge-row">
            <span className="state-badge warn">추정(현직 기반)</span>
            <span className="state-badge warn">여론조사 아님</span>
          </div>
          <ul className="fallback-candidate-list">
            {fallbackCandidates.map((candidate, index) => {
              const candidateHref = buildCandidateDetailHref(candidate.candidate_id, matchup.matchup_id);
              return (
                <li key={`${candidate.candidate_id || candidate.name}-${index}`} className="fallback-candidate-item">
                  <div className="fallback-candidate-head">
                    <strong>
                      {candidateHref ? (
                        <Link href={candidateHref} className="text-link small">
                          {candidate.name}
                        </Link>
                      ) : (
                        candidate.name
                      )}
                    </strong>
                    <span>{typeof candidate.confidence === "number" ? `${(candidate.confidence * 100).toFixed(0)}%` : "-"}</span>
                  </div>
                  <p className="muted-text">정당: {candidate.party || "미확정(검수대기)"}</p>
                  <p className="muted-text">직책: {candidate.office || matchup.office_type || "-"}</p>
                  <p className="muted-text">
                    근거: {Array.isArray(candidate.reasons) && candidate.reasons.length > 0 ? candidate.reasons.join(", ") : "-"}
                  </p>
                  {candidateHref ? (
                    <Link href={candidateHref} className="text-link small">
                      프로필
                    </Link>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section className="detail-grid">
        <article className="panel">
          <header className="panel-header">
            <div>
              <h3>시나리오 섹션</h3>
              <p>양자/다자 시나리오를 분리해 동일 매치업 내부 구도를 비교합니다.</p>
            </div>
          </header>
          {isIncumbentFallback ? (
            <div className="empty-state">
              여론조사 시나리오/옵션이 없어 시나리오 카드 대신 현직자 fallback 후보를 상단 별도 섹션으로 표시합니다.
            </div>
          ) : (
            <>
              <div className="scenario-tab-row" role="tablist" aria-label="시나리오 유형">
                {groupedScenarios.map((group) => (
                  <a key={group.groupKey} href={`#scenario-${group.groupKey}`} className="scenario-tab">
                    {group.groupLabel} ({group.items.length})
                  </a>
                ))}
              </div>
              {totalOptionCount === 0 ? (
                <div className="empty-state">
                  {matchup.has_data === false
                    ? "데이터 준비 중: 관측치 수집 전이며 매치업 메타데이터만 먼저 노출됩니다."
                    : "데이터 없음: 후보별 지표가 아직 수집되지 않았습니다."}
                </div>
              ) : (
                <div className="scenario-group-stack">
                  {groupedScenarios.map((group) => (
                    <section id={`scenario-${group.groupKey}`} key={group.groupKey} className="scenario-group">
                      <header className="scenario-group-head">
                        <h4>{group.groupLabel}</h4>
                        <span className="state-badge info">{group.items.length}개 시나리오</span>
                      </header>
                      <div className="scenario-card-grid">
                        {group.items.map((scenario, scenarioIndex) => {
                          const maxValue = Math.max(...scenario.options.map((option) => option.value_mid || 0), 1);
                          const scenarioType = scenarioTypeLabel(scenario);
                          return (
                            <article key={`${scenario.scenario_key}-${scenarioIndex}`} className="scenario-block">
                              <div className="scenario-block-head">
                                <div className="badge-row option-row-meta">
                                  <span className="state-badge info">{scenarioType}</span>
                                  <span className="state-badge ok">{scenario.scenario_title || "시나리오"}</span>
                                </div>
                              </div>
                              <ul className="option-bars scenario-options">
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
                            </article>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
              )}
            </>
          )}
        </article>

        <article className="panel">
          <h3>조사 메타데이터</h3>
          <div className="badge-row matchup-meta-priority">
            <span className="state-badge ok">조사기관 {matchup.pollster || "-"}</span>
            <span className="state-badge info">표본 {matchup.sample_size || "-"}명</span>
            <span className="state-badge info">응답률 {matchup.response_rate ? `${matchup.response_rate}%` : "-"}</span>
            <span className="state-badge warn">오차 {matchup.margin_of_error ? `±${matchup.margin_of_error}%p` : "-"}</span>
          </div>
          <dl className="meta-grid">
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
            <dt>region_code</dt>
            <dd>{matchup.region_code || "-"}</dd>
            <dt>office_type</dt>
            <dd>{matchup.office_type || "-"}</dd>
            <dt>matchup_id</dt>
            <dd>{matchup.matchup_id}</dd>
          </dl>
        </article>
      </section>
    </main>
  );
}
