"""Module documentation."""
import json
import logging
from uuid import UUID

from app.agent.providers.base import BaseAIProvider
from app.models.category import Category
from app.services.categorizer.base import BaseCategorizer, CategorySuggestion

logger = logging.getLogger("rasheed.agent")


class GeminiCategorizer(BaseCategorizer):
    def __init__(self, provider: BaseAIProvider):
        self._provider = provider

    def suggest_category(
        self, note: str, available_categories: list[Category]
    ) -> CategorySuggestion:
        normalized_note = note.strip()

        if not normalized_note:
            return CategorySuggestion(
                category_id=None, category_name=None, confidence=0.0,
                reasoning="ما في نص كافي للتصنيف",
            )
        if not available_categories:
            return CategorySuggestion(
                category_id=None, category_name=None, confidence=0.0,
                reasoning="ما في تصنيفات متاحة أصلًا",
            )

        category_lookup = {str(c.id): c.name for c in available_categories}
        options = "\n".join(f"- {cid}: {name}" for cid, name in category_lookup.items())

        prompt = (
            f'المستخدم كتب وصف مصروف: "{normalized_note}"\n'
            "اختر أنسب تصنيف من هالقائمة (id: اسم):\n"
            f"{options}\n\n"
            "رد فقط بصيغة JSON صحيحة على هذا الشكل بالظبط، بدون أي نص إضافي:\n"
            '{"category_id": "<id أو null>", "confidence": <رقم من 0 إلى 1>}\n'
            "لو ما في تصنيف مناسب أصلًا من القائمة، رجّع category_id: null وconfidence: 0."
        )

        reply = self._provider.generate_reply(
            system_prompt="أنت مصنّف مصاريف دقيق. رد بصيغة JSON فقط، بدون أي نص إضافي.",
            user_message=prompt,
        )

        if reply.raw_error:
            logger.error("GeminiCategorizer AI call failed: %s", reply.raw_error)
            return CategorySuggestion(
                category_id=None, category_name=None, confidence=0.0,
                reasoning="تعذر الوصول لخدمة التصنيف الذكي، جرب تختار يدويًا",
            )

        cleaned = reply.text.strip().strip("`").removeprefix("json").strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("GeminiCategorizer could not parse JSON: %r", reply.text)
            return CategorySuggestion(
                category_id=None, category_name=None, confidence=0.0,
                reasoning="رد غير مفهوم من محرك التصنيف",
            )

        category_id = parsed.get("category_id")
        confidence = parsed.get("confidence")

        if category_id not in category_lookup or not isinstance(confidence, (int, float)):

            return CategorySuggestion(
                category_id=None, category_name=None, confidence=0.0,
                reasoning="ما لقينا تصنيف مناسب بثقة كافية",
            )

        return CategorySuggestion(
            category_id=UUID(category_id),
            category_name=category_lookup[category_id],
            confidence=max(0.0, min(float(confidence), 1.0)),
            reasoning="تصنيف ذكي عبر Gemini بناءً على وصف المستخدم",
        )
