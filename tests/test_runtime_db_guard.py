from app.runtime_db_guard import should_auto_apply_schema_on_startup


def test_should_auto_apply_schema_on_startup_defaults_to_false_without_railway(monkeypatch):
    monkeypatch.delenv("AUTO_APPLY_SCHEMA_ON_STARTUP", raising=False)
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
    monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)
    assert should_auto_apply_schema_on_startup() is False


def test_should_auto_apply_schema_on_startup_uses_explicit_env(monkeypatch):
    monkeypatch.setenv("AUTO_APPLY_SCHEMA_ON_STARTUP", "true")
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
    monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)
    assert should_auto_apply_schema_on_startup() is True

    monkeypatch.setenv("AUTO_APPLY_SCHEMA_ON_STARTUP", "false")
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "dummy")
    assert should_auto_apply_schema_on_startup() is False


def test_should_auto_apply_schema_on_startup_enables_on_railway(monkeypatch):
    monkeypatch.delenv("AUTO_APPLY_SCHEMA_ON_STARTUP", raising=False)
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "svc-123")
    assert should_auto_apply_schema_on_startup() is True
