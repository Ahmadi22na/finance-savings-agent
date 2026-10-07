"""
اختبارات معالجة أخطاء GeminiProvider (بدون أي اتصال حقيقي بجوجل):
إعادة المحاولة عند 503، الموديل البديل، وتمييز رسائل 401/403/429/404.
"""
from types import SimpleNamespace

import pytest
from google.genai.errors import ClientError, ServerError

from app.agent.providers import gemini_provider
from app.agent.providers.gemini_provider import GeminiProvider
from app.config import settings


class FakeModels:
    """بيرجّع/بيرمي نتايج مبرمجة مسبقًا لكل موديل، وبيسجّل ترتيب الاستدعاءات."""

    def __init__(self, script: dict[str, list]):
        self.script = {model: list(outcomes) for model, outcomes in script.items()}
        self.calls: list[str] = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        outcome = self.script[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


def make_provider(script: dict[str, list]):
    provider = GeminiProvider.__new__(GeminiProvider)  # بدون استدعاء genai.Client الحقيقي
    fake_models = FakeModels(script)
    provider._client = SimpleNamespace(models=fake_models)
    return provider, fake_models


def server_503() -> ServerError:
    return ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


def client_error(code: int, status: str, message: str = "x") -> ClientError:
    return ClientError(code, {"error": {"code": code, "message": message, "status": status}})


@pytest.fixture(autouse=True)
def fast_and_configured(monkeypatch):
    monkeypatch.setattr(gemini_provider.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(settings, "AGENT_MODEL", "primary")
    monkeypatch.setattr(settings, "AGENT_FALLBACK_MODEL", "")


def test_retries_503_then_succeeds():
    provider, models = make_provider({"primary": [server_503(), "تمام"]})
    reply = provider.generate_reply("sys", "hi")
    assert reply.text == "تمام"
    assert models.calls == ["primary", "primary"]


def test_exhausted_503_without_fallback_returns_busy_message():
    provider, models = make_provider({"primary": [server_503(), server_503(), server_503()]})
    reply = provider.generate_reply("sys", "hi")
    assert "مشغولة" in reply.text
    assert "503" in reply.raw_error
    assert len(models.calls) == 3


def test_exhausted_503_uses_fallback_model(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_FALLBACK_MODEL", "backup")
    provider, models = make_provider({
        "primary": [server_503(), server_503(), server_503()],
        "backup": ["من البديل"],
    })
    reply = provider.generate_reply("sys", "hi")
    assert reply.text == "من البديل"
    assert models.calls == ["primary", "primary", "primary", "backup"]


def test_invalid_key_message_is_not_the_aq_message():
    provider, models = make_provider({
        "primary": [client_error(401, "UNAUTHENTICATED", "API key not valid. Please pass a valid API key.")],
    })
    reply = provider.generate_reply("sys", "hi")
    assert "مفتاح الـ API مش مقبول" in reply.text
    assert "google-genai" not in reply.text
    assert models.calls == ["primary"]  # بدون إعادة محاولة


def test_aq_key_issue_keeps_specific_message():
    provider, _ = make_provider({
        "primary": [client_error(401, "UNAUTHENTICATED", "ACCESS_TOKEN_TYPE_UNSUPPORTED")],
    })
    reply = provider.generate_reply("sys", "hi")
    assert "google-genai" in reply.text


def test_quota_error_message():
    provider, _ = make_provider({"primary": [client_error(429, "RESOURCE_EXHAUSTED")]})
    reply = provider.generate_reply("sys", "hi")
    assert "حد الاستخدام" in reply.text


def test_missing_model_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_FALLBACK_MODEL", "backup")
    provider, models = make_provider({
        "primary": [client_error(404, "NOT_FOUND", "model not found")],
        "backup": ["شغّال"],
    })
    reply = provider.generate_reply("sys", "hi")
    assert reply.text == "شغّال"
    assert models.calls == ["primary", "backup"]
