"""
تسجيل "يوم النشاط" (R08): أقل بيانات ممكنة لقياس العودة للاستخدام.

بنسجّل سطر واحد لكل (مستخدم، يوم) عند فتح التطبيق (GET /users/me) أو تسجيل الدخول/إنشاء الحساب.
ما في أي تتبع للشاشات أو الأجهزة أو المحتوى. وأي فشل بالتسجيل ما بيكسر الطلب الأصلي أبدًا.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.active_day import UserActiveDay
from app.models.user import User

logger = logging.getLogger("rasheed.usage")


def local_day(moment: datetime) -> date:
    """اليوم بتوقيت المستخدمين (فرق ثابت عن UTC، افتراضيًا +3 للأردن) — عشان حد اليوم يطابق يومهم الفعلي."""
    offset = timezone(timedelta(hours=settings.ANALYTICS_UTC_OFFSET_HOURS))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(offset).date()


def record_active_day(db: Session, user: User, *, now: datetime | None = None) -> bool:
    """بيرجّع True إذا سجّل يوم جديد، False إذا مسجّل مسبقًا أو صار خطأ (بدون رمي استثناء)."""
    try:
        day = local_day(now or datetime.now(timezone.utc))
        user_id = user.id
        already = db.query(UserActiveDay.id).filter(
            UserActiveDay.user_id == user_id, UserActiveDay.day == day
        ).first()
        if already:
            return False
        db.add(UserActiveDay(user_id=user_id, day=day))
        db.commit()
        return True
    except Exception:  # noqa: BLE001 — القياس ما لازم يعطّل التطبيق (مثلًا سباق على نفس اليوم)
        db.rollback()
        logger.warning("Could not record active day")
        return False
