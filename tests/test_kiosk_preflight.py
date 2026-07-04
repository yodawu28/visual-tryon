import httpx

import scripts.kiosk_preflight as kiosk_preflight


def test_run_preflight_returns_success_for_ready_api(monkeypatch):
    def fake_get(url: str, timeout: float):
        return httpx.Response(
            200,
            json={
                "status": "ready",
                "checks": {
                    "storage": {
                        "status": "ready",
                        "message": "Directory is writable",
                        "details": {},
                    }
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(kiosk_preflight.httpx, "get", fake_get)

    result = kiosk_preflight.run_preflight(base_url="http://localhost:8080")

    assert result["success"] is True
    assert result["status"] == "ready"
    assert kiosk_preflight.exit_code_for_result(result) == 0


def test_run_preflight_returns_not_ready_for_failed_check(monkeypatch):
    def fake_get(url: str, timeout: float):
        return httpx.Response(
            503,
            json={
                "status": "not_ready",
                "checks": {
                    "ollama_analyzer_config": {
                        "status": "not_ready",
                        "message": "Ollama analyzer runtime is not reachable",
                        "details": {"error": "connection refused"},
                    }
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(kiosk_preflight.httpx, "get", fake_get)

    result = kiosk_preflight.run_preflight(base_url="http://localhost:8080")
    summary = kiosk_preflight.format_human_summary(result)

    assert result["success"] is False
    assert result["status"] == "not_ready"
    assert kiosk_preflight.exit_code_for_result(result) == 1
    assert "ollama_analyzer_config" in summary
    assert "connection refused" in summary


def test_run_preflight_returns_unreachable_for_api_connection_error(monkeypatch):
    def fake_get(url: str, timeout: float):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(kiosk_preflight.httpx, "get", fake_get)

    result = kiosk_preflight.run_preflight(base_url="http://localhost:8080")

    assert result["success"] is False
    assert result["status"] == "unreachable"
    assert "not reachable" in result["message"]
    assert kiosk_preflight.exit_code_for_result(result) == 2


def test_default_base_url_uses_port_environment(monkeypatch):
    monkeypatch.setenv("PORT", "9090")

    assert kiosk_preflight.default_base_url() == "http://127.0.0.1:9090"


def test_main_prints_json_and_returns_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(
        kiosk_preflight,
        "run_preflight",
        lambda base_url, timeout: {
            "success": False,
            "status": "not_ready",
            "endpoint": "http://localhost:8080/api/v1/readiness",
            "checks": {},
        },
    )

    exit_code = kiosk_preflight.main(["--json"])

    assert exit_code == 1
    assert '"status": "not_ready"' in capsys.readouterr().out
