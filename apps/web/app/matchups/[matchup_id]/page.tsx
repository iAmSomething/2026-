"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api/endpoints";
import type { MatchupResponse } from "@/lib/types/api";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StateHint } from "@/components/ui/StateHint";
import { formatDate } from "@/lib/format/date";
import { freshnessLabel, freshnessTone } from "@/lib/format/freshness";
import {
  enrichedDescription,
  enrichedLabel,
  enrichedTone,
  inferenceBadgeLabel,
  inferenceBadgeTone,
  inferenceDescription,
  isInferredDate,
  reviewDescription,
  reviewLabel,
  reviewTone
} from "@/lib/format/inference_enrichment";
import {
  needsPartyReview,
  partyInferenceBadgeLabel,
  partyInferenceBadgeTone,
  partyInferenceDescription
} from "@/lib/format/party_inference";
import { formatPercentRange } from "@/lib/format/percent";
import {
  confirmationDescription,
  confirmationLabel,
  confirmationTone,
  resolveConfirmationBadge,
  sourcePriorityLabel
} from "@/lib/format/source_freshness";
import {
  provenanceDescription,
  provenanceLabel,
  provenanceTone,
  resolveProvenanceBadge
} from "@/lib/format/provenance";
import {
  completenessDescription,
  completenessLabel,
  resolveAudienceScope,
  resolveCompletenessLevel,
  scopeDescription,
  scopeDisplayLabel,
  scopeLabel,
  scopeTone
} from "@/lib/format/scope_completeness";

type LoadState = "loading" | "ready" | "empty" | "error";
type DemoState = "ready" | "partial" | "empty" | null;
type SourceDemo = "article" | "nesdc" | "multi" | "unknown" | null;
type StatusDemo = "all" | "inferred" | "enriched" | "review" | "clean" | null;
type PartyDemo = "inferred_low" | "inferred_high" | "confirmed" | null;
type ConfirmDemo = "official" | "pending24" | "pending48" | "article" | null;
type MetadataRow = {
  label: string;
  value: string;
  mobileValue?: string;
};

const OFFICE_LABELS: Record<string, string> = {
  metro_mayor: "광역자치단체장",
  metro_council: "광역의회",
  superintendent: "교육감",
  local_mayor: "기초자치단체장",
  local_council: "기초의회",
  by_election: "재보궐"
};

const SIDO_LABELS: Record<string, string> = {
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

function fallbackText(value: string | number | null | undefined, fallback = "미제공(수집 대기)"): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string") return value.trim() ? value : fallback;
  return String(value);
}

function fallbackTextCompact(value: string | number | null | undefined, fallback = "미제공"): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string") return value.trim() ? value : fallback;
  return String(value);
}

function formatResponseRate(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return "미제공(수집 대기)";
  if (typeof value === "number") return `${value}%`;
  return value.trim() ? value : "미제공(수집 대기)";
}

function formatResponseRateCompact(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return "미제공";
  if (typeof value === "number") return `${value}%`;
  return value.trim() ? value : "미제공";
}

function formatSurveyPeriod(start: string | null | undefined, end: string | null | undefined): string {
  const startText = start ? formatDate(start) : null;
  const endText = end ? formatDate(end) : null;
  if (startText && endText) return `${startText} ~ ${endText}`;
  if (endText) return endText;
  if (startText) return startText;
  return "미제공(수집 대기)";
}

function officeTypeLabel(officeType: string | null | undefined): string {
  if (!officeType) return "선거유형 미상";
  return OFFICE_LABELS[officeType] ?? officeType;
}

function regionLabelFromCode(regionCode: string | null | undefined): string {
  if (!regionCode) return "지역 미상";
  const prefixMatch = regionCode.match(/^KR-\d{2}/);
  const prefix = prefixMatch ? prefixMatch[0] : null;
  const sido = prefix ? SIDO_LABELS[prefix] : null;
  if (!sido) return regionCode;
  if (/^KR-\d{2}-000$/.test(regionCode)) return sido;
  if (/^KR-\d{2}$/.test(regionCode)) return sido;
  return `${sido} (${regionCode})`;
}

function canonicalMatchupTitle(officeType: string | null | undefined, regionCode: string | null | undefined): string {
  return `${regionLabelFromCode(regionCode)} ${officeTypeLabel(officeType)}`;
}

function applyDemoState(
  data: MatchupResponse,
  demoState: DemoState,
  sourceDemo: SourceDemo,
  statusDemo: StatusDemo,
  partyDemo: PartyDemo,
  confirmDemo: ConfirmDemo
): MatchupResponse {
  const withSourceDemo = (() => {
    if (!sourceDemo) return data;
    if (sourceDemo === "unknown") {
      return {
        ...data,
        latest_poll: {
          ...data.latest_poll,
          source_channel: null,
          source_channels: []
        }
      };
    }
    if (sourceDemo === "multi") {
      return {
        ...data,
        latest_poll: {
          ...data.latest_poll,
          source_channel: "article",
          source_channels: ["article", "nesdc"]
        }
      };
    }
    return {
      ...data,
      latest_poll: {
        ...data.latest_poll,
        source_channel: sourceDemo,
        source_channels: [sourceDemo]
      }
    };
  })();

  const withStatusDemo = (() => {
    if (!statusDemo) return withSourceDemo;
    const base = {
      ...withSourceDemo,
      latest_poll: {
        ...withSourceDemo.latest_poll
      }
    };
    if (statusDemo === "clean") {
      return {
        ...base,
        latest_poll: {
          ...base.latest_poll,
          date_inference_mode: "exact",
          date_inference_confidence: 1.0,
          nesdc_enriched: false,
          needs_manual_review: false
        }
      };
    }
    if (statusDemo === "inferred") {
      return {
        ...base,
        latest_poll: {
          ...base.latest_poll,
          date_inference_mode: "inferred_relative",
          date_inference_confidence: 0.71,
          nesdc_enriched: false,
          needs_manual_review: false
        }
      };
    }
    if (statusDemo === "enriched") {
      return {
        ...base,
        latest_poll: {
          ...base.latest_poll,
          date_inference_mode: "exact",
          date_inference_confidence: 1.0,
          nesdc_enriched: true,
          needs_manual_review: false
        }
      };
    }
    if (statusDemo === "review") {
      return {
        ...base,
        latest_poll: {
          ...base.latest_poll,
          date_inference_mode: "exact",
          date_inference_confidence: 1.0,
          nesdc_enriched: false,
          needs_manual_review: true
        }
      };
    }
    return {
      ...base,
      latest_poll: {
        ...base.latest_poll,
        date_inference_mode: "inferred_relative",
        date_inference_confidence: 0.62,
        nesdc_enriched: true,
        needs_manual_review: true
      }
    };
  })();

  const withPartyDemo = (() => {
    if (!partyDemo) return withStatusDemo;
    const enrichOption = (option: MatchupResponse["latest_poll"]["options"][number]) => {
      if (partyDemo === "confirmed") {
        return {
          ...option,
          party_name: option.party_name ?? "정당확정",
          party_inferred: false,
          party_inference_source: "already_present",
          party_inference_confidence: 1.0
        };
      }
      if (partyDemo === "inferred_high") {
        return {
          ...option,
          party_name: option.party_name ?? "무소속(추정)",
          party_inferred: true,
          party_inference_source: "article_context",
          party_inference_confidence: 0.84
        };
      }
      return {
        ...option,
        party_name: option.party_name ?? "무소속(추정)",
        party_inferred: true,
        party_inference_source: "article_context",
        party_inference_confidence: 0.51
      };
    };
    return {
      ...withStatusDemo,
      latest_poll: {
        ...withStatusDemo.latest_poll,
        options: (withStatusDemo.latest_poll.options ?? []).map(enrichOption)
      }
    };
  })();

  const withConfirmDemo = (() => {
    if (!confirmDemo) return withPartyDemo;
    if (confirmDemo === "official") {
      return {
        ...withPartyDemo,
        latest_poll: {
          ...withPartyDemo.latest_poll,
          source_priority: "official" as const,
          is_official_confirmed: true,
          freshness_hours: 4,
          official_release_at: "2026-02-19T09:00:00+09:00",
          article_published_at: "2026-02-19T05:00:00+09:00"
        }
      };
    }
    if (confirmDemo === "pending24") {
      return {
        ...withPartyDemo,
        latest_poll: {
          ...withPartyDemo.latest_poll,
          source_priority: "mixed" as const,
          is_official_confirmed: false,
          freshness_hours: 18,
          official_release_at: null,
          article_published_at: "2026-02-19T08:00:00+09:00"
        }
      };
    }
    if (confirmDemo === "pending48") {
      return {
        ...withPartyDemo,
        latest_poll: {
          ...withPartyDemo.latest_poll,
          source_priority: "mixed" as const,
          is_official_confirmed: false,
          freshness_hours: 34,
          official_release_at: null,
          article_published_at: "2026-02-18T16:00:00+09:00"
        }
      };
    }
    return {
      ...withPartyDemo,
      latest_poll: {
        ...withPartyDemo.latest_poll,
        source_priority: "article" as const,
        is_official_confirmed: false,
        freshness_hours: 72,
        official_release_at: null,
        article_published_at: "2026-02-16T10:00:00+09:00"
      }
    };
  })();

  if (!demoState || demoState === "ready") return withConfirmDemo;

  if (demoState === "empty") {
    return {
      ...withConfirmDemo,
      latest_poll: {
        ...withConfirmDemo.latest_poll,
        legal_required_count: 11,
        legal_filled_count: 0,
        legal_completeness_score: 0,
        options: []
      },
      trend: [],
      polls: []
    };
  }

  return {
    ...withConfirmDemo,
    latest_poll: {
      ...withConfirmDemo.latest_poll,
      audience_scope: "local",
      audience_region_code: withConfirmDemo.matchup.region_code,
      sampling_population_text: "해당 지역 거주 만 18세 이상",
      response_rate: null,
      survey_method: null,
      legal_required_count: 11,
      legal_filled_count: 6,
      legal_completeness_score: 0.55
    },
    trend: (data.trend ?? []).slice(0, 2),
    polls: (data.polls ?? []).slice(0, 1)
  };
}

export default function MatchupPage() {
  const params = useParams<{ matchup_id: string }>();
  const searchParams = useSearchParams();
  const matchupId = params?.matchup_id || "";
  const demoState = (() => {
    const value = searchParams?.get("demo_state");
    if (value === "ready" || value === "partial" || value === "empty") return value;
    return null;
  })();
  const sourceDemo = (() => {
    const value = searchParams?.get("source_demo");
    if (value === "article" || value === "nesdc" || value === "multi" || value === "unknown") return value;
    return null;
  })();
  const statusDemo = (() => {
    const value = searchParams?.get("status_demo");
    if (value === "all" || value === "inferred" || value === "enriched" || value === "review" || value === "clean") {
      return value;
    }
    return null;
  })();
  const partyDemo = (() => {
    const value = searchParams?.get("party_demo");
    if (value === "inferred_low" || value === "inferred_high" || value === "confirmed") return value;
    return null;
  })();
  const confirmDemo = (() => {
    const value = searchParams?.get("confirm_demo");
    if (value === "official" || value === "pending24" || value === "pending48" || value === "article") return value;
    return null;
  })();
  const fromFlow = (() => {
    const value = searchParams?.get("from");
    if (value === "map" || value === "search" || value === "candidate") return value;
    return null;
  })();
  const fromRegionCode = searchParams?.get("region_code") || null;
  const fromOfficeType = searchParams?.get("office_type") || null;
  const compactMode = searchParams?.get("mobile_compact") !== "0";
  const fromLabel = fromFlow === "map" ? "지도" : fromFlow === "search" ? "검색" : fromFlow === "candidate" ? "후보 상세" : null;
  const returnHref = fromFlow === "map" ? "/" : fromFlow === "search" ? "/search" : fromFlow === "candidate" ? "/candidates/cand-jwo" : null;

  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<MatchupResponse | null>(null);

  const trendRows = useMemo(() => data?.trend ?? [], [data]);
  const pollRows = useMemo(() => data?.polls ?? [], [data]);

  const load = async () => {
    if (!matchupId) return;
    setState("loading");
    try {
      const res = await api.matchup(matchupId);
      const prepared = applyDemoState(res, demoState, sourceDemo, statusDemo, partyDemo, confirmDemo);
      setData(prepared);
      const hasOptions = (prepared.latest_poll?.options?.length ?? 0) > 0;
      setState(hasOptions ? "ready" : "empty");
    } catch {
      setState("error");
    }
  };

  useEffect(() => {
    void load();
  }, [matchupId, demoState, sourceDemo, statusDemo, partyDemo, confirmDemo]);

  if (state === "loading") {
    return (
      <div className="space-y-3">
        <StateHint tone="loading" title="매치업 데이터를 불러오는 중입니다." description="최신 조사 결과를 정리하고 있습니다." />
        <Skeleton className="h-40" />
        <Skeleton className="h-28" />
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="space-y-3">
        <ErrorState message="매치업 데이터를 불러오지 못했습니다." />
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md bg-slate-700 px-3 py-2 text-xs font-semibold text-white"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (state === "empty" || !data) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <p className="font-semibold">해당 매치업 데이터가 아직 없습니다.</p>
        <p className="mt-1">지역 검색에서 다른 선거를 먼저 확인해 주세요.</p>
        <Link href="/search" className="mt-3 inline-block rounded-md bg-amber-700 px-3 py-2 text-xs font-semibold text-white">
          지역 검색하기
        </Link>
      </div>
    );
  }

  const optionCount = data.latest_poll.options.length;
  const pollCount = pollRows.length;
  const trendCount = trendRows.length;
  const scope = resolveAudienceScope({
    audience_scope: data.latest_poll.audience_scope,
    office_type: data.matchup.office_type,
    region_code: data.matchup.region_code
  });
  const completenessLevel = resolveCompletenessLevel({
    legal_required_count: data.latest_poll.legal_required_count,
    legal_filled_count: data.latest_poll.legal_filled_count,
    legal_completeness_score: data.latest_poll.legal_completeness_score
  });
  const provenanceBadge = resolveProvenanceBadge({
    source_channel: data.latest_poll.source_channel,
    source_channels: data.latest_poll.source_channels
  });
  const confirmationBadge = resolveConfirmationBadge({
    source_priority: data.latest_poll.source_priority,
    freshness_hours: data.latest_poll.freshness_hours,
    is_official_confirmed: data.latest_poll.is_official_confirmed
  });
  const inferredDate = isInferredDate(data.latest_poll.date_inference_mode);
  const nesdcEnriched = Boolean(data.latest_poll.nesdc_enriched);
  const needsManualReview = Boolean(data.latest_poll.needs_manual_review);
  const partialData =
    completenessLevel !== "compliant" ||
    pollCount < 2 ||
    trendCount < 4 ||
    data.latest_poll.margin_of_error === null;
  const metadataRows: MetadataRow[] = [
    { label: "조사기관", value: fallbackText(data.latest_poll.pollster) },
    {
      label: "조사기간",
      value: formatSurveyPeriod(data.latest_poll.survey_start_date, data.latest_poll.survey_end_date)
    },
    { label: "표본수", value: `${data.latest_poll.sample_size}명` },
    {
      label: "응답률",
      value: formatResponseRate(data.latest_poll.response_rate),
      mobileValue: formatResponseRateCompact(data.latest_poll.response_rate)
    },
    {
      label: "표본오차",
      value: data.latest_poll.margin_of_error !== null ? `±${data.latest_poll.margin_of_error}%p` : "미제공(수집 대기)",
      mobileValue: data.latest_poll.margin_of_error !== null ? `±${data.latest_poll.margin_of_error}%p` : "미제공"
    },
    {
      label: "조사방법",
      value: fallbackText(data.latest_poll.survey_method),
      mobileValue: fallbackTextCompact(data.latest_poll.survey_method)
    },
    {
      label: "모집단/범위",
      value: fallbackText(data.latest_poll.sampling_population_text),
      mobileValue: fallbackTextCompact(data.latest_poll.sampling_population_text)
    },
    {
      label: "법정필수항목",
      value: `${fallbackText(data.latest_poll.legal_filled_count, "-")}/${fallbackText(
        data.latest_poll.legal_required_count,
        "-"
      )} (score ${fallbackText(data.latest_poll.legal_completeness_score, "-")})`,
      mobileValue: `${fallbackText(data.latest_poll.legal_filled_count, "-")}/${fallbackText(data.latest_poll.legal_required_count, "-")}`
    },
    { label: "일자추정모드", value: fallbackText(data.latest_poll.date_inference_mode, "exact") },
    { label: "일자추정신뢰도", value: fallbackText(data.latest_poll.date_inference_confidence, "-") },
    { label: "출처 우선순위", value: sourcePriorityLabel(data.latest_poll.source_priority) },
    { label: "신선도(시간)", value: fallbackText(data.latest_poll.freshness_hours, "-") },
    {
      label: "공식 공개시각",
      value: fallbackText(data.latest_poll.official_release_at, "-"),
      mobileValue: fallbackTextCompact(data.latest_poll.official_release_at, "미제공")
    },
    {
      label: "기사 게시시각",
      value: fallbackText(data.latest_poll.article_published_at, "-"),
      mobileValue: fallbackTextCompact(data.latest_poll.article_published_at, "미제공")
    },
    {
      label: "비교 기준 스코프",
      value: scope === "national" ? "전국 지표와 비교 가능" : `${scopeLabel(scope)} 기준 비교만 권장`
    }
  ];
  const verboseTextClass = compactMode ? "hidden text-xs text-slate-600 md:block" : "text-xs text-slate-600";
  const verboseTextClassMt = compactMode ? "mt-1 hidden text-xs text-slate-600 md:block" : "mt-1 text-xs text-slate-600";
  const canonicalTitle = canonicalMatchupTitle(data.matchup.office_type, data.matchup.region_code);
  const articleHeadline = fallbackTextCompact(data.matchup.title, "기사 제목 미제공");
  const surveyPeriod = formatSurveyPeriod(data.latest_poll.survey_start_date, data.latest_poll.survey_end_date);

  return (
    <div className="space-y-4">
      <Card title={`매치업: ${canonicalTitle}`}>
        {fromFlow ? (
          <div className="mb-2 rounded-lg border border-slate-200 bg-white p-2 text-xs text-slate-700">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">{`${fromLabel}에서 진입`}</Badge>
              <Badge tone="neutral">{`기준 제목: ${canonicalTitle}`}</Badge>
              {fromRegionCode ? <Badge tone="neutral">{`유입 지역: ${regionLabelFromCode(fromRegionCode)}`}</Badge> : null}
              {fromOfficeType ? <Badge tone="neutral">{`유입 선거유형: ${officeTypeLabel(fromOfficeType)}`}</Badge> : null}
              {returnHref ? (
                <Link href={returnHref} className="font-semibold text-teal-700 underline">
                  이전 화면으로
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
        <div className="mb-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
          <p className="font-semibold text-slate-800">{`기사 제목: ${articleHeadline}`}</p>
          <p className="mt-1">{`출처: ${fallbackText(data.latest_poll.pollster)} / 조사기간: ${surveyPeriod}`}</p>
        </div>
        <div className="mb-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700" aria-live="polite">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={freshnessTone(data.latest_poll.survey_end_date)}>{freshnessLabel(data.latest_poll.survey_end_date)}</Badge>
            <Badge tone={provenanceTone(provenanceBadge)}>{provenanceLabel(provenanceBadge)}</Badge>
            <Badge tone={confirmationTone(confirmationBadge)}>{confirmationLabel(confirmationBadge)}</Badge>
            <span title={inferenceDescription(data.latest_poll.date_inference_mode, data.latest_poll.date_inference_confidence)}>
              <Badge tone={inferenceBadgeTone(data.latest_poll.date_inference_mode)}>
                {inferenceBadgeLabel(data.latest_poll.date_inference_mode)}
              </Badge>
            </span>
            <span title={enrichedDescription(data.latest_poll.nesdc_enriched)}>
              <Badge tone={enrichedTone(data.latest_poll.nesdc_enriched)}>{enrichedLabel(data.latest_poll.nesdc_enriched)}</Badge>
            </span>
            <span title={reviewDescription(data.latest_poll.needs_manual_review)}>
              <Badge tone={reviewTone(data.latest_poll.needs_manual_review)}>
                {reviewLabel(data.latest_poll.needs_manual_review)}
              </Badge>
            </span>
            <Badge tone={scopeTone(scope)}>{scopeDisplayLabel(scope)}</Badge>
            <Badge tone={scope === "national" ? "ok" : "warn"}>{scope === "national" ? "전국 비교 가능" : "동일 스코프 비교 권장"}</Badge>
            <Badge tone={completenessLevel === "compliant" ? "ok" : "warn"}>{completenessLabel(completenessLevel)}</Badge>
            <Badge tone="neutral">{`커버리지 옵션 ${optionCount}명 / 원자료 ${pollCount}건`}</Badge>
            {partialData ? <Badge tone="warn">부분 데이터</Badge> : null}
          </div>
          {partialData ? <p className="mt-1 text-amber-700">원자료 수가 제한적이어서 해석에 주의가 필요합니다.</p> : null}
        </div>
        <div className="space-y-1 text-sm text-slate-700">
          <p>
            표준 선거명: {canonicalTitle}
          </p>
          <p>
            표본 {data.latest_poll.sample_size}명 / 오차범위 ±
            {data.latest_poll.margin_of_error ?? "-"}%p / 등급 {data.latest_poll.source_grade}
          </p>
          <Link
            href={data.latest_poll.source_url}
            target="_blank"
            className="inline-block text-xs font-semibold text-teal-700 underline"
          >
            출처 기사 링크
          </Link>
          {compactMode ? (
            <p className="text-xs text-slate-600 md:hidden">
              {`모바일 요약: ${provenanceLabel(provenanceBadge)} · ${confirmationLabel(confirmationBadge)} · ${completenessLabel(
                completenessLevel
              )}`}
            </p>
          ) : null}
          <p className={verboseTextClass}>
            {scopeDescription({
              scope,
              audience_region_code: data.latest_poll.audience_region_code,
              sampling_population_text: data.latest_poll.sampling_population_text
            })}
          </p>
          <p className={verboseTextClass}>
            {scope === "national"
              ? "비교 안내: 전국 지표 간 비교가 가능합니다."
              : `비교 안내: ${scopeLabel(scope)} 기준 데이터로, 전국 지표와 직접 비교 해석은 주의가 필요합니다.`}
          </p>
          <p className={verboseTextClass}>{provenanceDescription(provenanceBadge)}</p>
          <p className={verboseTextClass}>
            {confirmationDescription({
              badge: confirmationBadge,
              source_priority: data.latest_poll.source_priority,
              freshness_hours: data.latest_poll.freshness_hours,
              official_release_at: data.latest_poll.official_release_at
            })}
          </p>
          <p className={verboseTextClass}>
            {inferenceDescription(data.latest_poll.date_inference_mode, data.latest_poll.date_inference_confidence)}
          </p>
          <p className={verboseTextClass}>{enrichedDescription(data.latest_poll.nesdc_enriched)}</p>
          <p className={verboseTextClass}>{reviewDescription(data.latest_poll.needs_manual_review)}</p>
          <p className={verboseTextClass}>
            {completenessDescription({
              legal_required_count: data.latest_poll.legal_required_count,
              legal_filled_count: data.latest_poll.legal_filled_count,
              legal_completeness_score: data.latest_poll.legal_completeness_score
            })}
          </p>
        </div>
      </Card>

      <Card title="조사 상세 메타데이터 패널">
        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={provenanceTone(provenanceBadge)}>{provenanceLabel(provenanceBadge)}</Badge>
            <Badge tone={confirmationTone(confirmationBadge)}>{confirmationLabel(confirmationBadge)}</Badge>
            <Badge tone={inferenceBadgeTone(data.latest_poll.date_inference_mode)}>
              {inferenceBadgeLabel(data.latest_poll.date_inference_mode)}
            </Badge>
            <Badge tone={enrichedTone(data.latest_poll.nesdc_enriched)}>{enrichedLabel(data.latest_poll.nesdc_enriched)}</Badge>
            <Badge tone={reviewTone(data.latest_poll.needs_manual_review)}>{reviewLabel(data.latest_poll.needs_manual_review)}</Badge>
            <Badge tone={completenessLevel === "compliant" ? "ok" : "warn"}>{completenessLabel(completenessLevel)}</Badge>
          </div>
          {compactMode ? (
            <p className="mt-1 text-xs text-slate-600 md:hidden">
              {`모바일 요약: ${provenanceLabel(provenanceBadge)} · ${confirmationLabel(confirmationBadge)} · ${completenessLabel(
                completenessLevel
              )}`}
            </p>
          ) : null}
          <p className={verboseTextClassMt}>{provenanceDescription(provenanceBadge)}</p>
          <p className={verboseTextClassMt}>
            {confirmationDescription({
              badge: confirmationBadge,
              source_priority: data.latest_poll.source_priority,
              freshness_hours: data.latest_poll.freshness_hours,
              official_release_at: data.latest_poll.official_release_at
            })}
          </p>
          <p className={verboseTextClassMt}>
            {inferenceDescription(data.latest_poll.date_inference_mode, data.latest_poll.date_inference_confidence)}
          </p>
          <p className={verboseTextClassMt}>{enrichedDescription(data.latest_poll.nesdc_enriched)}</p>
          <p className={verboseTextClassMt}>{reviewDescription(data.latest_poll.needs_manual_review)}</p>
          <p className={verboseTextClassMt}>
            {completenessDescription({
              legal_required_count: data.latest_poll.legal_required_count,
              legal_filled_count: data.latest_poll.legal_filled_count,
              legal_completeness_score: data.latest_poll.legal_completeness_score
            })}
          </p>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {metadataRows.map((row) => (
            <div key={row.label} className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs font-semibold text-slate-500">{row.label}</p>
              <p className="mt-1 text-xs text-slate-900 md:hidden">{compactMode ? row.mobileValue ?? row.value : row.value}</p>
              <p className="mt-1 hidden break-words text-sm text-slate-900 md:block">{row.value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3">
          <Link
            href={data.latest_poll.source_url}
            target="_blank"
            className="inline-block text-xs font-semibold text-teal-700 underline"
          >
            출처 원문 링크
          </Link>
        </div>
        {inferredDate || nesdcEnriched || needsManualReview ? (
          <p className="mt-2 text-xs text-amber-700">
            상태 배지(추정/보강/검수 상태)는 데이터 수집 파이프라인의 자동 판별 결과이며, QA 검수로 변경될 수 있습니다.
          </p>
        ) : null}
      </Card>

      <Card title="최신 스냅샷">
        <div className="space-y-2">
          {data.latest_poll.options.map((option) => (
            <div key={option.option_name} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
              <div className="flex items-start justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold text-slate-800">{option.option_name}</p>
                  <span
                    title={partyInferenceDescription({
                      inferred: option.party_inferred,
                      source: option.party_inference_source,
                      confidence: option.party_inference_confidence
                    })}
                  >
                    <Badge tone={partyInferenceBadgeTone(option.party_inferred)}>
                      {partyInferenceBadgeLabel(option.party_inferred)}
                    </Badge>
                  </span>
                  {needsPartyReview({
                    inferred: option.party_inferred,
                    confidence: option.party_inference_confidence
                  }) ? (
                    <Badge tone="warn">검수 필요</Badge>
                  ) : (
                    <Badge tone="ok">검수 완료</Badge>
                  )}
                </div>
                {option.candidate_id ? (
                  <Link
                    href={`/candidates/${encodeURIComponent(option.candidate_id)}?from=matchup&matchup_id=${encodeURIComponent(matchupId)}`}
                    className="rounded-md border border-teal-700 bg-white px-2 py-1 text-xs font-semibold text-teal-700"
                  >
                    프로필
                  </Link>
                ) : (
                  <button
                    type="button"
                    disabled
                    className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-400"
                    aria-disabled="true"
                  >
                    프로필 준비중
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-600">
                정당: {fallbackText(option.party_name)}
                {option.party_inferred ? " (추정)" : ""}
              </p>
              {needsPartyReview({
                inferred: option.party_inferred,
                confidence: option.party_inference_confidence
              }) ? (
                <p className="text-xs text-amber-700">정당 추정 신뢰도가 낮아 검수 대기 상태입니다.</p>
              ) : null}
              <p className="text-slate-700">
                {formatPercentRange(option.value_mid, option.value_min, option.value_max, option.value_raw)}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <Card title="추세 원자료 포인트">
        {trendRows.length === 0 ? (
          <p className="text-sm text-slate-600">추세 포인트가 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-600">
                  <th className="py-2">일자</th>
                  <th className="py-2">후보</th>
                  <th className="py-2">값</th>
                  <th className="py-2">poll_id</th>
                </tr>
              </thead>
              <tbody>
                {trendRows.map((row) => (
                  <tr key={`${row.poll_id}-${row.option_name}`} className="border-b border-slate-100">
                    <td className="py-2">{formatDate(row.survey_end_date)}</td>
                    <td className="py-2">{row.option_name}</td>
                    <td className="py-2">{row.value_mid ?? "-"}</td>
                    <td className="py-2 text-xs text-slate-500">{row.poll_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="원자료 테이블">
        {pollRows.length === 0 ? (
          <p className="text-sm text-slate-600">원자료 목록이 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-600">
                  <th className="py-2">조사기관</th>
                  <th className="py-2">종료일</th>
                  <th className="py-2">표본</th>
                  <th className="py-2">오차</th>
                  <th className="py-2">출처</th>
                </tr>
              </thead>
              <tbody>
                {pollRows.map((poll) => (
                  <tr key={poll.poll_id} className="border-b border-slate-100">
                    <td className="py-2">{poll.pollster}</td>
                    <td className="py-2">{formatDate(poll.survey_end_date)}</td>
                    <td className="py-2">{poll.sample_size}</td>
                    <td className="py-2">±{poll.margin_of_error ?? "-"}%p</td>
                    <td className="py-2">
                      <Link href={poll.source_url} target="_blank" className="text-xs font-semibold text-teal-700 underline">
                        링크
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
