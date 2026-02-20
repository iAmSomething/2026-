import Link from "next/link";

import { formatDate, formatDateTime, formatPercent, joinChannels } from "../../_components/format";
import { fetchApi } from "../../_lib/api";

const CANDIDATE_ALIAS_BY_NAME = {
  정원오: "cand-jwo"
};

export default async function MatchupPage({ params }) {
  const resolvedParams = await params;
  const matchupId = resolvedParams.matchup_id;
  const payload = await fetchApi(`/api/v1/matchups/${encodeURIComponent(matchupId)}`);

  if (!payload.ok) {
    return (
      <main className="detail-root">
        <section className="panel error-panel">
          <h1>매치업을 불러오지 못했습니다.</h1>
          <p>요청 ID: {matchupId}</p>
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
