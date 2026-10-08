from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_success_exact_stdout(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("AI must not be called on success")

    monkeypatch.setattr(main, "analyze_error", boom)
    r = client.post("/code-interpreter", json={"code": "print(2 + 3)"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["output"] == "5\n"
    assert body["error"] == []


def test_error_line_number(monkeypatch):
    monkeypatch.delenv("AIPIPE_TOKEN", raising=False)  # forces fallback path
    code = "x = 1\ny = 2\nprint(x / 0)\n"
    r = client.post("/code-interpreter", json={"code": code})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["error"] == [3]
    assert "ZeroDivisionError" in body["traceback"]
    assert body["analysis"]["line_number"] == 3
    assert body["analysis"]["error_type"] == "ZeroDivisionError"


def test_syntax_error_line(monkeypatch):
    monkeypatch.delenv("AIPIPE_TOKEN", raising=False)
    r = client.post("/code-interpreter", json={"code": "a = 1\nb = (\n"})
    body = r.json()
    assert body["success"] is False
    assert body["error"] and body["error"][0] >= 2


def test_cors_header():
    r = client.options(
        "/code-interpreter",
        headers={"Origin": "http://example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == "*"
