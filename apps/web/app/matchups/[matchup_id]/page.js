import Link from "next/link";

import { toScenarioBadge } from "../../_components/demoParams";
import { formatDate, formatDateTime, formatPercent, joinChannels } from "../../_components/format";
import { fetchApi } from "../../_lib/api";

const CANDIDATE_ALIAS_BY_NAME = {
  정원오: "cand-jwo"
};

export default async function MatchupPage({ params, searchParams }) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const requestedMatchupId = resolvedParams.matchup_id;

  const confirmDemo = (resolvedSearch?.confirm_demo || "").trim().toLowerCase();
  const sourceDemo = (resolvedSearch?.source_demo || "").trim().toLowerCase();
  const demoState = (resolvedSearch?.demo_state || "").trim().toLowerCase();

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
  const options = Array.isArray(matchup.options) ? [...matchup.options] : [];
  options.sort((a, b) => (b.value_mid || 0) - (a.value_mid || 0));
  const maxValue = Math.max(...options.map((option) => option.value_mid || 0), 1);

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

  return (
    <main className="detail-root">
      <section className="panel detail-hero">
        <div>
          <p className="kicker">MATCHUP DETAIL</p>
          <h1>{matchup.title || matchup.matchup_id}</h1>
          <p>
            {matchup.pollster || "조사기관 미상"} · {formatDate(matchup.survey_start_date)} ~ {formatDate(matchup.survey_end_date)}
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
          {scenarioBadges.map((badge) => (
            <span key={badge.text} className={`state-badge ${badge.tone}`}>
              {badge.text}
            </span>
          ))}
        </div>
        {scenarioCopy ? <p className="scenario-copy">{scenarioCopy}</p> : null}
      </section>

      <section className="detail-grid">
        <article className="panel">
          <h3>후보별 최신 지표</h3>
          <ul className="option-bars">
            {options.map((option) => {
              const width = Math.max(6, Math.round(((option.value_mid || 0) / maxValue) * 100));
              const candidateAlias = CANDIDATE_ALIAS_BY_NAME[option.option_name];
              return (
                <li key={option.option_name}>
                  <div className="option-row-head">
                    <strong>{option.option_name}</strong>
                    <span>{formatPercent(option.value_mid)}</span>
                  </div>
                  <div className="bar-track">
                    <span className="bar-fill" style={{ width: `${width}%` }} />
                  </div>
                  <p className="muted-text">원문: {option.value_raw || "-"}</p>
                  {candidateAlias ? (
                    <Link href={`/candidates/${candidateAlias}`} className="text-link small">
                      후보 상세 보기
                    </Link>
                  ) : null}
                </li>
              );
            })}
          </ul>
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
