from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RegionOut(BaseModel):
    region_code: str
    sido_name: str
    sigungu_name: str
    admin_level: str
    has_data: bool = False
    matchup_count: int = 0


class CandidateOut(BaseModel):
    candidate_id: str
    name_ko: str
    party_name: str | None = None
    party_inferred: bool = False
    party_inference_source: Literal["name_rule", "article_context", "manual"] | None = None
    party_inference_confidence: float | None = None
    needs_manual_review: bool = False
    source_channel: Literal["article", "nesdc"] | None = None
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list)
    source_priority: Literal["official", "article", "mixed"] = "article"
    official_release_at: datetime | None = None
    article_published_at: datetime | None = None
    freshness_hours: float | None = None
    is_official_confirmed: bool = False
    gender: str | None = None
    birth_date: date | None = None
    job: str | None = None
    career_summary: str | None = None
    election_history: str | None = None
    profile_source: Literal["data_go", "ingest", "mixed", "none"] = "none"
    profile_completeness: Literal["complete", "partial", "empty"] = "empty"
    profile_provenance: dict[
        Literal["party_name", "gender", "birth_date", "job", "career_summary", "election_history"],
        Literal["data_go", "ingest", "missing"],
    ] = Field(default_factory=dict)
    profile_source_type: str | None = None
    profile_source_url: str | None = None
    placeholder_name_applied: bool = False


class SourceTraceOut(BaseModel):
    source_priority: Literal["official", "article", "mixed"] = "article"
    source_channel: Literal["article", "nesdc"] | None = None
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list)
    selected_source_tier: Literal["official", "nesdc", "article_aggregate", "article"] | None = None
    selected_source_channel: str | None = None
    official_release_at: datetime | None = None
    article_published_at: datetime | None = None
    freshness_hours: float | None = None
    is_official_confirmed: bool = False


class SummaryPoint(BaseModel):
    option_name: str
    value_mid: float | None = None
    pollster: str | None = None
    survey_end_date: date | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    source_priority: Literal["official", "article", "mixed"] = Field(default="article", deprecated=True)
    selected_source_tier: Literal["official", "nesdc", "article_aggregate", "article"] | None = Field(
        default=None,
        deprecated=True,
    )
    selected_source_channel: str | None = Field(default=None, deprecated=True)
    official_release_at: datetime | None = Field(default=None, deprecated=True)
    article_published_at: datetime | None = Field(default=None, deprecated=True)
    freshness_hours: float | None = Field(default=None, deprecated=True)
    is_official_confirmed: bool = Field(default=False, deprecated=True)
    source_channel: Literal["article", "nesdc"] | None = Field(default=None, deprecated=True)
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list, deprecated=True)
    source_trace: SourceTraceOut = Field(default_factory=SourceTraceOut)
    selection_trace: dict[str, Any] = Field(default_factory=dict)
    verified: bool


class ScopeBreakdownOut(BaseModel):
    national: int = 0
    regional: int = 0
    local: int = 0
    unknown: int = 0


class DashboardSummaryOut(BaseModel):
    as_of: date | None = None
    data_source: Literal["official", "article", "mixed"] = "article"
    party_support: list[SummaryPoint]
    president_job_approval: list[SummaryPoint] = Field(default_factory=list)
    election_frame: list[SummaryPoint] = Field(default_factory=list)
    presidential_approval: list[SummaryPoint] = Field(default_factory=list)
    presidential_approval_deprecated: bool = True
    scope_breakdown: ScopeBreakdownOut = Field(default_factory=ScopeBreakdownOut)


class TrendPoint(BaseModel):
    survey_end_date: date
    option_name: str
    value_mid: float | None = None
    pollster: str | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    source_trace: SourceTraceOut = Field(default_factory=SourceTraceOut)


class TrendsOut(BaseModel):
    metric: Literal["party_support", "president_job_approval", "election_frame"]
    scope: Literal["national", "regional", "local"]
    region_code: str | None = None
    days: int
    points: list[TrendPoint] = Field(default_factory=list)
    generated_at: datetime


class MapLatestPoint(BaseModel):
    region_code: str
    office_type: str
    title: str = Field(..., deprecated=True)
    canonical_title: str | None = None
    article_title: str | None = None
    value_mid: float | None = None
    survey_end_date: date | None = None
    option_name: str | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    source_priority: Literal["official", "article", "mixed"] = Field(default="article", deprecated=True)
    selected_source_tier: Literal["official", "nesdc", "article_aggregate", "article"] | None = Field(
        default=None,
        deprecated=True,
    )
    selected_source_channel: str | None = Field(default=None, deprecated=True)
    official_release_at: datetime | None = Field(default=None, deprecated=True)
    article_published_at: datetime | None = Field(default=None, deprecated=True)
    freshness_hours: float | None = Field(default=None, deprecated=True)
    is_official_confirmed: bool = Field(default=False, deprecated=True)
    source_channel: Literal["article", "nesdc"] | None = Field(default=None, deprecated=True)
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list, deprecated=True)
    source_trace: SourceTraceOut = Field(default_factory=SourceTraceOut)
    selection_trace: dict[str, Any] = Field(default_factory=dict)


class DashboardFilterStatsOut(BaseModel):
    total_count: int = 0
    kept_count: int = 0
    excluded_count: int = 0
    reason_counts: dict[str, int] = Field(default_factory=dict)


class DashboardMapLatestOut(BaseModel):
    as_of: date | None = None
    items: list[MapLatestPoint]
    scope_breakdown: ScopeBreakdownOut = Field(default_factory=ScopeBreakdownOut)
    filter_stats: DashboardFilterStatsOut = Field(default_factory=DashboardFilterStatsOut)


class BigMatchPoint(BaseModel):
    matchup_id: str
    title: str = Field(..., deprecated=True)
    canonical_title: str | None = None
    article_title: str | None = None
    survey_end_date: date | None = None
    value_mid: float | None = None
    spread: float | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    source_priority: Literal["official", "article", "mixed"] = Field(default="article", deprecated=True)
    official_release_at: datetime | None = Field(default=None, deprecated=True)
    article_published_at: datetime | None = Field(default=None, deprecated=True)
    freshness_hours: float | None = Field(default=None, deprecated=True)
    is_official_confirmed: bool = Field(default=False, deprecated=True)
    source_channel: Literal["article", "nesdc"] | None = Field(default=None, deprecated=True)
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list, deprecated=True)
    source_trace: SourceTraceOut = Field(default_factory=SourceTraceOut)


class DashboardBigMatchesOut(BaseModel):
    as_of: date | None = None
    items: list[BigMatchPoint]
    scope_breakdown: ScopeBreakdownOut = Field(default_factory=ScopeBreakdownOut)


class SourceChannelMixOut(BaseModel):
    article_ratio: float = 0.0
    nesdc_ratio: float = 0.0


class DashboardQualityFreshnessOut(BaseModel):
    p50_hours: float | None = None
    p90_hours: float | None = None
    over_24h_ratio: float = 0.0
    over_48h_ratio: float = 0.0
    status: Literal["healthy", "warn", "critical"] = "healthy"


class DashboardQualityOfficialOut(BaseModel):
    confirmed_ratio: float = 0.0
    unconfirmed_count: int = 0
    status: Literal["healthy", "warn", "critical"] = "healthy"


class DashboardQualityReviewOut(BaseModel):
    pending_count: int = 0
    in_progress_count: int = 0
    pending_over_24h_count: int = 0


class DashboardQualityOut(BaseModel):
    generated_at: datetime
    quality_status: Literal["healthy", "warn", "critical"] = "healthy"
    freshness_p50_hours: float | None = None
    freshness_p90_hours: float | None = None
    official_confirmed_ratio: float = 0.0
    needs_manual_review_count: int = 0
    source_channel_mix: SourceChannelMixOut = Field(default_factory=SourceChannelMixOut)
    freshness: DashboardQualityFreshnessOut = Field(default_factory=DashboardQualityFreshnessOut)
    official_confirmation: DashboardQualityOfficialOut = Field(default_factory=DashboardQualityOfficialOut)
    review_queue: DashboardQualityReviewOut = Field(default_factory=DashboardQualityReviewOut)


class RegionElectionOut(BaseModel):
    matchup_id: str
    region_code: str
    office_type: str
    title: str
    is_active: bool
    topology: Literal["official", "scenario"] = "official"
    topology_version_id: str | None = None
    is_placeholder: bool = False
    is_fallback: bool = False
    source: str = "master"
    has_poll_data: bool = False
    has_candidate_data: bool = False
    latest_survey_end_date: date | None = None
    latest_matchup_id: str | None = None
    status: Literal["조사 데이터 없음", "후보 정보 준비중", "데이터 준비 완료"] = "조사 데이터 없음"


class MatchupOptionOut(BaseModel):
    option_name: str
    candidate_id: str | None
    party_name: str | None = None
    scenario_key: str | None = None
    scenario_type: Literal["head_to_head", "multi_candidate"] | None = None
    scenario_title: str | None = None
    value_mid: float | None = None
    value_raw: str | None = None
    party_inferred: bool = False
    party_inference_source: Literal["name_rule", "article_context", "manual"] | None = None
    party_inference_confidence: float | None = None
    candidate_verified: bool = True
    candidate_verify_source: Literal["data_go", "article_context", "manual"] | None = None
    candidate_verify_confidence: float | None = None
    candidate_verify_matched_key: str | None = None
    needs_manual_review: bool = False


class MatchupScenarioOut(BaseModel):
    scenario_key: str
    scenario_type: Literal["head_to_head", "multi_candidate"]
    scenario_title: str
    options: list[MatchupOptionOut]


class MatchupOut(BaseModel):
    matchup_id: str
    region_code: str
    office_type: str
    title: str = Field(..., deprecated=True)
    canonical_title: str | None = None
    article_title: str | None = None
    has_data: bool = True
    pollster: str | None = None
    survey_start_date: date | None = None
    survey_end_date: date | None = None
    confidence_level: float | None = None
    sample_size: int | None = None
    response_rate: float | None = None
    margin_of_error: float | None = None
    source_grade: str | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    sampling_population_text: str | None = None
    legal_completeness_score: float | None = None
    legal_filled_count: int | None = None
    legal_required_count: int | None = None
    date_resolution: str | None = None
    date_inference_mode: str | None = None
    date_inference_confidence: float | None = None
    nesdc_enriched: bool = False
    needs_manual_review: bool = False
    source_priority: Literal["official", "article", "mixed"] = Field(default="article", deprecated=True)
    official_release_at: datetime | None = Field(default=None, deprecated=True)
    article_published_at: datetime | None = Field(default=None, deprecated=True)
    freshness_hours: float | None = Field(default=None, deprecated=True)
    is_official_confirmed: bool = Field(default=False, deprecated=True)
    poll_fingerprint: str | None = None
    source_channel: Literal["article", "nesdc"] | None = Field(default=None, deprecated=True)
    source_channels: list[Literal["article", "nesdc"]] | None = Field(default=None, deprecated=True)
    source_trace: SourceTraceOut = Field(default_factory=SourceTraceOut)
    verified: bool = False
    scenarios: list[MatchupScenarioOut] = Field(default_factory=list)
    options: list[MatchupOptionOut]


class JobRunOut(BaseModel):
    run_id: int
    processed_count: int
    error_count: int
    status: str


class OpsIngestionMetricsOut(BaseModel):
    total_runs: int
    success_runs: int
    partial_success_runs: int
    failed_runs: int
    total_processed_count: int
    total_error_count: int
    date_inference_failed_count: int = 0
    date_inference_estimated_count: int = 0
    fetch_fail_rate: float


class OpsReviewMetricsOut(BaseModel):
    pending_count: int
    in_progress_count: int
    resolved_count: int
    pending_over_24h_count: int
    mapping_error_24h_count: int


class OpsFailureDistributionOut(BaseModel):
    issue_type: str
    count: int
    ratio: float


class OpsWarningRuleOut(BaseModel):
    rule_key: str
    description: str
    threshold: float
    actual: float
    triggered: bool


class OpsMetricsSummaryOut(BaseModel):
    generated_at: datetime
    window_hours: int
    ingestion: OpsIngestionMetricsOut
    review_queue: OpsReviewMetricsOut
    failure_distribution: list[OpsFailureDistributionOut]
    warnings: list[OpsWarningRuleOut]


class OpsCoverageSummaryOut(BaseModel):
    generated_at: datetime
    state: str
    warning_message: str | None = None
    regions_total: int
    regions_covered: int
    sido_covered: int
    observations_total: int
    latest_survey_end_date: date | None = None


class ReviewQueueItemOut(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    issue_type: str
    status: str
    assigned_to: str | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewQueueDecisionIn(BaseModel):
    assigned_to: str | None = None
    review_note: str | None = None


class ReviewQueueIssueCountOut(BaseModel):
    issue_type: str
    count: int


class ReviewQueueErrorCountOut(BaseModel):
    error_code: str
    count: int


class ReviewQueueStatsOut(BaseModel):
    generated_at: datetime
    window_hours: int
    total_count: int
    pending_count: int
    in_progress_count: int
    resolved_count: int
    issue_type_counts: list[ReviewQueueIssueCountOut]
    error_code_counts: list[ReviewQueueErrorCountOut]


class ReviewQueueTrendPointOut(BaseModel):
    bucket_start: datetime
    issue_type: str
    error_code: str
    count: int


class ReviewQueueTrendsOut(BaseModel):
    generated_at: datetime
    window_hours: int
    bucket_hours: int
    points: list[ReviewQueueTrendPointOut]


class ArticleInput(BaseModel):
    url: str
    title: str
    publisher: str
    published_at: datetime | None = None
    raw_text: str | None = None
    raw_hash: str | None = None


class RegionInput(BaseModel):
    region_code: str
    sido_name: str
    sigungu_name: str
    admin_level: str = "sigungu"
    parent_region_code: str | None = None


class CandidateInput(BaseModel):
    candidate_id: str
    name_ko: str
    party_name: str | None = None
    party_inferred: bool = False
    party_inference_source: Literal["name_rule", "article_context", "manual"] | None = None
    party_inference_confidence: float | None = None
    needs_manual_review: bool = False
    source_channel: Literal["article", "nesdc"] = "article"
    source_channels: list[Literal["article", "nesdc"]] | None = None
    official_release_at: datetime | None = None
    article_published_at: datetime | None = None
    gender: str | None = None
    birth_date: date | None = None
    job: str | None = None
    career_summary: str | None = None
    election_history: str | None = None


class PollObservationInput(BaseModel):
    observation_key: str
    survey_name: str
    pollster: str
    survey_start_date: date | None = None
    survey_end_date: date | None = None
    confidence_level: float | None = None
    sample_size: int | None = None
    response_rate: float | None = None
    margin_of_error: float | None = None
    sponsor: str | None = None
    method: str | None = None
    region_code: str
    office_type: str
    matchup_id: str
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    sampling_population_text: str | None = None
    legal_completeness_score: float | None = None
    legal_filled_count: int | None = None
    legal_required_count: int | None = None
    date_resolution: str | None = None
    date_inference_mode: str | None = None
    date_inference_confidence: float | None = None
    poll_fingerprint: str | None = None
    source_channel: Literal["article", "nesdc"] = "article"
    source_channels: list[Literal["article", "nesdc"]] | None = None
    official_release_at: datetime | None = None
    verified: bool = False
    source_grade: str = "C"


class PollOptionInput(BaseModel):
    option_type: str
    option_name: str
    candidate_id: str | None = None
    party_name: str | None = None
    scenario_key: str | None = None
    scenario_type: Literal["head_to_head", "multi_candidate"] | None = None
    scenario_title: str | None = None
    value_raw: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_mid: float | None = None
    is_missing: bool = False
    party_inferred: bool = False
    party_inference_source: Literal["name_rule", "article_context", "manual"] | None = None
    party_inference_confidence: float | None = None
    candidate_verified: bool = True
    candidate_verify_source: Literal["data_go", "article_context", "manual"] | None = None
    candidate_verify_confidence: float | None = None
    candidate_verify_matched_key: str | None = None
    needs_manual_review: bool = False


class IngestRecordInput(BaseModel):
    article: ArticleInput
    region: RegionInput | None = None
    candidates: list[CandidateInput] = Field(default_factory=list)
    observation: PollObservationInput
    options: list[PollOptionInput]


class IngestPayload(BaseModel):
    run_type: str = "manual"
    extractor_version: str = "manual-v1"
    llm_model: str | None = None
    records: list[IngestRecordInput]
