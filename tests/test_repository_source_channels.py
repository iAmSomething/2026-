from app.services.repository import PostgresRepository


def test_prepare_observation_payload_backfills_source_channels_from_source_channel():
    repo = PostgresRepository(conn=None)
    payload = repo._prepare_observation_payload(  # noqa: SLF001
        {
            "observation_key": "obs-1",
            "source_channel": "article",
        },
        article_id=1,
        ingestion_run_id=1,
    )
    assert payload["source_channels"] == ["article"]


def test_prepare_observation_payload_keeps_given_source_channels():
    repo = PostgresRepository(conn=None)
    payload = repo._prepare_observation_payload(  # noqa: SLF001
        {
            "observation_key": "obs-1",
            "source_channel": "article",
            "source_channels": ["article", "nesdc"],
        },
        article_id=1,
        ingestion_run_id=1,
    )
    assert payload["source_channels"] == ["article", "nesdc"]
