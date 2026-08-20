# Finance & Savings Agent

تطبيق موبايل لإدارة الدخل والمصروفات والأهداف المالية بتجربة Gamified،
مع AI Agent يفهم اللغة الطبيعية بصلاحيات تنفيذ محدودة صارمة.

> ⚠️ **حالة المشروع: Discovery — لا كود منطقي فعلي بعد.**
> هاي بس بنية تحتية (Repo structure, Docker, CI) بانتظار:
> 1. مقابلات مستخدمين فعلية
> 2. Concept Testing للتمثيل البصري (القناني هي مجرد Placeholder)
>
> راجع `AI_CODING_CONTEXT.md` (أو الملف المرجعي الكامل) قبل أي عمل برمجي.

## البنية

```
finance-savings-agent/
├── backend/        # Flask + Pydantic
├── mobile/         # Flutter
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml
```

## التشغيل المحلي (Backend فقط حاليًا)

```bash
cp .env.example .env
# املأ القيم بـ .env (خصوصًا POSTGRES_PASSWORD, FLASK_SECRET_KEY)

docker-compose up --build
```

## قواعد أساسية غير قابلة للتفاوض

راجع قسم 9 بالتوثيق الكامل — أهمها:

- **لا AI يتخذ قرار مالي نيابة عن المستخدم — بدون استثناء.**
- **لا تعديل مالي بدون تأكيد صريح من المستخدم.**
- أي PR يمس `backend/app/agent/` يحتاج مراجعة إلزامية من شخص ثانٍ
  (مفعّلة جزئيًا عبر `.github/CODEOWNERS` — يحتاج تفعيل Branch
  Protection يدويًا بإعدادات الـ repo).

## الخطوة الجاية

**ما بتبلش ببرمجة منطق فعلي** لحد ما يصير:
- [ ] مقابلات مستخدمين (على الأقل عدد كافي يعطي إشارة)
- [ ] Concept Testing لأكتر من فكرة بصرية للتمثيل (مو بس القناني)
- [ ] حسم القرارات المفتوحة بقسم 8 من التوثيق
