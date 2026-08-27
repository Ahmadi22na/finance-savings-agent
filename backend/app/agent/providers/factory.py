from functools import lru_cache

from app.agent.providers.base import BaseAIProvider
from app.agent.providers.gemini_provider import GeminiProvider


@lru_cache
def get_ai_provider() -> BaseAIProvider:
    return GeminiProvider()
