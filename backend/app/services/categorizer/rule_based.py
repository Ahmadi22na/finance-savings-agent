"""Module documentation."""
from uuid import UUID

from app.models.category import Category
from app.services.categorizer.base import BaseCategorizer, CategorySuggestion


class RuleBasedCategorizer(BaseCategorizer):
    def suggest_category(
        self, note: str, available_categories: list[Category]
    ) -> CategorySuggestion:
        normalized_note = note.strip().lower()

        if not normalized_note:
            return CategorySuggestion(
                category_id=None, category_name=None, confidence=0.0,
                reasoning="ما في نص كافي للتصنيف",
            )

        best_match: Category | None = None
        best_score = 0

        for category in available_categories:
            if not category.keywords:
                continue
            score = sum(1 for kw in category.keywords if kw.lower() in normalized_note)
            if score > best_score:
                best_score = score
                best_match = category

        if best_match is None:
            return CategorySuggestion(
                category_id=None, category_name=None, confidence=0.0,
                reasoning="ما لقينا كلمة مفتاحية مطابقة — بيحتاج المستخدم يختار يدويًا",
            )


        confidence = min(0.6 + (best_score - 1) * 0.15, 0.95)

        return CategorySuggestion(
            category_id=best_match.id,
            category_name=best_match.name,
            confidence=confidence,
            reasoning=f"تطابق مع كلمات مفتاحية بتصنيف '{best_match.name}'",
        )
