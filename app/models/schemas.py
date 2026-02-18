from datetime import date, datetime

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
    verified: bool


class DashboardSummaryOut(BaseModel):
    as_of: date | None = None
    party_support: list[SummaryPoint]
    presidential_approval: list[SummaryPoint]


class MapLatestPoint(BaseModel):
    region_code: str
    office_type: str
    title: str
    value_mid: float | None = None
    survey_end_date: date | None = None
    option_name: str | None = None


class DashboardMapLatestOut(BaseModel):
    as_of: date | None = None
    items: list[MapLatestPoint]


class BigMatchPoint(BaseModel):
    matchup_id: str
    title: str
    survey_end_date: date | None = None
    value_mid: float | None = None
    spread: float | None = None


class DashboardBigMatchesOut(BaseModel):
    as_of: date | None = None
    items: list[BigMatchPoint]


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


class MatchupOut(BaseModel):
    matchup_id: str
    region_code: str
    office_type: str
    title: str
    pollster: str | None = None
    survey_end_date: date | None = None
    margin_of_error: float | None = None
    source_grade: str | None = None
    verified: bool
    options: list[MatchupOptionOut]


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
    sample_size: int | None = None
    response_rate: float | None = None
    margin_of_error: float | None = None
    region_code: str
    office_type: str
    matchup_id: str
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
