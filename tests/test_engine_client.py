import io
import json
from email.message import Message
import urllib.error

import engine
import pandas as pd
import pytest


def test_chat_json_posts_to_gemini_rest_api(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response_body = {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return io.BytesIO(json.dumps(response_body).encode("utf-8"))

    monkeypatch.setattr(engine.urllib.request, "urlopen", fake_urlopen)

    assert engine._chat_json("system rules", "user prompt") == {"ok": True}
    request = captured["request"]
    assert request.full_url.endswith(f"/models/{engine.MODEL}:generateContent")
    assert request.get_header("X-goog-api-key") == "test-key"
    assert captured["timeout"] == 60
    payload = json.loads(request.data)
    assert payload["systemInstruction"]["parts"][0]["text"] == "system rules"
    assert payload["contents"][0]["parts"][0]["text"] == "user prompt"


def test_chat_json_retries_temporary_server_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response_body = {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}
    attempts = []
    delays = []

    def fake_urlopen(request, timeout):
        attempts.append(request)
        if len(attempts) == 1:
            headers = Message()
            headers["Retry-After"] = "0"
            raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", headers, io.BytesIO(b"busy"))
        return io.BytesIO(json.dumps(response_body).encode("utf-8"))

    monkeypatch.setattr(engine.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(engine.time, "sleep", delays.append)

    assert engine._chat_json("system rules", "user prompt") == {"ok": True}
    assert len(attempts) == 2
    assert delays == [0.0]


@pytest.mark.parametrize("wrapped", [False, True])
def test_recommend_accepts_list_or_insights_object(monkeypatch, wrapped):
    item = {"insight": "Electronics revenue was 123", "action": "Review stock", "evidence": "123"}
    response = {"insights": [item]} if wrapped else [item]
    monkeypatch.setattr(engine, "_chat_json", lambda system, user: response)
    results = engine.recommend("top category?", "SELECT 1", pd.DataFrame({"revenue": [123]}))

    assert len(results) == 1
    assert results[0]["insight"] == item["insight"]
    assert results[0]["action"] == item["action"]
    assert results[0]["ungrounded"] == []