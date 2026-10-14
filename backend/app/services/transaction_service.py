from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services.categorizer.rule_based import RuleBasedCategorizer
from app.services.categorizer.gemini_based import GeminiCategorizer
from app.services import ai_usage_service
from app.models.ai_usage import AiUsageKind
from app.models.category import Category, CategoryType
from app.models.transaction import CategoryOrigin, Transaction, TransactionSource, TransactionType
from app.models.user import User
from app.schemas.transaction import TransactionQuickLogCreate
from app.services import category_service
from app.services.categorizer.factory import get_categorizer

# تحت هذا الحد من الثقة، ما نطبّق التصنيف تلقائيًا — منرجعه كـ "اقتراح" بس
# ومنسيب القرار النهائي للمستخدم بالموبايل (تصميم يحمي من تصنيف خاطئ صامت)
AUTO_APPLY_CONFIDENCE_THRESHOLD = 0.6


def _accessible_category_or_400(db: Session, user: User, category_id) -> Category:
    """تصنيف افتراضي أو خاص بالمستخدم نفسه فقط (مستخدم ما بيقدر يستخدم تصنيف مستخدم غيره)."""
    category = (
        db.query(Category)
        .filter(Category.id == category_id, or_(Category.is_default.is_(True), Category.user_id == user.id))
        .first()
    )
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="التصنيف غير موجود")
    return category


def create_quick_log_transaction(
    db: Session, user: User, data: TransactionQuickLogCreate
) -> tuple[Transaction, bool, float | None]:
    """
    يرجّع (المعاملة, ai_suggested, suggestion_confidence) عشان الـ route يبني الـ Response
    بدون ما يحتاج يعرف تفاصيل منطق التصنيف.
    """
    ai_suggested = False
    suggestion_confidence: float | None = None
    category_id = data.category_id
    category_origin: CategoryOrigin | None = None

    if category_id is not None:
        _accessible_category_or_400(db, user, category_id)
        category_origin = CategoryOrigin.USER  # المستخدم اختار التصنيف بنفسه (مسار الأيقونات)
    else:
        # مسار التصنيف الذكي: ما وصلنا category_id، لازم نحاول نخمّن من النص
        available_categories = category_service.list_categories_for_user(db, user)
        categorizer = get_categorizer()
        note = data.note or ""
        if isinstance(categorizer, GeminiCategorizer) and note.strip():
            if ai_usage_service.check_quota(db, user, AiUsageKind.CATEGORIZE).allowed:
                suggestion = categorizer.suggest_category(note, available_categories)
                ai_usage_service.record_usage(db, user, AiUsageKind.CATEGORIZE)
            else:
                # تجاوز حد الاستهلاك: منرجع للتصنيف بالكلمات المفتاحية بدل ما نوقف التسجيل
                suggestion = RuleBasedCategorizer().suggest_category(note, available_categories)
        else:
            suggestion = categorizer.suggest_category(note, available_categories)

        if suggestion.category_id is not None:
            category_id = suggestion.category_id
            ai_suggested = True
            suggestion_confidence = suggestion.confidence
            category_origin = CategoryOrigin.AUTO
        # لو ما قدر يخمّن، منسيب category_id فاضي — المعاملة تنحفظ بدون تصنيف
        # والمستخدم يقدر يصنّفها يدويًا لاحقًا من شاشة المعاملات

    transaction = Transaction(
        user_id=user.id,
        category_id=category_id,
        category_origin=category_origin,
        category_confidence=round(suggestion_confidence, 2) if category_origin == CategoryOrigin.AUTO else None,
        amount=data.amount,
        type=data.type,
        source=TransactionSource(data.source),
        note=data.note,
        occurred_at=data.occurred_at or datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction, ai_suggested, suggestion_confidence


def update_transaction_category(db: Session, user: User, transaction_id, category_id) -> Transaction:
    """تصحيح المستخدم للتصنيف: بيصير origin=user وبتنمسح درجة الثقة (القرار صار قرار بشري)."""
    transaction = get_transaction_or_404(db, user, transaction_id)

    if category_id is None:
        transaction.category_id = None
        transaction.category_origin = None
        transaction.category_confidence = None
    else:
        category = _accessible_category_or_400(db, user, category_id)
        matches_type = category.category_type == CategoryType.BOTH or (
            category.category_type == CategoryType.INCOME and transaction.type == TransactionType.INCOME
        ) or (
            category.category_type == CategoryType.EXPENSE and transaction.type == TransactionType.EXPENSE
        )
        if not matches_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="هذا التصنيف لا يناسب نوع المعاملة")
        transaction.category_id = category.id
        transaction.category_origin = CategoryOrigin.USER
        transaction.category_confidence = None

    db.commit()
    db.refresh(transaction)
    return transaction


def list_transactions_for_user(db: Session, user: User, limit: int = 50) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
        .all()
    )


def get_transaction_or_404(db: Session, user: User, transaction_id) -> Transaction:
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة غير موجودة")
    return transaction
