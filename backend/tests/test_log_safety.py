"""
R05 — منع تسرب البيانات الحساسة للسجلات: مفاتيح/توكنات/كلمات مرور، نصوص الرسائل والفواتير،
وقيم استعلامات SQL.
"""
import io
import logging

from app.agent.providers.base import AgentReply
from app.core.log_safety import (
    SensitiveDataFilter, describe_text, install_log_redaction, redact, safe_error,
)
from app.database import session as db_session_module
from app.services import agent_chat_service
from app.services.categorizer.gemini_based import GeminiCategorizer
from app.models.category import Category, CategoryType

SECRET_TEXT = "SENTINEL-ملاحظة-مالية-سرية-12345"
FAKE_GOOGLE_KEY = "AIza" + "A" * 35
FAKE_AQ_KEY = "AQ.Ab8RN6" + "x" * 30
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlMTIz"


def test_redact_removes_api_keys_tokens_and_passwords():
    text = (
        f"key={FAKE_GOOGLE_KEY} other {FAKE_AQ_KEY} auth Bearer {FAKE_JWT} "
        f"jwt {FAKE_JWT} password: hunter2secret"
    )
    cleaned = redact(text)
    for secret in (FAKE_GOOGLE_KEY, FAKE_AQ_KEY, FAKE_JWT, "hunter2secret"):
        assert secret not in cleaned
    assert "[REDACTED" in cleaned


def test_describe_text_and_safe_error_do_not_leak_content():
    assert SECRET_TEXT not in describe_text(SECRET_TEXT)
    assert "len=" in describe_text(SECRET_TEXT)
    long_error = f"boom {FAKE_GOOGLE_KEY} " + "x" * 1000
    cleaned = safe_error(long_error)
    assert FAKE_GOOGLE_KEY not in cleaned
    assert len(cleaned) <= 300


def test_filter_redacts_formatted_log_messages():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SensitiveDataFilter())
    logger = logging.getLogger("test.log_safety.filter")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        logger.warning("call failed with key %s and token %s", FAKE_GOOGLE_KEY, FAKE_JWT)
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert FAKE_GOOGLE_KEY not in output and FAKE_JWT not in output
    assert "[REDACTED" in output


def test_install_log_redaction_is_idempotent():
    install_log_redaction()
    install_log_redaction()
    root = logging.getLogger()
    assert root.handlers
    for handler in root.handlers:
        filters = [f for f in handler.filters if isinstance(f, SensitiveDataFilter)]
        assert len(filters) <= 1


def test_sql_echo_is_off_and_parameters_are_hidden():
    engine = db_session_module.engine
    assert engine.echo is False
    assert engine.hide_parameters is True


class _FakeProvider:
    def __init__(self, text):
        self.text = text

    def generate_reply(self, system_prompt, user_message, history=None):
        return AgentReply(text=self.text)


def test_categorizer_parse_failure_does_not_log_model_output(caplog):
    categorizer = GeminiCategorizer(_FakeProvider(f"مش JSON {SECRET_TEXT}"))
    category = Category(name="مطاعم", icon="x", is_default=True, category_type=CategoryType.EXPENSE, keywords=[])
    with caplog.at_level(logging.ERROR):
        categorizer.suggest_category("غدا مع الشباب", [category])
    assert SECRET_TEXT not in caplog.text
    assert "len=" in caplog.text


def test_malformed_protocol_block_does_not_log_its_content(caplog):
    text = f"رد عادي <<<GOAL_PROPOSAL>>>{{مش json {SECRET_TEXT}}}<<<END>>>"
    with caplog.at_level(logging.WARNING):
        agent_chat_service._extract_and_strip_block(agent_chat_service.GOAL_PROPOSAL_PATTERN, text)
    assert SECRET_TEXT not in caplog.text
