from functools import lru_cache

import logging

from app.agent.providers.base import BaseAIProvider
from app.agent.providers.demo_provider import DemoProvider
from app.agent.providers.gemini_provider import GeminiProvider
from app.config import settings


@lru_cache
def get_ai_provider() -> BaseAIProvider:
    if settings.AI_PROVIDER == "demo":
        logging.getLogger("rasheed.agent").warning("AI_PROVIDER=demo: ردود رشيد جاهزة ومحاكاة، مش Gemini حقيقي")
        return DemoProvider()
    return GeminiProvider()
