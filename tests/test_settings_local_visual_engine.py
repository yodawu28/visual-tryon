from src.config.settings import Settings


def test_local_visual_engine_settings_default_to_subprocess_mode(monkeypatch):
    monkeypatch.delenv("LOCAL_VISUAL_ENGINE_MODE", raising=False)
    monkeypatch.delenv("LOCAL_VISUAL_ENGINE_SERVICE_URL", raising=False)
    monkeypatch.delenv("LOCAL_VISUAL_ENGINE_START_SERVICE", raising=False)

    settings = Settings(_env_file=None)

    assert settings.local_visual_engine_mode == "subprocess"
    assert settings.local_visual_engine_service_url == "http://127.0.0.1:8091"
    assert settings.local_visual_engine_start_service is False
    assert settings.local_visual_engine_service_host == "127.0.0.1"
    assert settings.local_visual_engine_service_port == 8091
    assert settings.local_visual_engine_service_ready_timeout == 900
    assert (
        settings.effective_local_visual_engine_service_request_timeout
        == settings.local_leffa_timeout
    )
    assert settings.local_visual_engine_engine == "leffa"


def test_local_visual_engine_settings_read_environment(monkeypatch):
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_MODE", "service")
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_SERVICE_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_START_SERVICE", "true")
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_SERVICE_HOST", "127.0.0.2")
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_SERVICE_PORT", "9000")
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_SERVICE_READY_TIMEOUT", "120")
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_SERVICE_REQUEST_TIMEOUT", "600")
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_ENGINE", "leffa")

    settings = Settings(_env_file=None)

    assert settings.local_visual_engine_mode == "service"
    assert settings.local_visual_engine_service_url == "http://127.0.0.1:9000"
    assert settings.local_visual_engine_start_service is True
    assert settings.local_visual_engine_service_host == "127.0.0.2"
    assert settings.local_visual_engine_service_port == 9000
    assert settings.local_visual_engine_service_ready_timeout == 120
    assert settings.local_visual_engine_service_request_timeout == 600
    assert settings.local_visual_engine_engine == "leffa"
