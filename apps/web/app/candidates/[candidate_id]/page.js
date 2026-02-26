import Link from "next/link";

import { toScenarioBadge } from "../../_components/demoParams";
import { formatDate, formatDateTime, joinChannels } from "../../_components/format";
import { fetchApi } from "../../_lib/api";

const RELATED_MATCHUP_ALIAS_BY_CANDIDATE = {
  "cand-jwo": "m_2026_seoul_mayor"
};

export default async function CandidatePage({ params, searchParams }) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const requestedCandidateId = resolvedParams.candidate_id;
  const fromSource = (resolvedSearch?.from || "").trim().toLowerCase();
  const fromMatchupId = (resolvedSearch?.matchup_id || "").trim();

  const partyDemo = (resolvedSearch?.party_demo || "").trim().toLowerCase();
  const confirmDemo = (resolvedSearch?.confirm_demo || "").trim().toLowerCase();

  const payload = await fetchApi(`/api/v1/candidates/${encodeURIComponent(requestedCandidateId)}`);

  let candidatePayload = payload;
  let fallbackApplied = false;

  if (!candidatePayload.ok) {
    const fallbackPayload = await fetchApi("/api/v1/candidates/cand-jwo");
    if (fallbackPayload.ok) {
      candidatePayload = fallbackPayload;
      fallbackApplied = true;
    }
  }

  if (!candidatePayload.ok) {
    return (
      <main className="detail-root">
        <section className="panel error-panel">
          <h1>후보 정보를 불러오지 못했습니다.</h1>
          <p>요청 ID: {requestedCandidateId}</p>
          <p>status: {candidatePayload.status}</p>
          <p className="muted-text">{JSON.stringify(candidatePayload.body)}</p>
          <Link href="/" className="text-link">
            대시보드로 이동
          </Link>
        </section>
      </main>
    );
  }

  const candidate = candidatePayload.body;
  const effectiveCandidateId = candidate.candidate_id;

  const relatedAlias =
    RELATED_MATCHUP_ALIAS_BY_CANDIDATE[effectiveCandidateId] ||
    RELATED_MATCHUP_ALIAS_BY_CANDIDATE[requestedCandidateId] ||
    "m_2026_seoul_mayor";
  const returnMatchupHref =
    fromSource === "matchup" && fromMatchupId
      ? `/matchups/${encodeURIComponent(fromMatchupId)}`
      : null;

  const relatedMatchup = await fetchApi(`/api/v1/matchups/${encodeURIComponent(relatedAlias)}`);

  const scenarioBadges = [];
  const scenarioCopies = [];

  if (partyDemo === "inferred_low") {
    scenarioBadges.push(toScenarioBadge("검수 필요", "warn"));
    scenarioCopies.push("정당 정보 신뢰도가 낮아 검수 필요 상태입니다.");
  }

  if (confirmDemo === "pending48") {
    scenarioBadges.push(toScenarioBadge("공식확정 대기(48시간)", "info"));
    scenarioCopies.push("공식확정 대기(48시간) 상태로 운영 정책상 재확인을 기다립니다.");
  }

  if (partyDemo) {
    scenarioBadges.push(
      toScenarioBadge(
        `party_demo=${partyDemo}`,
        partyDemo === "official" ? "ok" : partyDemo === "inferred" ? "warn" : "info"
      )
    );
  }
  if (confirmDemo) {
    scenarioBadges.push(
      toScenarioBadge(
        `confirm_demo=${confirmDemo}`,
        confirmDemo === "official" ? "ok" : confirmDemo === "article" ? "warn" : "info"
      )
    );
  }

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
          {returnMatchupHref ? (
            <Link href={returnMatchupHref} className="text-link">
              매치업으로 복귀
            </Link>
          ) : null}
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
          <span className="state-badge info">요청 후보 ID: {requestedCandidateId}</span>
          <span className="state-badge ok">표준 후보 ID: {effectiveCandidateId}</span>
          {scenarioBadges.map((badge) => (
            <span key={badge.text} className={`state-badge ${badge.tone}`}>
              {badge.text}
            </span>
          ))}
        </div>
        {fallbackApplied ? (
          <p className="scenario-copy">
            baseline 안전 fallback 적용: 요청 후보를 찾지 못해 <strong>{effectiveCandidateId}</strong> 기준으로 화면을 유지했습니다.
          </p>
        ) : null}
        {scenarioCopies.map((copy) => (
          <p key={copy} className="scenario-copy">
            {copy}
          </p>
        ))}
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
