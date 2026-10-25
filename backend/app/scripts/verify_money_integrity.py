"""
فحص سلامة الأرقام المالية — للقراءة فقط (ما بيعدّل أي شي).

التشغيل (داخل حاوية الباكاند، مثل seed_demo):
    python -m app.scripts.verify_money_integrity
    python -m app.scripts.verify_money_integrity --out before_0B.json
    python -m app.scripts.verify_money_integrity --database-url postgresql://...

يطبع ملخص أعداد ومجاميع (للمقارنة قبل/بعد كل مهاجرة)، وفحوصات:
  FAIL  = كسر فعلي بسلامة البيانات (الكود يرجّع خروج 1)
  WARN  = ملاحظة تستاهل نظرة، مش بالضرورة خطأ
وإذا جدول goal_movements موجود (من الدفعة 0.C) بيفحص كمان أن مجموع الحركات = current_amount.
"""
import argparse
import json
import sys

from sqlalchemy import create_engine, inspect, text

from app.config import settings

TYPE_TXT = "lower(CAST(t.type AS TEXT))"
STATUS_TXT = "lower(CAST(g.status AS TEXT))"
MAX_ROWS = 10


def _short(value):
    return str(value)[:8]


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only money integrity check")
    parser.add_argument("--database-url", default=settings.DATABASE_URL)
    parser.add_argument("--out", help="يحفظ الملخص بملف JSON للمقارنة لاحقًا")
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    summary: dict = {}
    failures: list[str] = []
    warnings: list[str] = []

    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION READ ONLY"))

        tables = set(inspect(conn).get_table_names())
        has_movements = "goal_movements" in tables
        has_accounts = "financial_accounts" in tables

        def scalar(sql):
            return conn.execute(text(sql)).scalar()

        def rows(sql):
            return conn.execute(text(sql)).fetchall()

        # ---- ملخص (للمقارنة قبل/بعد) ----
        summary["users"] = scalar("SELECT COUNT(*) FROM users")
        summary["transactions"] = scalar("SELECT COUNT(*) FROM transactions")
        summary["goals"] = scalar("SELECT COUNT(*) FROM goals")
        summary["income_allocations"] = scalar("SELECT COUNT(*) FROM income_allocations")
        for kind in ("income", "expense"):
            summary[f"sum_{kind}"] = str(
                scalar(f"SELECT COALESCE(SUM(t.amount),0) FROM transactions t WHERE {TYPE_TXT} = '{kind}'")
            )
        summary["sum_goal_current"] = str(scalar("SELECT COALESCE(SUM(current_amount),0) FROM goals"))
        summary["sum_goal_target"] = str(scalar("SELECT COALESCE(SUM(target_amount),0) FROM goals"))
        summary["sum_allocations"] = str(scalar("SELECT COALESCE(SUM(amount),0) FROM income_allocations"))
        summary["goal_movements_table"] = has_movements
        if has_movements:
            summary["goal_movements"] = scalar("SELECT COUNT(*) FROM goal_movements")
        if has_accounts:
            summary["financial_accounts"] = scalar("SELECT COUNT(*) FROM financial_accounts")
            summary["account_balance_snapshots"] = scalar("SELECT COUNT(*) FROM account_balance_snapshots")
            summary["transactions_with_account"] = scalar("SELECT COUNT(*) FROM transactions WHERE account_id IS NOT NULL")

        def check(bucket, label, sql):
            found = rows(sql)
            if found:
                bucket.append(f"{label}: {len(found)}")
                print(f"[{'FAIL' if bucket is failures else 'WARN'}] {label} ({len(found)})")
                for row in found[:MAX_ROWS]:
                    print("    ", tuple(_short(v) if i == 0 else str(v) for i, v in enumerate(row)))
                if len(found) > MAX_ROWS:
                    print(f"     ... و{len(found) - MAX_ROWS} أخرى")

        # ---- FAIL ----
        check(failures, "دخل موزَّع أكتر من مبلغه", """
            SELECT t.id, t.amount, SUM(a.amount) FROM transactions t
            JOIN income_allocations a ON a.transaction_id = t.id
            GROUP BY t.id, t.amount HAVING SUM(a.amount) > t.amount""")
        check(failures, "توزيع مربوط بمعاملة ليست دخلاً", f"""
            SELECT a.id, t.type FROM income_allocations a
            JOIN transactions t ON t.id = a.transaction_id WHERE {TYPE_TXT} <> 'income'""")
        check(failures, "معاملة بمبلغ <= 0", "SELECT id, amount FROM transactions WHERE amount <= 0")
        check(failures, "توزيع بمبلغ <= 0", "SELECT id, amount FROM income_allocations WHERE amount <= 0")
        check(failures, "هدف current_amount سالب", "SELECT id, current_amount FROM goals WHERE current_amount < 0")
        check(failures, "هدف target_amount <= 0", "SELECT id, target_amount FROM goals WHERE target_amount <= 0")
        if has_movements:
            check(failures, "هدف current_amount ≠ مجموع حركاته", """
                SELECT g.id, g.current_amount, COALESCE(SUM(m.amount),0) FROM goals g
                LEFT JOIN goal_movements m ON m.goal_id = g.id
                GROUP BY g.id, g.current_amount
                HAVING g.current_amount <> COALESCE(SUM(m.amount),0)""")

        if has_accounts:
            check(failures, "معاملة مربوطة بحساب مستخدم آخر", """
                SELECT t.id, t.user_id, a.user_id FROM transactions t
                JOIN financial_accounts a ON a.id = t.account_id WHERE a.user_id <> t.user_id""")
            check(failures, "لقطة رصيد بدون حساب (يتيمة)", """
                SELECT s.id, s.account_id FROM account_balance_snapshots s
                LEFT JOIN financial_accounts a ON a.id = s.account_id WHERE a.id IS NULL""")
            check(failures, "اسم حساب مكرر لنفس المستخدم (بدون حساسية للأحرف)", """
                SELECT user_id, lower(name), COUNT(*) FROM financial_accounts
                GROUP BY user_id, lower(name) HAVING COUNT(*) > 1""")
            check(failures, "لقطة رصيد بوقت مستقبلي بعيد", """
                SELECT id, account_id, as_of FROM account_balance_snapshots
                WHERE as_of > now() + interval '1 day'""" if engine.dialect.name == "postgresql" else """
                SELECT id, account_id, as_of FROM account_balance_snapshots WHERE 1 = 0""")

        # ---- WARN ----
        check(warnings, "هدف current_amount أكبر من الهدف (contribute اليدوي بدون سقف)",
              "SELECT id, current_amount, target_amount FROM goals WHERE current_amount > target_amount")
        check(warnings, "هدف ACHIEVED لكن تحت المستهدف", f"""
            SELECT g.id, g.current_amount, g.target_amount FROM goals g
            WHERE {STATUS_TXT} = 'achieved' AND g.current_amount < g.target_amount""")
        check(warnings, "هدف ACTIVE وصل المستهدف", f"""
            SELECT g.id, g.current_amount, g.target_amount FROM goals g
            WHERE {STATUS_TXT} = 'active' AND g.current_amount >= g.target_amount""")
        if not has_movements:
            check(warnings, "مجموع توزيعات الهدف أكبر من current_amount (قد يكون طبيعي بعد reset شهري)", """
                SELECT g.id, g.current_amount, SUM(a.amount) FROM goals g
                JOIN income_allocations a ON a.goal_id = g.id
                GROUP BY g.id, g.current_amount HAVING SUM(a.amount) > g.current_amount""")

    print("\n== الملخص ==")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(f"\nFAIL: {len(failures)}   WARN: {len(warnings)}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"summary": summary, "failures": failures, "warnings": warnings}, handle,
                      ensure_ascii=False, indent=2, default=str)
        print(f"انحفظ الملخص بـ {args.out}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
