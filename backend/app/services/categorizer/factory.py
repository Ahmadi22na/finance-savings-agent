"""
النقطة الوحيدة يلي رح تتغيّر لما نضيف Gemini بـ Sprint القادم.
اليوم بترجع RuleBasedCategorizer دايمًا. لما يجهز مفتاح Gemini، هالدالة رح تصير:

    if settings.ANTHROPIC_API_KEY أو GEMINI_API_KEY موجود:
        return GeminiCategorizer()
    return RuleBasedCategorizer()

وبقية النظام (transaction_service) ما بيحتاج يعرف ولا يتغيّر إطلاقًا.
"""
from functools import lru_cache

from app.services.categorizer.base import BaseCategorizer
from app.services.categorizer.rule_based import RuleBasedCategorizer


@lru_cache
def get_categorizer() -> BaseCategorizer:
    return RuleBasedCategorizer()
