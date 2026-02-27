from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    data_go_kr_key: str
    database_url: str
    internal_job_token: str | None = None
    app_env: str = "dev"
    data_go_candidate_endpoint_url: str = (
        "https://apis.data.go.kr/9760000/PofelcddInfoInqireService/getPoelpcddRegistSttusInfoInqire"
    )
    data_go_candidate_sg_id: str | None = None
    data_go_candidate_sg_typecode: str | None = None
    data_go_candidate_sd_name: str | None = None
    data_go_candidate_sgg_name: str | None = None
    data_go_candidate_timeout_sec: float = 4.0
    data_go_candidate_max_retries: int = 2
    data_go_candidate_cache_ttl_sec: int = 300
    data_go_candidate_requests_per_sec: float = 5.0
    data_go_candidate_num_of_rows: int = 300
    api_read_cache_ttl_sec: int = 0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
