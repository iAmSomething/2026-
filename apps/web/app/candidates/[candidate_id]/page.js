import Link from "next/link";

import { formatDate, formatDateTime, joinChannels } from "../../_components/format";
import { fetchApi } from "../../_lib/api";

const RELATED_MATCHUP_ALIAS_BY_CANDIDATE = {
  "cand-jwo": "m_2026_seoul_mayor"
};

export default async function CandidatePage({ params }) {
  const resolvedParams = await params;
  const candidateId = resolvedParams.candidate_id;
  const payload = await fetchApi(`/api/v1/candidates/${encodeURIComponent(candidateId)}`);

  if (!payload.ok) {
    return (
      <main className="detail-root">
        <section className="panel error-panel">
          <h1>후보 정보를 불러오지 못했습니다.</h1>
          <p>요청 ID: {candidateId}</p>
          <p>status: {payload.status}</p>
          <p className="muted-text">{JSON.stringify(payload.body)}</p>
          <Link href="/" className="text-link">
            대시보드로 이동
          </Link>
        </section>
      </main>
    );
  }

  const candidate = payload.body;
  const relatedAlias = RELATED_MATCHUP_ALIAS_BY_CANDIDATE[candidateId];
  const relatedMatchup = relatedAlias
    ? await fetchApi(`/api/v1/matchups/${encodeURIComponent(relatedAlias)}`)
    : { ok: false, body: null };

  return (
    <main className="detail-root">
      <section className="panel detail-hero">
        <div>
          <p className="kicker">CANDIDATE DETAIL</p>
          <h1>{candidate.name_ko}</h1>
          <p>
            {candidate.party_name || "정당 미상"} · {candidate.job || "직업 정보 없음"}
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
          <h3>기본 정보</h3>
          <dl className="meta-grid">
            <dt>candidate_id</dt>
            <dd>{candidate.candidate_id}</dd>
            <dt>정당</dt>
            <dd>{candidate.party_name || "-"}</dd>
            <dt>성별</dt>
            <dd>{candidate.gender || "-"}</dd>
            <dt>생년월일</dt>
            <dd>{formatDate(candidate.birth_date)}</dd>
            <dt>직업</dt>
            <dd>{candidate.job || "-"}</dd>
            <dt>약력</dt>
            <dd>{candidate.career_summary || "-"}</dd>
            <dt>선거이력</dt>
            <dd>{candidate.election_history || "-"}</dd>
            <dt>출처 채널</dt>
            <dd>{joinChannels(candidate.source_channels)}</dd>
            <dt>최신시각</dt>
            <dd>{formatDateTime(candidate.article_published_at || candidate.official_release_at)}</dd>
          </dl>
        </article>

        <article className="panel">
          <h3>관련 매치업 요약</h3>
          {relatedMatchup.ok ? (
            <div className="related-card">
              <strong>{relatedMatchup.body.title}</strong>
              <p>
                {relatedMatchup.body.pollster || "조사기관 미상"} · {formatDate(relatedMatchup.body.survey_end_date)}
              </p>
              <p className="muted-text">matchup_id: {relatedMatchup.body.matchup_id}</p>
              <Link href={`/matchups/${encodeURIComponent(relatedAlias)}`} className="text-link small">
                매치업 상세 보기
              </Link>
            </div>
          ) : (
            <div className="empty-state">연결된 매치업 정보가 없습니다.</div>
          )}
        </article>
      </section>
    </main>
  );
}
