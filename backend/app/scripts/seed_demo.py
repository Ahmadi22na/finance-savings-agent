"""
سكربت بيانات الـ Demo — أمر واحد بيجهّز حساب تجريبي كامل لعرض رشيد.

التشغيل (من مجلد المشروع الرئيسي، والـ backend شغّال بالـ Docker):

    docker compose exec backend python -m app.scripts.seed_demo

خيارات اختيارية:

    --persona wise|business|energetic   الشخصية المختارة (الافتراضي: energetic)
    --mood energized|concerned|neutral  حالة رشيد المزاجية المطلوب عرضها (الافتراضي: energized)
    --phone / --password                بيانات دخول الحساب التجريبي
    --force                             للسماح بالتشغيل لو ENVIRONMENT=production

ملاحظات تصميم:
- السكربت idempotent: كل مرة بيحذف الحساب التجريبي (بنفس رقم الهاتف فقط) وبيبنيه من جديد،
  فما بيلمس أي مستخدم حقيقي.
- البيانات ثابتة (random بـ seed محدد)، يعني نفس العرض كل مرة.
- بيحتاج إنك شغّلت `alembic upgrade head` قبل (التصنيفات والشخصيات بتجي من الـ Migrations).
- الاقتراحات المعلّقة (Pending) المزروعة هون بيانات عرض فقط؛ الاقتراحات الحقيقية بتضل
  تنولّد من الـ Backend لما تفتح الشاشة (مثلاً تصنيف المعاملات غير المصنّفة عبر Gemini).
"""
import argparse
import hashlib
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from app import models  # noqa: F401  (تسجيل كل الـ Models)
from app.agent.mood_engine import compute_mood_state
from app.config import settings
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models.agent import (
    AgentAction, AgentActionStatus, AgentActionType, AgentInteraction, InteractionTrigger,
)
from app.models.category import Category
from app.models.goal import Goal, GoalStatus
from app.models.income_allocation import IncomeAllocation
from app.models.persona import Persona
from app.models.transaction import Transaction, TransactionSource, TransactionType
from app.models.user import IncomeType, User

DEMO_NAME = "سامر (ديمو)"
DAYS_BACK = 60

# (التصنيف، ملاحظات محتملة، أقل مبلغ، أعلى مبلغ، احتمال حدوثه باليوم)
EXPENSE_TEMPLATES = [
    ("مطاعم وكافيهات", ["قهوة", "فلافل وحمص", "غدا", "عصير وساندويش"], 2, 9, 0.60),
    ("مواصلات", ["تكسي", "باص", "أوبر"], 1.5, 6, 0.45),
    ("بقالة وسوبرماركت", ["خضار وفواكه", "أغراض البيت"], 5, 22, 0.22),
    ("ترفيه", ["سينما", "لعبة"], 5, 15, 0.05),
    ("تسوق", ["لبس"], 15, 40, 0.04),
    ("صحة", ["صيدلية"], 4, 10, 0.03),
]

# مصاريف ثابتة بأيام محددة (قبل كم يوم): (التصنيف، الملاحظة، المبلغ)
FIXED_EXPENSES = {
    9: ("فواتير واشتراكات", "تعبئة خط موبايل", 7),
    39: ("فواتير واشتراكات", "تعبئة خط موبايل", 7),
    24: ("فواتير واشتراكات", "فاتورة انترنت", 18),
    54: ("فواتير واشتراكات", "فاتورة انترنت", 18),
    14: ("حلاقة وعناية", "حلاقة", 4),
    44: ("حلاقة وعناية", "حلاقة", 4),
}

# أسبوع "تبذير" يظهر فقط بوضع --mood concerned (يخلّي رشيد قلقان فعلاً حسب الـ Mood Engine)
SPENDING_SPIKE = {
    1: ("تسوق", "شراء لبس جديد", 52),
    2: ("مطاعم وكافيهات", "عشا مع الشباب", 24),
    3: ("ترفيه", "سهرة", 30),
    4: ("مواصلات", "بنزين", 18),
    5: ("تسوق", "اكسسوارات موبايل", 21),
}

INCOME_AMOUNTS = [20, 25, 30, 35, 40, 45, 50, 60]
BIG_INCOMES = {33: ("مشروع تصميم", 150), 12: ("مشروع تصميم", 120)}


def _day(now: datetime, days_ago: int, rng: random.Random) -> datetime:
    """وقت عشوائي معقول بنهار اليوم المطلوب، وما بيطلع بالمستقبل أبدًا."""
    base = (now - timedelta(days=days_ago)).replace(
        hour=rng.randint(8, 21), minute=rng.randint(0, 59), second=0, microsecond=0
    )
    return min(base, now - timedelta(minutes=5))


def build_demo(db, persona_key: str, mood: str, phone: str, password: str) -> dict:
    rng = random.Random(7)
    now = datetime.now(timezone.utc)

    persona = db.query(Persona).filter(Persona.key == persona_key).first()
    if persona is None:
        sys.exit(f"الشخصية '{persona_key}' مش موجودة بقاعدة البيانات — شغّل alembic upgrade head أول.")

    cats = {c.name: c for c in db.query(Category).filter(Category.is_default.is_(True)).all()}
    income_cat = cats.get("راتب / دخل")
    if income_cat is None:
        sys.exit("التصنيفات الافتراضية مش موجودة — شغّل alembic upgrade head أول.")

    def cat(name: str):
        return cats.get(name) or cats.get("أخرى")

    # --- حذف الحساب التجريبي القديم (بنفس رقم الهاتف فقط) ---
    old = db.query(User).filter(User.phone == phone).first()
    if old is not None:
        tx_ids = [t.id for t in db.query(Transaction.id).filter(Transaction.user_id == old.id).all()]
        if tx_ids:
            db.query(IncomeAllocation).filter(IncomeAllocation.transaction_id.in_(tx_ids)).delete(
                synchronize_session=False
            )
        db.delete(old)
        db.commit()

    # --- المستخدم ---
    user = User(
        id=uuid.uuid4(), name=DEMO_NAME, phone=phone, hashed_password=hash_password(password),
        income_type=IncomeType.VARIABLE, avg_monthly_income_estimate=450,
        estimated_monthly_essentials=180, persona_id=persona.id, has_completed_onboarding=True,
    )
    db.add(user)
    db.flush()

    # --- الأهداف ---
    # الـ Mood Engine بيعتمد على آخر هدف نشط انشأ (created_at)، فهدف "اللابتوب" لازم ينشأ أخير.
    energized = mood == "energized"
    laptop_current = 510 if energized else 210
    today = date.today()
    goal_specs = [
        # (العنوان، الأيقونة، الهدف، الحالي، قبل كم يوم أُنشئ، الموعد النهائي، الأولوية، متكرر)
        ("صندوق الطوارئ", "shield", 1000, 80, 68, None, 3, False),
        ("رحلة العقبة", "plane", 250, 70, 66, today + timedelta(days=21), 1, False),
        ("اشتراك النادي", "dumbbell", 40, 40, 62, None, 0, True),
        ("لابتوب جديد", "laptop", 600, laptop_current, 60, today + timedelta(days=90), 2, False),
    ]
    goals = []
    for title, icon, target, current, created_days_ago, deadline, priority, recurring in goal_specs:
        goals.append(Goal(
            id=uuid.uuid4(), user_id=user.id, title=title, icon=icon,
            target_amount=target, current_amount=current, priority=priority,
            is_recurring=recurring,
            last_reset_month=today.strftime("%Y-%m") if recurring else None,
            deadline=deadline,
            status=GoalStatus.ACHIEVED if current >= target else GoalStatus.ACTIVE,
            created_at=now - timedelta(days=created_days_ago),
        ))
    db.add_all(goals)
    db.flush()
    laptop = goals[-1]

    # --- المعاملات ---
    transactions: list[Transaction] = []
    incomes: list[Transaction] = []

    def add_tx(kind, category, amount, note, when, source=TransactionSource.MANUAL, raw=None, ref=None):
        tx = Transaction(
            id=uuid.uuid4(), user_id=user.id, category_id=category.id if category else None,
            amount=amount, type=kind, source=source, note=note, occurred_at=when,
            raw_source_data=raw, external_ref=ref, created_at=when,
        )
        transactions.append(tx)
        return tx

    # دخل غير منتظم: كل 1-3 أيام تقريبًا، مع مشروعين أكبر (نمط فريلانسر/عامل يومية)
    income_count = 0
    day = DAYS_BACK - 1
    while day >= 0:
        if day in BIG_INCOMES:
            note, amount = BIG_INCOMES[day]
        else:
            note, amount = rng.choice(["أجرة يوم", "شغل جانبي", "دوام جزئي"]), rng.choice(INCOME_AMOUNTS)
        when = _day(now, day, rng)
        income_count += 1
        if income_count % 4 == 0:  # كل رابع دخل بيجي من رسالة CliQ (مصدر SMS)
            body = f"You have successfully received {amount:.3f} JOD from Client {income_count} via CliQ"
            tx = add_tx(
                TransactionType.INCOME, income_cat, amount, note, when, TransactionSource.SMS,
                raw={"body": body, "sender": "BANK"},
                ref=hashlib.sha256(f"{body}{when.isoformat()}".encode()).hexdigest(),
            )
        else:
            tx = add_tx(TransactionType.INCOME, income_cat, amount, note, when)
        incomes.append(tx)
        day -= rng.randint(1, 3)

    # مصاريف يومية
    for days_ago in range(DAYS_BACK - 1, -1, -1):
        recent = days_ago <= 6
        damp = 0.6 if (recent and mood != "concerned") else 1.0  # أسبوع هادي بغير وضع القلق
        for cat_name, notes, low, high, prob in EXPENSE_TEMPLATES:
            if rng.random() < prob * damp:
                amount = round(rng.uniform(low, high) * 2) / 2  # مبالغ مقرّبة لنصف دينار
                is_ocr = cat_name == "بقالة وسوبرماركت" and rng.random() < 0.5
                add_tx(
                    TransactionType.EXPENSE, cat(cat_name), amount, rng.choice(notes), _day(now, days_ago, rng),
                    TransactionSource.OCR if is_ocr else TransactionSource.MANUAL,
                    raw={"merchant": "سوبرماركت", "confidence": 0.9} if is_ocr else None,
                )
        if days_ago in FIXED_EXPENSES:
            c, note, amount = FIXED_EXPENSES[days_ago]
            add_tx(TransactionType.EXPENSE, cat(c), amount, note, _day(now, days_ago, rng))
        if mood == "concerned" and days_ago in SPENDING_SPIKE:
            c, note, amount = SPENDING_SPIKE[days_ago]
            add_tx(TransactionType.EXPENSE, cat(c), amount, note, _day(now, days_ago, rng))

    # معاملات بدون تصنيف (لعرض اقتراحات تصحيح التصنيف)
    night_out = add_tx(TransactionType.EXPENSE, None, 18, "سهرة مع الشباب", _day(now, 3, rng))
    add_tx(TransactionType.EXPENSE, None, 12, "هدية لصاحبي", _day(now, 5, rng))
    add_tx(TransactionType.EXPENSE, None, 4.5, "اشتراك سبوتيفاي", _day(now, 8, rng))

    db.add_all(transactions)
    db.flush()

    # --- توزيع الدخل على الأهداف (متطابق تمامًا مع current_amount لكل هدف) ---
    incomes.sort(key=lambda t: t.occurred_at)
    remaining = {t.id: float(t.amount) for t in incomes}
    if sum(remaining.values()) < sum(float(g.current_amount) for g in goals):
        sys.exit("إجمالي الدخل المولّد أقل من المطلوب توزيعه — عدّل مبالغ الدخل بالسكربت.")
    for index, goal in enumerate(goals):
        need = float(goal.current_amount)
        rotated = incomes[index * 5:] + incomes[:index * 5]
        for tx in rotated:
            if need <= 0:
                break
            take = round(min(remaining[tx.id], need), 2)
            if take <= 0:
                continue
            db.add(IncomeAllocation(transaction_id=tx.id, goal_id=goal.id, amount=take))
            remaining[tx.id] = round(remaining[tx.id] - take, 2)
            need = round(need - take, 2)
        if need > 0.01:
            sys.exit(f"ما قدرت أوزّع كامل المبلغ على هدف '{goal.title}'.")

    # --- سجل المحادثة مع رشيد (قديم كفاية عشان ما يعطّل الـ Nudge) ---
    left = int(float(laptop.target_amount) - float(laptop.current_amount))
    chat = [
        (5, True, InteractionTrigger.USER_CHAT, "كم باقيلي عشان اجيب اللابتوب؟"),
        (5, False, InteractionTrigger.USER_CHAT,
         f"باقيلك {left} دينار على اللابتوب. وإنت ماشي منيح، كمل بنفس الوتيرة."),
        (2, True, InteractionTrigger.USER_CHAT, "شو رأيك أحوّل جزء من دخل اليوم للرحلة؟"),
        (2, False, InteractionTrigger.USER_CHAT, "فكرة حلوة، الرحلة موعدها أقرب فخلّيها أولوية."),
        (20, False, InteractionTrigger.GOAL_MILESTONE, "خلصت أول 30% من هدف اللابتوب. بداية ممتازة!"),
    ]
    for days_ago, from_user, trigger, text in chat:
        db.add(AgentInteraction(
            id=uuid.uuid4(), user_id=user.id, trigger_type=trigger, message=text,
            is_from_user=from_user, created_at=now - timedelta(days=days_ago, hours=1),
        ))

    # --- اقتراحات معلّقة جاهزة للعرض ---
    ent = cat("ترفيه")
    db.add(AgentAction(
        id=uuid.uuid4(), user_id=user.id, action_type=AgentActionType.SUGGEST_CATEGORY_CORRECTION,
        status=AgentActionStatus.PENDING,
        payload={
            "transaction_id": str(night_out.id), "new_category_id": str(ent.id),
            "new_category_name": ent.name, "transaction_note": night_out.note,
            "transaction_amount": float(night_out.amount),
        },
        reasoning="'سهرة مع الشباب' أقرب لتصنيف الترفيه من أي تصنيف ثاني.",
    ))
    if energized:
        amount = round((float(laptop.target_amount) - float(laptop.current_amount)) * 0.2)
        db.add(AgentAction(
            id=uuid.uuid4(), user_id=user.id, action_type=AgentActionType.SUGGEST_GOAL_CONTRIBUTION,
            status=AgentActionStatus.PENDING,
            payload={"goal_id": str(laptop.id), "goal_title": laptop.title, "amount": amount},
            reasoning=f"إنت قريب من هدف '{laptop.title}' ({laptop.progress_percentage}%)! دفعة بسيطة بتقرّبك أكتر.",
        ))

    db.commit()
    db.refresh(user)
    return {
        "user": user, "goals": len(goals), "transactions": len(transactions),
        "mood": compute_mood_state(db, user),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="تجهيز حساب Demo كامل لتطبيق رشيد")
    parser.add_argument("--persona", choices=["wise", "business", "energetic"], default="energetic")
    parser.add_argument("--mood", choices=["energized", "concerned", "neutral"], default="energized")
    parser.add_argument("--phone", default="0799000000")
    parser.add_argument("--password", default="demo1234")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if settings.ENVIRONMENT == "production" and not args.force:
        sys.exit("ENVIRONMENT=production — السكربت مخصص للتطوير والعرض. استخدم --force لو متأكد.")

    db = SessionLocal()
    try:
        result = build_demo(db, args.persona, args.mood, args.phone, args.password)
    finally:
        db.close()

    print("تم تجهيز حساب الـ Demo")
    print(f"  رقم الهاتف:    {args.phone}")
    print(f"  كلمة المرور:   {args.password}")
    print(f"  الشخصية:       {args.persona}")
    print(f"  الأهداف:       {result['goals']}   المعاملات: {result['transactions']}")
    print(f"  مزاج رشيد الحالي (حسب الـ Mood Engine): {result['mood'].state.value}")
    if result["mood"].state.value != args.mood:
        print(f"  تنبيه: المزاج المطلوب كان '{args.mood}' بس الناتج مختلف — خبّرني لأعدّل البيانات.")


if __name__ == "__main__":
    main()
