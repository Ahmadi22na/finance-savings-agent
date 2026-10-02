"""Module documentation."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app.models.category import Category


@dataclass
class CategorySuggestion:
    category_id: UUID | None
    category_name: str | None
    confidence: float
    reasoning: str | None = None


class BaseCategorizer(ABC):
    @abstractmethod
    def suggest_category(
        self, note: str, available_categories: list[Category]
    ) -> CategorySuggestion:
        """Suggest category documentation."""
        raise NotImplementedError
