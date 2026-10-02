"""Module documentation."""
from functools import lru_cache

from app.agent.providers.factory import get_ai_provider
from app.config import settings
from app.services.categorizer.base import BaseCategorizer
from app.services.categorizer.gemini_based import GeminiCategorizer
from app.services.categorizer.rule_based import RuleBasedCategorizer


@lru_cache
def get_categorizer() -> BaseCategorizer:
    if settings.GEMINI_API_KEY:
        return GeminiCategorizer(get_ai_provider())
    return RuleBasedCategorizer()
