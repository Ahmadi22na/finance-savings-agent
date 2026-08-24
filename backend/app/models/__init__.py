"""
استيراد كل الـ Models هون ضروري حتى لو ما استخدمناها مباشرة (noqa: F401)،
لأن Alembic بيعتمد على Base.metadata لتوليد الـ Migrations تلقائيًا،
وبدون هذا الاستيراد بعض الجداول ممكن ما تنكشف.
"""
from app.models.user import User, IncomeType  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.goal import Goal, GoalStatus  # noqa: F401
from app.models.transaction import Transaction, TransactionType, TransactionSource  # noqa: F401
from app.models.agent import (  # noqa: F401
    AgentInteraction,
    InteractionTrigger,
    AgentAction,
    AgentActionType,
    AgentActionStatus,
)
