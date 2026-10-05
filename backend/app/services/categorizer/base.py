"""
Categorizer Interface (Strategy Pattern).

هذا الملف هو "العقد" — أي محرك تصنيف (قواعد بسيطة اليوم، Gemini غدًا) لازم يلتزم فيه.
بقية النظام (transaction_service) بيتعامل مع هالواجهة فقط، وما بيعرف ولا بيهتم
شو المحرك الفعلي خلفها. هيك تبديل المحرك لاحقًا = تغيير سطر واحد بـ factory.py،
بدون ما نلمس أي كود تاني بالمشروع.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app.models.category import Category


@dataclass
class CategorySuggestion:
    category_id: UUID | None
    category_name: str | None
    confidence: float          # 0.0 إلى 1.0 — تستخدمها الموبايل لتقرر تعرض التصنيف مباشرة أو تسأل المستخدم يأكد
    reasoning: str | None = None  # مفيد لاحقًا لما رشيد يشرح ليش اختار هالتصنيف


class BaseCategorizer(ABC):
    @abstractmethod
    def suggest_category(
        self, note: str, available_categories: list[Category]
    ) -> CategorySuggestion:
        """
        يرجّع أفضل تصنيف مقترح بناءً على نص وصفي كتبه المستخدم (مثال: "قهوة مع صاحبي")
        من ضمن قائمة التصنيفات المتاحة لهذا المستخدم فقط (افتراضية + خاصة فيه).
        """
        raise NotImplementedError
