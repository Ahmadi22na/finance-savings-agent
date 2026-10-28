"""
التحويل الداخلي بين حسابين للمستخدم — المرحلة 1 / الدفعة 1.B.

التحويل = معاملتان بنفس transfer_group_id، بتنشأ بعملية ذرّية وحدة (commit واحد):
  - طرف خروج  type=expense  بالحساب المحوَّل منه
  - طرف دخول  type=income   بالحساب المحوَّل إليه
مستثنى من الدخل/المصروف الحقيقي (مزاج رشيد، المصاريف الأساسية، التوزيع على الأهداف، المقاييس، اقتراحات التصنيف)،
وبينعكس تلقائيًا على رصيدي الحسابين (لأن الرصيد بيعتمد على نوع المعاملة).
تعديل/حذف أي طرف بيطبّق على الطرفين (transaction_edit_service)، فما بيصير تحويل غير متوازن.
القفل: الحسابين بقفل مشترك (FOR SHARE) بترتيب ثابت، فتحويلين معاكسين متزامنين ما بيعملوا deadlock، وما بينحذف/بينؤرشف
حساب بنص التحويل.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.money import to_money
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import User
from app.schemas.transfer import TransferCreate, TransferOut
from app.services import financial_account_service


def create_transfer(db: Session, user: User, data: TransferCreate) -> TransferOut:
    if data.from_account_id == data.to_account_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ما بتقدر تحوّل من حساب لنفسه")

    try:
        financial_account_service.lock_accounts_for_link(db, user, [data.from_account_id, data.to_account_id])

        group_id = uuid.uuid4()
        amount = to_money(data.amount)
        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        note = (data.note or "").strip() or None

        def leg(kind: TransactionType, account_id: uuid.UUID) -> Transaction:
            return Transaction(
                user_id=user.id, account_id=account_id, amount=amount, type=kind, source=TransactionSource.MANUAL,
                note=note, occurred_at=occurred_at, is_transfer=True, transfer_group_id=group_id,
            )

        out_leg = leg(TransactionType.EXPENSE, data.from_account_id)
        db.add(out_leg)
        db.flush()
        in_leg = leg(TransactionType.INCOME, data.to_account_id)
        db.add(in_leg)
        db.flush()
        result = TransferOut(
            transfer_group_id=group_id, amount=float(amount), occurred_at=occurred_at, note=note,
            from_account_id=data.from_account_id, to_account_id=data.to_account_id,
            out_transaction_id=out_leg.id, in_transaction_id=in_leg.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result
