"""اختبارات: تسجيل الدخل عبر المحادثة، وحذف الأهداف."""
import uuid

import pytest

from app.agent.providers.base import AgentReply
from app.agent.providers import factory as provider_factory
from app.models.persona import Persona
from app.services import agent_chat_service, agent_action_service


class FakeReplyProvider:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_reply(self, system_prompt, user_message, history=None):
        self.calls.append((system_prompt, user_message, history))
        return AgentReply(text=self.text)


def patch_provider(monkeypatch, fake):
    monkeypatch.setattr(provider_factory, "get_ai_provider", lambda: fake)
    monkeypatch.setattr(agent_chat_service, "get_ai_provider", lambda: fake)


def register_with_persona(client, db_session, phone):
    # اختبارات زي test_cannot_delete_another_users_goal بتسجل مستخدمين اثنين
    # بنفس الاختبار — فبدون هالفحص، ثاني استدعاء بيصطدم بقيد UNIQUE على key.
    persona = db_session.query(Persona).filter(Persona.key == "wise").first()
    if persona is None:
        persona = Persona(
            key="wise", display_name="رشيد الحكيم", tagline="خبرة",
            color_hex="#1B4332", system_prompt="كن حكيمًا.", is_active=True,
        )
        db_session.add(persona)
        db_session.commit()

    reg = client.post("/api/v1/auth/register", json={
        "name": "مستخدم اختبار", "phone": phone, "password": "testpassword123",
    }).json()
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    client.post("/api/v1/onboarding/complete", headers=headers, json={
        "income_type": "variable", "persona_id": str(persona.id),
        "goal_title": "هدف قديم", "goal_target_amount": 500,
    })
    from app.models.user import User
    user = db_session.query(User).filter(User.phone == phone).first()
    return headers, user


# ---------- تسجيل الدخل عبر المحادثة ----------

def test_income_log_marker_creates_pending_action(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790010001")
    reply_text = (
        'حلو! سجلتلك ياها. '
        '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "اشتغلت اليوم واجاني 25 دينار",
    })
    assert response.status_code == 200
    assert "INCOME_LOG_PROPOSAL" not in response.json()["reply"]

    pending = agent_action_service.list_pending_actions(db_session, user)
    income_actions = [a for a in pending if a.action_type.value == "suggest_income_log"]
    assert len(income_actions) == 1
    assert income_actions[0].payload["amount"] == 25


def test_income_and_goal_proposal_in_same_reply_dont_leak_markers_into_reasoning(
    client, db_session, monkeypatch
):
    """
    السيناريو الحقيقي يلي طلع بالتجربة: رشيد يسجل دخل ويقترح هدف بنفس الرد
    (مثلاً "اجاني 25 دينار، وبدي أوفر لشراء ملابس بـ200 دينار آخر السنة").
    قبل الإصلاح، reasoning اقتراح الدخل كان يحتوي حرفيًا على نص كتلة
    <<<GOAL_PROPOSAL>>> الخام لأنها ما كانت انشالت بعد وقت أخذ الـ reasoning.
    """
    headers, user = register_with_persona(client, db_session, "0790010013")
    reply_text = (
        'تمام يا أستاذ، سجلتلك الدخل. وجهزتلك خطة لهدفك كمان. '
        '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
        '<<<GOAL_PROPOSAL>>>{"title": "ملابس نهاية السنة", "target_amount": 200}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    response = client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "اجاني 25 دينار، وبدي أوفر 200 دينار لملابس آخر السنة",
    })
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "<<<" not in reply and ">>>" not in reply

    pending = agent_action_service.list_pending_actions(db_session, user)
    income_action = next(a for a in pending if a.action_type.value == "suggest_income_log")
    goal_action = next(a for a in pending if a.action_type.value == "suggest_goal_creation")

    # هاد بالضبط الإصلاح: ولا كتلة خام لازم تظهر جوا reasoning أي اقتراح
    for action in (income_action, goal_action):
        assert "<<<" not in action.reasoning
        assert ">>>" not in action.reasoning


def test_confirming_income_log_creates_real_income_transaction(client, db_session, monkeypatch):
    headers, user = register_with_persona(client, db_session, "0790010002")
    reply_text = '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 25 دينار"})

    pending = agent_action_service.list_pending_actions(db_session, user)
    action_id = str(pending[0].id)

    confirm_response = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert confirm_response.status_code == 200

    transactions_response = client.get("/api/v1/transactions", headers=headers)
    incomes = [t for t in transactions_response.json() if t["type"] == "income"]
    assert any(t["amount"] == 25 for t in incomes)


def test_income_report_does_not_trigger_goal_creation(client, db_session, monkeypatch):
    """
    محاكاة الـ Bug الفعلي يلي انلقط: مزود وهمي "مطيع" بيتبع التعليمات الصح
    (ما يستخدم GOAL_PROPOSAL لخبر دخل) — هاد اختبار توثيقي للسلوك المتوقع،
    مش ضمان سلوك Gemini الفعلي (هاد تحكمه صياغة الـ Prompt، مش الكود).
    """
    headers, user = register_with_persona(client, db_session, "0790010003")
    reply_text = '<<<INCOME_LOG_PROPOSAL>>>{"amount": 25, "note": "شغل يوم"}<<<END>>>'
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "اجاني 25 دينار"})

    pending = agent_action_service.list_pending_actions(db_session, user)
    goal_proposals = [a for a in pending if a.action_type.value == "suggest_goal_creation"]
    assert len(goal_proposals) == 0


# ---------- حذف هدف ----------

def test_delete_goal(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010004")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف للحذف", "target_amount": 100,
    }).json()

    delete_response = client.delete(f"/api/v1/goals/{goal['id']}", headers=headers)
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/goals", headers=headers)
    remaining_ids = [g["id"] for g in list_response.json()]
    assert goal["id"] not in remaining_ids


def test_delete_nonexistent_goal_returns_404(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010005")
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/api/v1/goals/{fake_id}", headers=headers)
    assert response.status_code == 404


def test_cannot_delete_another_users_goal(client, db_session):
    headers1, user1 = register_with_persona(client, db_session, "0790010006")
    headers2, user2 = register_with_persona(client, db_session, "0790010007")

    goal = client.post("/api/v1/goals", headers=headers1, json={
        "title": "هدف خاص", "target_amount": 100,
    }).json()

    response = client.delete(f"/api/v1/goals/{goal['id']}", headers=headers2)
    assert response.status_code == 404


# ---------- ترتيب أولوية الخطط ----------

def test_new_goal_gets_next_priority_after_existing_ones(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010008")
    first = client.post("/api/v1/goals", headers=headers, json={
        "title": "أول خطة", "target_amount": 100,
    }).json()
    second = client.post("/api/v1/goals", headers=headers, json={
        "title": "ثاني خطة", "target_amount": 100,
    }).json()

    assert second["priority"] > first["priority"]


def test_reorder_goals_updates_priority_and_list_order(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010009")
    goal_a = client.post("/api/v1/goals", headers=headers, json={
        "title": "أا", "target_amount": 100,
    }).json()
    goal_b = client.post("/api/v1/goals", headers=headers, json={
        "title": "بب", "target_amount": 100,
    }).json()
    goal_c = client.post("/api/v1/goals", headers=headers, json={
        "title": "جج", "target_amount": 100,
    }).json()

    # register_with_persona بينشئ خطة "هدف قديم" أصلاً وقت onboarding —
    # لازم نضمّها بالترتيب الجديد كمان، وإلا الطلب هيرفض (كل الخطط أو ولا وحدة).
    existing_ids = [g["id"] for g in client.get("/api/v1/goals", headers=headers).json()]
    onboarding_goal_id = next(
        gid for gid in existing_ids
        if gid not in (goal_a["id"], goal_b["id"], goal_c["id"])
    )

    new_order = [goal_c["id"], goal_a["id"], onboarding_goal_id, goal_b["id"]]
    response = client.put(
        "/api/v1/goals/reorder", headers=headers, json={"ordered_goal_ids": new_order}
    )
    assert response.status_code == 200

    list_response = client.get("/api/v1/goals", headers=headers)
    active_ids_in_order = [g["id"] for g in list_response.json()]
    assert active_ids_in_order == new_order


def test_reorder_rejects_incomplete_goal_list(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010010")
    goal_a = client.post("/api/v1/goals", headers=headers, json={
        "title": "أا", "target_amount": 100,
    }).json()
    client.post("/api/v1/goals", headers=headers, json={
        "title": "بب", "target_amount": 100,
    })

    response = client.put(
        "/api/v1/goals/reorder", headers=headers, json={"ordered_goal_ids": [goal_a["id"]]}
    )
    assert response.status_code == 400


def test_reorder_rejects_goal_belonging_to_another_user(client, db_session):
    headers1, user1 = register_with_persona(client, db_session, "0790010011")
    headers2, user2 = register_with_persona(client, db_session, "0790010012")

    goal1 = client.post("/api/v1/goals", headers=headers1, json={
        "title": "خطتي", "target_amount": 100,
    }).json()
    client.post("/api/v1/goals", headers=headers2, json={
        "title": "خطة غيري", "target_amount": 100,
    })

    response = client.put(
        "/api/v1/goals/reorder", headers=headers2, json={"ordered_goal_ids": [goal1["id"]]}
    )
    assert response.status_code == 400


# ---------- المصاريف الثابتة الشهرية (is_recurring + Lazy Reset) ----------

def test_recurring_goal_created_with_current_month_marked(client, db_session):
    headers, user = register_with_persona(client, db_session, "0790010014")
    response = client.post("/api/v1/goals", headers=headers, json={
        "title": "إيجار", "target_amount": 150, "is_recurring": True,
    })
    assert response.status_code == 201
    assert response.json()["is_recurring"] is True


def test_recurring_goal_achieved_this_month_stays_achieved(client, db_session):
    """لسا بنفس الشهر يلي اكتملت فيه — لازم تضل ACHIEVED، ما تنصفر قبل الأوان."""
    headers, user = register_with_persona(client, db_session, "0790010015")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "اشتراك", "target_amount": 20, "is_recurring": True,
    }).json()

    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 20})

    listing = client.get("/api/v1/goals", headers=headers).json()
    updated = next(g for g in listing if g["id"] == goal["id"])
    assert updated["status"] == "achieved"
    assert updated["current_amount"] == 20.0


def test_recurring_goal_resets_when_month_changes(client, db_session, monkeypatch):
    """
    هاد الاختبار الأساسي لكل ميزة الـ Lazy Reset: نحاكي "مرور شهر" بتزييف
    last_reset_month لشهر سابق يدويًا (بدل ما ننتظر تقويم حقيقي)، وبعدين
    نتأكد إنه أول قراءة بعدها بترجّع الخطة نشطة بـ 0 تلقائيًا.
    """
    headers, user = register_with_persona(client, db_session, "0790010016")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "اشتراك", "target_amount": 20, "is_recurring": True,
    }).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 20})

    from app.models.goal import Goal, GoalStatus
    db_goal = db_session.query(Goal).filter(Goal.id == uuid.UUID(goal["id"])).first()
    assert db_goal.status == GoalStatus.ACHIEVED
    db_goal.last_reset_month = "2000-01"  # شهر بعيد بالماضي — أكيد مختلف عن الحالي
    db_session.commit()

    listing = client.get("/api/v1/goals", headers=headers).json()
    reset_goal = next(g for g in listing if g["id"] == goal["id"])
    assert reset_goal["status"] == "active"
    assert reset_goal["current_amount"] == 0.0


def test_non_recurring_goal_never_auto_resets(client, db_session):
    """خطة عادية (مش is_recurring) لازم تضل ACHIEVED للأبد، حتى لو الشهر تغيّر."""
    headers, user = register_with_persona(client, db_session, "0790010017")
    goal = client.post("/api/v1/goals", headers=headers, json={
        "title": "هدف عادي", "target_amount": 20,
    }).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", headers=headers, json={"amount": 20})

    from app.models.goal import Goal
    db_goal = db_session.query(Goal).filter(Goal.id == uuid.UUID(goal["id"])).first()
    db_goal.last_reset_month = "2000-01"  # حتى لو انزرعت هاي القيمة صدفة، ما لازم تأثر
    db_session.commit()

    listing = client.get("/api/v1/goals", headers=headers).json()
    unchanged = next(g for g in listing if g["id"] == goal["id"])
    assert unchanged["status"] == "achieved"
    assert unchanged["current_amount"] == 20.0


def test_chat_goal_proposal_with_is_recurring_creates_recurring_goal(
    client, db_session, monkeypatch
):
    """المسار الكامل: رشيد يكتشف من كلام المستخدم إنه التزام شهري متكرر
    (مش مصروف لمرة وحدة)، ويضمّن is_recurring:true بالاقتراح — وبعد التأكيد
    لازم تنطلع خطة حقيقية is_recurring=True فعليًا."""
    headers, user = register_with_persona(client, db_session, "0790010018")
    reply_text = (
        'ظبطتلك! <<<GOAL_PROPOSAL>>>{"title": "إيجار البيت", "target_amount": 150, '
        '"breakdown": [], "is_recurring": true}<<<END>>>'
    )
    fake = FakeReplyProvider(reply_text)
    patch_provider(monkeypatch, fake)

    client.post("/api/v1/agent/chat", headers=headers, json={
        "message": "بدي أخصص لإيجار البيت كل شهر 150 دينار",
    })

    pending = agent_action_service.list_pending_actions(db_session, user)
    action = next(a for a in pending if a.action_type.value == "suggest_goal_creation")
    assert action.payload["is_recurring"] is True

    confirm_response = client.post(
        f"/api/v1/agent/actions/{action.id}/confirm", headers=headers
    )
    assert confirm_response.status_code == 200

    from app.models.goal import Goal
    new_goal = db_session.query(Goal).filter(Goal.title == "إيجار البيت").first()
    assert new_goal is not None
    assert new_goal.is_recurring is True
    assert new_goal.last_reset_month is not None
