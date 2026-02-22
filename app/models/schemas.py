from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class RegionOut(BaseModel):
    region_code: str
    sido_name: str
    sigungu_name: str
    admin_level: str


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


class SummaryPoint(BaseModel):
    option_name: str
    value_mid: float | None = None
    pollster: str | None = None
    survey_end_date: date | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    source_priority: Literal["official", "article", "mixed"] = "article"
    official_release_at: datetime | None = None
    article_published_at: datetime | None = None
    freshness_hours: float | None = None
    is_official_confirmed: bool = False
    source_channel: Literal["article", "nesdc"] | None = None
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list)
    verified: bool


class ScopeBreakdownOut(BaseModel):
    national: int = 0
    regional: int = 0
    local: int = 0
    unknown: int = 0


class DashboardSummaryOut(BaseModel):
    as_of: date | None = None
    party_support: list[SummaryPoint]
    presidential_approval: list[SummaryPoint]
    scope_breakdown: ScopeBreakdownOut = Field(default_factory=ScopeBreakdownOut)


class MapLatestPoint(BaseModel):
    region_code: str
    office_type: str
    title: str
    value_mid: float | None = None
    survey_end_date: date | None = None
    option_name: str | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    audience_region_code: str | None = None
    source_priority: Literal["official", "article", "mixed"] = "article"
    official_release_at: datetime | None = None
    article_published_at: datetime | None = None
    freshness_hours: float | None = None
    is_official_confirmed: bool = False
    source_channel: Literal["article", "nesdc"] | None = None
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list)


class DashboardMapLatestOut(BaseModel):
    as_of: date | None = None
    items: list[MapLatestPoint]
    scope_breakdown: ScopeBreakdownOut = Field(default_factory=ScopeBreakdownOut)


class BigMatchPoint(BaseModel):
    matchup_id: str
    title: str
    survey_end_date: date | None = None
    value_mid: float | None = None
    spread: float | None = None
    audience_scope: Literal["national", "regional", "local"] | None = None
    source_channel: Literal["article", "nesdc"] | None = None
    source_channels: list[Literal["article", "nesdc"]] = Field(default_factory=list)


class DashboardBigMatchesOut(BaseModel):
    as_of: date | None = None
    items: list[BigMatchPoint]
    scope_breakdown: ScopeBreakdownOut = Field(default_factory=ScopeBreakdownOut)


class SourceChannelMixOut(BaseModel):
    article_ratio: float = 0.0
    nesdc_ratio: float = 0.0


class DashboardQualityOut(BaseModel):
    generated_at: datetime
    freshness_p50_hours: float | None = None
    freshness_p90_hours: float | None = None
    official_confirmed_ratio: float = 0.0
    needs_manual_review_count: int = 0
    source_channel_mix: SourceChannelMixOut = Field(default_factory=SourceChannelMixOut)


class RegionElectionOut(BaseModel):
    matchup_id: str
    region_code: str
    office_type: str
    title: str
    is_active: bool


class MatchupOptionOut(BaseModel):
    option_name: str
    value_mid: float | None = None
    value_raw: str | None = None
    party_inferred: bool = False
    party_inference_source: Literal["name_rule", "article_context", "manual"] | None = None
    party_inference_confidence: float | None = None
    needs_manual_review: bool = False


class MatchupOut(BaseModel):
    matchup_id: str
    region_code: str
    office_type: str
    title: str
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
    source_priority: Literal["official", "article", "mixed"] = "article"
    official_release_at: datetime | None = None
    article_published_at: datetime | None = None
    freshness_hours: float | None = None
    is_official_confirmed: bool = False
    poll_fingerprint: str | None = None
    source_channel: Literal["article", "nesdc"] | None = None
    source_channels: list[Literal["article", "nesdc"]] | None = None
    verified: bool
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
    value_raw: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_mid: float | None = None
    is_missing: bool = False
    party_inferred: bool = False
    party_inference_source: Literal["name_rule", "article_context", "manual"] | None = None
    party_inference_confidence: float | None = None
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
