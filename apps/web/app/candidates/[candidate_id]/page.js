import Link from "next/link";

import { toScenarioBadge } from "../../_components/demoParams";
import { formatDate, formatDateTime, joinChannels } from "../../_components/format";
import { fetchApi } from "../../_lib/api";

const RELATED_MATCHUP_ALIAS_BY_CANDIDATE = {
  "cand-jwo": "m_2026_seoul_mayor"
};

function hasValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

function applyStateDemo(candidate, stateDemo) {
  if (stateDemo === "empty") {
    return {
      ...candidate,
      party_name: null,
      party_inferred: true,
      party_inference_source: null,
      party_inference_confidence: null,
      gender: null,
      birth_date: null,
      job: null,
      career_summary: null,
      election_history: null,
      source_channel: null,
      source_channels: [],
      source_priority: null,
      official_release_at: null,
      article_published_at: null,
      freshness_hours: null,
      is_official_confirmed: false
    };
  }

  if (stateDemo === "partial") {
    return {
      ...candidate,
      birth_date: null,
      election_history: null,
      source_channels: Array.isArray(candidate.source_channels) ? candidate.source_channels : [],
      official_release_at: null
    };
  }

  return candidate;
}

function profileState(candidate, stateDemo) {
  if (stateDemo === "empty" || stateDemo === "partial" || stateDemo === "ready") return stateDemo;
  const affiliationReady = hasValue(candidate.party_name) || Boolean(candidate.party_inferred);
  const bioReady = hasValue(candidate.career_summary) || hasValue(candidate.job);
  const electionReady = hasValue(candidate.election_history);
  const sourceReady =
    hasValue(candidate.source_channel) ||
    hasValue(candidate.source_channels) ||
    hasValue(candidate.article_published_at) ||
    hasValue(candidate.official_release_at) ||
    Number.isFinite(Number(candidate.freshness_hours));

  const readyCount = [affiliationReady, bioReady, electionReady, sourceReady].filter(Boolean).length;
  if (readyCount === 0) return "empty";
  if (readyCount === 4) return "ready";
  return "partial";
}

function stateMeta(state) {
  if (state === "empty") {
    return {
      tone: "warn",
      badge: "프로필 없음",
      copy: "후보 기본 프로필이 아직 비어 있습니다. 출처 확보 후 자동 갱신됩니다."
    };
  }
  if (state === "partial") {
    return {
      tone: "info",
      badge: "부분 프로필",
      copy: "일부 필드만 확인되었습니다. 누락 필드는 검수 후 보강됩니다."
    };
  }
  return {
    tone: "ok",
    badge: "프로필 준비됨",
    copy: "핵심 프로필 필드가 준비된 상태입니다."
  };
}

export default async function CandidatePage({ params, searchParams }) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const requestedCandidateId = resolvedParams.candidate_id;
  const fromSource = (resolvedSearch?.from || "").trim().toLowerCase();
  const fromMatchupId = (resolvedSearch?.matchup_id || "").trim();

  const partyDemo = (resolvedSearch?.party_demo || "").trim().toLowerCase();
  const confirmDemo = (resolvedSearch?.confirm_demo || "").trim().toLowerCase();
  const stateDemo = (resolvedSearch?.state_demo || "").trim().toLowerCase();

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

  const candidateRaw = candidatePayload.body;
  const candidate = applyStateDemo(candidateRaw, stateDemo);
  const effectiveCandidateId = candidate.candidate_id;

  const relatedAlias =
    RELATED_MATCHUP_ALIAS_BY_CANDIDATE[effectiveCandidateId] ||
    RELATED_MATCHUP_ALIAS_BY_CANDIDATE[requestedCandidateId] ||
    "m_2026_seoul_mayor";
  const returnMatchupHref = fromSource === "matchup" && fromMatchupId ? `/matchups/${encodeURIComponent(fromMatchupId)}` : null;

  const primaryLookupId = fromMatchupId || relatedAlias;
  let relatedMatchup = await fetchApi(`/api/v1/matchups/${encodeURIComponent(primaryLookupId)}`);
  if (!relatedMatchup.ok && primaryLookupId !== relatedAlias) {
    relatedMatchup = await fetchApi(`/api/v1/matchups/${encodeURIComponent(relatedAlias)}`);
  }

  const derivedState = profileState(candidate, stateDemo);
  const stateInfo = stateMeta(derivedState);
  const sourceChannels = Array.isArray(candidate.source_channels) ? candidate.source_channels : [];

  const scenarioBadges = [toScenarioBadge(stateInfo.badge, stateInfo.tone)];
  const scenarioCopies = [stateInfo.copy];

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
      toScenarioBadge(`party_demo=${partyDemo}`, partyDemo === "official" ? "ok" : partyDemo === "inferred" ? "warn" : "info")
    );
  }
  if (confirmDemo) {
    scenarioBadges.push(
      toScenarioBadge(`confirm_demo=${confirmDemo}`, confirmDemo === "official" ? "ok" : confirmDemo === "article" ? "warn" : "info")
    );
  }
  if (stateDemo) {
    scenarioBadges.push(toScenarioBadge(`state_demo=${stateDemo}`, stateDemo === "ready" ? "ok" : "info"));
  }

  return (
    <main className="detail-root">
      <section className="panel">
        <h3>이동 경로</h3>
        <div className="badge-row">
          <span className="state-badge info">{returnMatchupHref ? "매치업에서 진입" : "직접 진입"}</span>
          {fromMatchupId ? <span className="state-badge info">matchup_id: {fromMatchupId}</span> : null}
        </div>
        <div className="hero-actions" style={{ marginTop: "8px" }}>
          {returnMatchupHref ? (
            <Link href={returnMatchupHref} className="text-link">
              이전 화면으로
            </Link>
          ) : null}
          <Link href="/" className="text-link">
            대시보드
          </Link>
          <Link href="/search" className="text-link">
            지역 검색
          </Link>
        </div>
      </section>

      <section className="panel detail-hero">
        <div>
          <p className="kicker">CANDIDATE DETAIL</p>
          <h1>{candidate.name_ko}</h1>
          <p>
            {candidate.party_name || "정당 미상"} · {candidate.job || "직업 정보 없음"}
          </p>
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
          <h3>소속 / 확정 상태</h3>
          <dl className="meta-grid">
            <dt>candidate_id</dt>
            <dd>{candidate.candidate_id}</dd>
            <dt>정당</dt>
            <dd>{candidate.party_name || "-"}</dd>
            <dt>정당 추정</dt>
            <dd>{candidate.party_inferred ? "추정" : "공식"}</dd>
            <dt>정당 근거</dt>
            <dd>{candidate.party_inference_source || "-"}</dd>
            <dt>정당 신뢰도</dt>
            <dd>{candidate.party_inference_confidence ?? "-"}</dd>
            <dt>공식확정</dt>
            <dd>{candidate.is_official_confirmed ? "확정" : "대기"}</dd>
          </dl>
        </article>

        <article className="panel">
          <h3>출처 / 신선도 패널</h3>
          <dl className="meta-grid">
            <dt>출처 채널</dt>
            <dd>{joinChannels(sourceChannels)}</dd>
            <dt>source_priority</dt>
            <dd>{candidate.source_priority || "-"}</dd>
            <dt>공식 공개시각</dt>
            <dd>{formatDateTime(candidate.official_release_at)}</dd>
            <dt>기사 게시시각</dt>
            <dd>{formatDateTime(candidate.article_published_at)}</dd>
            <dt>신선도(시간)</dt>
            <dd>{Number.isFinite(Number(candidate.freshness_hours)) ? `${Number(candidate.freshness_hours).toFixed(1)}h` : "-"}</dd>
          </dl>
        </article>

        <article className="panel">
          <h3>약력 / 출마 정보 (MVP 최소필드)</h3>
          {derivedState === "empty" ? (
            <div className="empty-state">약력/출마 정보가 없습니다. 후보 식별 정보만 우선 노출합니다.</div>
          ) : (
            <dl className="meta-grid">
              <dt>성별</dt>
              <dd>{candidate.gender || "-"}</dd>
              <dt>생년월일</dt>
              <dd>{formatDate(candidate.birth_date)}</dd>
              <dt>직업</dt>
              <dd>{candidate.job || "-"}</dd>
              <dt>약력 요약</dt>
              <dd>{candidate.career_summary || "-"}</dd>
              <dt>선거 이력</dt>
              <dd>{candidate.election_history || "-"}</dd>
            </dl>
          )}
          {derivedState === "partial" ? (
            <p className="scenario-copy">누락 필드(예: 생년월일/선거이력)는 수집 후 자동 보강됩니다.</p>
          ) : null}
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
              <Link href={`/matchups/${encodeURIComponent(relatedMatchup.body.matchup_id || relatedAlias)}`} className="text-link small">
                매치업 상세 보기
              </Link>
            </div>
          ) : (
            <>
              <div className="empty-state">MVP에서는 후보 상세와 매치업 자동 연결 API가 아직 없습니다.</div>
              <Link href="/search" className="text-link small">
                지역 검색에서 관련 매치업 찾기
              </Link>
            </>
          )}
        </article>
      </section>
    </main>
  );
}
