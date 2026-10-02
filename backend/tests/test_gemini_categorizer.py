"""Module documentation."""
import pytest

from app.agent.providers.base import AgentReply
from app.config import settings
from app.models.category import Category, CategoryType
from app.services.categorizer import factory as categorizer_factory
from app.services.categorizer.gemini_based import GeminiCategorizer
from app.services.categorizer.rule_based import RuleBasedCategorizer


class FakeProvider:
    def __init__(self, text):
        self.text = text

    def generate_reply(self, system_prompt, user_message, history=None):
        return AgentReply(text=self.text)

    def analyze_image(self, *args, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    """ clear factory cache documentation."""
    categorizer_factory.get_categorizer.cache_clear()
    yield
    categorizer_factory.get_categorizer.cache_clear()


def make_category(name="مطاعم"):
    return Category(
        name=name, icon="utensils", is_default=True,
        category_type=CategoryType.EXPENSE, keywords=[],
    )




def test_factory_uses_rule_based_when_no_gemini_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    engine = categorizer_factory.get_categorizer()
    assert isinstance(engine, RuleBasedCategorizer)


def test_factory_uses_gemini_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-test-key")
    engine = categorizer_factory.get_categorizer()
    assert isinstance(engine, GeminiCategorizer)




def test_suggests_category_from_valid_json_response(db_session):
    category = make_category()
    db_session.add(category)
    db_session.commit()

    fake = FakeProvider(f'{{"category_id": "{category.id}", "confidence": 0.9}}')
    result = GeminiCategorizer(fake).suggest_category("عشا برا مع صحابي", [category])

    assert result.category_id == category.id
    assert result.category_name == "مطاعم"
    assert result.confidence == 0.9


def test_empty_note_never_calls_ai(db_session):
    category = make_category()
    fake = FakeProvider('{"category_id": null, "confidence": 0}')
    result = GeminiCategorizer(fake).suggest_category("   ", [category])
    assert result.confidence == 0.0
    assert result.category_id is None


def test_no_available_categories_returns_zero_confidence():
    fake = FakeProvider('{"category_id": null, "confidence": 0}')
    result = GeminiCategorizer(fake).suggest_category("قهوة", [])
    assert result.confidence == 0.0


def test_ignores_hallucinated_category_id(db_session):
    """Test ignores hallucinated category id documentation."""
    category = make_category()
    fake = FakeProvider('{"category_id": "not-a-real-uuid", "confidence": 0.8}')
    result = GeminiCategorizer(fake).suggest_category("شي ما", [category])
    assert result.category_id is None
    assert result.confidence == 0.0


def test_handles_malformed_json_gracefully(db_session):
    category = make_category()
    fake = FakeProvider("هاد مش JSON أصلًا")
    result = GeminiCategorizer(fake).suggest_category("شي ما", [category])
    assert result.confidence == 0.0


def test_handles_ai_provider_error_gracefully(db_session):
    category = make_category()

    class FailingProvider:
        def generate_reply(self, *args, **kwargs):
            return AgentReply(text="", raw_error="Gemini unavailable")

        def analyze_image(self, *args, **kwargs):
            raise NotImplementedError

    result = GeminiCategorizer(FailingProvider()).suggest_category("شي ما", [category])
    assert result.confidence == 0.0
    assert result.category_id is None


def test_confidence_is_clamped_between_zero_and_one(db_session):
    category = make_category()
    db_session.add(category)
    db_session.commit()
    fake = FakeProvider(f'{{"category_id": "{category.id}", "confidence": 5}}')
    result = GeminiCategorizer(fake).suggest_category("شي ما", [category])
    assert result.confidence == 1.0
