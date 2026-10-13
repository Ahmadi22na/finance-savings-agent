"""
تقرير مقاييس النجاح (R08): مسار التفعيل، العودة للاستخدام، النشاط، نتائج التوفير، وثقة المستخدمين برشيد.

    docker compose exec backend python -m app.scripts.usage_report

بيكتب docs/usage_report.md (داخل مجلد backend) وبيطبع المسار. خيارات:
    --days 30                 نافذة مسار التفعيل (المسجّلون آخر N يوم)
    --include-demo            يضم حساب العرض التجريبي (مستبعد افتراضيًا)
    --exclude-phone <رقم>     استبعاد حسابات اختبار إضافية (ممكن تكرره)
    --output <مسار>           مكان الملف

التقرير تجميعي بالكامل: ما بيعرض اسم ولا رقم هاتف ولا أي بيانات فردية.
"""
import argparse
import sys
from pathlib import Path

from app.database.session import SessionLocal
from app.scripts.seed_demo import DEMO_PHONE
from app.services import usage_metrics_service


def main() -> None:
    parser = argparse.ArgumentParser(description="تقرير مقاييس نجاح رشيد")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--include-demo", action="store_true")
    parser.add_argument("--exclude-phone", action="append", default=[])
    parser.add_argument("--output", default="docs/usage_report.md")
    args = parser.parse_args()

    excluded = list(args.exclude_phone)
    if not args.include_demo:
        excluded.append(DEMO_PHONE)

    db = SessionLocal()
    try:
        report = usage_metrics_service.build_report(db, days=args.days, exclude_phones=excluded)
    finally:
        db.close()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(usage_metrics_service.render_markdown(report), encoding="utf-8")
    sys.stdout.write(f"تم توليد التقرير: {output}\n")


if __name__ == "__main__":
    main()
