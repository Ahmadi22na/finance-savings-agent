"""
حدود استهلاك الذكاء الاصطناعي (R11): تجنّب فواتير مفاجئة وإساءة الاستخدام.

ثلاث طبقات حدود (نافذة متحركة 24 ساعة)، وكلها قابلة للضبط من .env (القيمة 0 = بدون حد):
1. لكل مستخدم ولكل نوع استدعاء (chat، receipt_scan، ...): AI_DAILY_LIMIT_<KIND>
2. لكل مستخدم على إجمالي كل الأنواع: AI_DAILY_LIMIT_PER_USER_TOTAL
3. عام لكل التطبيق (قاطع دائرة للميزانية): AI_GLOBAL_DAILY_LIMIT

عند التجاوز: 429 (حد المستخدم) أو 503 (الحد العام) مع هيدر Retry-After.
التنبيهات: سطر WARNING بالـ logs عند الوصول لنسبة AI_ALERT_THRESHOLD_PERCENT من أي حد، وآخر عند بلوغه.
(بدون أي محتوى مستخدم؛ فقط user_id ونوع الاستدعاء والأعداد.)

بوضع AI_PROVIDER=demo ما في تكلفة، فالحدود معطّلة تمامًا.
"""
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_usage import AiUsageEvent, AiUsageKind
from app.models.user import User

logger = logging.getLogger("rasheed.usage")

WINDOW = timedelta(hours=24)
RETENTION = timedelta(days=7)


@dataclass
class QuotaStatus:
    allowed: bool
    reason: str | None = None  # "global" | "user_total" | "user_kind"
    used: int = 0
    limit: int = 0
    retry_after_seconds: int = 0


def quotas_enabled() -> bool:
    return settings.AI_PROVIDER != "demo"


def _kind_limit(kind: AiUsageKind) -> int:
    return {
        AiUsageKind.CHAT: settings.AI_DAILY_LIMIT_CHAT,
        AiUsageKind.RECEIPT_SCAN: settings.AI_DAILY_LIMIT_RECEIPT_SCAN,
        AiUsageKind.SUGGESTION: settings.AI_DAILY_LIMIT_SUGGESTION,
        AiUsageKind.CATEGORIZE: settings.AI_DAILY_LIMIT_CATEGORIZE,
        AiUsageKind.NUDGE: settings.AI_DAILY_LIMIT_NUDGE,
    }[kind]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _scopes(user: User, kind: AiUsageKind) -> list[tuple[str, object, AiUsageKind | None, int]]:
    """(اسم الحد، user_id أو None للعام، النوع أو None للإجمالي، قيمة الحد) — بترتيب الفحص."""
    return [
        ("global", None, None, settings.AI_GLOBAL_DAILY_LIMIT),
        ("user_total", user.id, None, settings.AI_DAILY_LIMIT_PER_USER_TOTAL),
        ("user_kind", user.id, kind, _kind_limit(kind)),
    ]


def _count_and_oldest(db: Session, since: datetime, user_id=None, kind: AiUsageKind | None = None):
    query = db.query(func.count(AiUsageEvent.id), func.min(AiUsageEvent.created_at)).filter(
        AiUsageEvent.created_at >= since
    )
    if user_id is not None:
        query = query.filter(AiUsageEvent.user_id == user_id)
    if kind is not None:
        query = query.filter(AiUsageEvent.kind == kind.value)
    count, oldest = query.one()
    return int(count or 0), (_aware(oldest) if oldest else None)


def check_quota(db: Session, user: User, kind: AiUsageKind, *, now: datetime | None = None) -> QuotaStatus:
    """فحص بدون رمي استثناء (للمسارات الي بتتراجع بلطف، مثل التصنيف الذكي)."""
    if not quotas_enabled():
        return QuotaStatus(allowed=True)

    now = now or datetime.now(timezone.utc)
    since = now - WINDOW
    for reason, user_id, scope_kind, limit in _scopes(user, kind):
        if limit <= 0:
            continue
        used, oldest = _count_and_oldest(db, since, user_id, scope_kind)
        if used >= limit:
            retry = math.ceil((oldest + WINDOW - now).total_seconds()) if oldest else 60
            return QuotaStatus(False, reason, used, limit, max(1, retry))
    return QuotaStatus(allowed=True)


def _human_wait(seconds: int) -> str:
    if seconds < 90:
        return "بعد شوي"
    if seconds < 3600:
        return f"بعد حوالي {math.ceil(seconds / 60)} دقيقة"
    return f"بعد حوالي {math.ceil(seconds / 3600)} ساعة"


def enforce_quota(db: Session, user: User, kind: AiUsageKind, *, now: datetime | None = None) -> None:
    """يرمي 429 (حد المستخدم) أو 503 (الحد العام للتطبيق) مع Retry-After لو تجاوز الحد."""
    result = check_quota(db, user, kind, now=now)
    if result.allowed:
        return

    logger.warning(
        "AI quota exceeded: reason=%s kind=%s user=%s used=%s limit=%s",
        result.reason, kind.value, user.id, result.used, result.limit,
    )
    headers = {"Retry-After": str(result.retry_after_seconds)}
    if result.reason == "global":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="رشيد مشغول كتير هلأ، جرب كمان شوي 🙏",
            headers=headers,
        )
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"وصلت للحد اليومي لاستخدام رشيد الذكي. جرب {_human_wait(result.retry_after_seconds)}",
        headers=headers,
    )


def prune_old_events(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    deleted = (
        db.query(AiUsageEvent)
        .filter(AiUsageEvent.created_at < now - RETENTION)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def record_usage(db: Session, user: User, kind: AiUsageKind, *, now: datetime | None = None) -> None:
    """بنسجّل الاستدعاء الناجح (الفاشل ما بيستهلك من حصة المستخدم)، وبعدين بنفحص إذا لازم نبعت تنبيه."""
    if not quotas_enabled():
        return

    now = now or datetime.now(timezone.utc)
    db.add(AiUsageEvent(user_id=user.id, kind=kind.value, created_at=now))
    db.commit()
    _alert_if_needed(db, user, kind, now)


def _alert_if_needed(db: Session, user: User, kind: AiUsageKind, now: datetime) -> None:
    since = now - WINDOW
    percent = settings.AI_ALERT_THRESHOLD_PERCENT
    for reason, user_id, scope_kind, limit in _scopes(user, kind):
        used, _ = _count_and_oldest(db, since, user_id, scope_kind)

        if reason == "user_total" and used == 1:
            # أول استدعاء للمستخدم بالنافذة: فرصة رخيصة ننظّف فيها السجلات القديمة (مرة باليوم لكل مستخدم)
            prune_old_events(db, now)

        if limit <= 0:
            continue
        if used == limit:
            logger.warning(
                "AI usage limit REACHED: reason=%s kind=%s user=%s used=%s limit=%s",
                reason, kind.value, user.id, used, limit,
            )
        elif percent > 0 and used == math.ceil(limit * percent / 100):
            logger.warning(
                "AI usage approaching limit (%s%%): reason=%s kind=%s user=%s used=%s limit=%s",
                percent, reason, kind.value, user.id, used, limit,
            )
