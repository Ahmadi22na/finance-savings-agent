"""
R10 — حالات حدّية لتوزيع الدخل المتغيّر: أخطاء التقريب، مبالغ صفر/سالبة، تجاوز المتاح، تكرار الأهداف.
"""
import pytest

from tests.test_income_and_goal_delete import register_with_persona


def make_goal(client, headers, title, target=1000):
    return client.post("/api/v1/goals", headers=headers, json={"title": title, "target_amount": target}).json()


def make_income(client, headers, amount):
    return client.post("/api/v1/transactions/quick-log", headers=headers, json={
        "amount": amount, "type": "income", "note": "دخل",
    }).json()


def allocate(client, headers, transaction_id, allocations):
    return client.post(
        f"/api/v1/transactions/{transaction_id}/allocate", headers=headers, json={"allocations": allocations},
    )


@pytest.mark.parametrize("bad_amount", [0, -5])
def test_zero_or_negative_allocation_is_rejected(client, db_session, bad_amount):
    headers, _ = register_with_persona(client, db_session, f"07900910{abs(bad_amount):02d}")
    goal = make_goal(client, headers, "سفر")
    income = make_income(client, headers, 100)
    response = allocate(client, headers, income["id"], [{"goal_id": goal["id"], "amount": bad_amount}])
    assert response.status_code == 422


def test_empty_allocation_list_is_rejected(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091010")
    income = make_income(client, headers, 100)
    assert allocate(client, headers, income["id"], []).status_code == 422


def test_split_of_100_into_three_equal_parts_has_no_rounding_leftover(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091011")
    goals = [make_goal(client, headers, f"هدف {i}") for i in range(3)]
    income = make_income(client, headers, 100)

    response = allocate(client, headers, income["id"], [
        {"goal_id": goals[0]["id"], "amount": 33.33},
        {"goal_id": goals[1]["id"], "amount": 33.33},
        {"goal_id": goals[2]["id"], "amount": 33.34},
    ])

    assert response.status_code == 200
    assert response.json()["transaction"]["unallocated_amount"] == 0.0


def test_float_pitfall_0_1_plus_0_2_fully_allocates_0_3(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091012")
    goal_a = make_goal(client, headers, "هدف أ")
    goal_b = make_goal(client, headers, "هدف ب")
    income = make_income(client, headers, 0.3)

    response = allocate(client, headers, income["id"], [
        {"goal_id": goal_a["id"], "amount": 0.1},
        {"goal_id": goal_b["id"], "amount": 0.2},
    ])

    assert response.status_code == 200
    assert response.json()["transaction"]["unallocated_amount"] == 0.0


def test_total_over_available_is_rejected_even_if_each_item_fits(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091013")
    goal_a = make_goal(client, headers, "هدف أ")
    goal_b = make_goal(client, headers, "هدف ب")
    income = make_income(client, headers, 100)

    response = allocate(client, headers, income["id"], [
        {"goal_id": goal_a["id"], "amount": 60},
        {"goal_id": goal_b["id"], "amount": 60},
    ])

    assert response.status_code == 400
    # ما انحفظ شي: الدخل لسا كله غير موزّع
    listed = client.get("/api/v1/transactions", headers=headers).json()
    assert next(t for t in listed if t["id"] == income["id"])["unallocated_amount"] == 100.0


def test_same_goal_twice_in_one_request_is_rejected(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091014")
    goal = make_goal(client, headers, "سفر")
    income = make_income(client, headers, 100)
    response = allocate(client, headers, income["id"], [
        {"goal_id": goal["id"], "amount": 10},
        {"goal_id": goal["id"], "amount": 10},
    ])
    assert response.status_code == 400


def test_cannot_allocate_to_another_users_goal(client, db_session):
    headers_a, _ = register_with_persona(client, db_session, "0790091015")
    headers_b, _ = register_with_persona(client, db_session, "0790091016")
    others_goal = make_goal(client, headers_b, "هدف غيري")
    income = make_income(client, headers_a, 100)
    response = allocate(client, headers_a, income["id"], [{"goal_id": others_goal["id"], "amount": 10}])
    assert response.status_code == 400


def test_sub_cent_amounts_are_rounded_and_never_exceed_the_income(client, db_session):
    """10.004 على دخل 10.00: بيتقرّب لـ 10.00 (خانتين عشريتين)، فما في تجاوز ولا فلس زيادة."""
    headers, _ = register_with_persona(client, db_session, "0790091017")
    goal = make_goal(client, headers, "سفر")
    income = make_income(client, headers, 10)
    response = allocate(client, headers, income["id"], [{"goal_id": goal["id"], "amount": 10.004}])
    assert response.status_code == 200
    body = response.json()
    assert body["transaction"]["unallocated_amount"] == 0.0
    assert body["updated_goals"][0]["current_amount"] == 10.0


def test_clearly_over_the_income_by_a_cent_is_rejected(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091019")
    goal = make_goal(client, headers, "سفر")
    income = make_income(client, headers, 10)
    response = allocate(client, headers, income["id"], [{"goal_id": goal["id"], "amount": 10.01}])
    assert response.status_code == 400


def test_smallest_allocation_of_one_cent_works(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091018")
    goal = make_goal(client, headers, "سفر")
    income = make_income(client, headers, 10)
    response = allocate(client, headers, income["id"], [{"goal_id": goal["id"], "amount": 0.01}])
    assert response.status_code == 200
    assert response.json()["transaction"]["unallocated_amount"] == 9.99


def test_amount_that_rounds_to_zero_is_rejected(client, db_session):
    headers, _ = register_with_persona(client, db_session, "0790091020")
    goal = make_goal(client, headers, "سفر")
    income = make_income(client, headers, 10)
    response = allocate(client, headers, income["id"], [{"goal_id": goal["id"], "amount": 0.004}])
    assert response.status_code == 400
