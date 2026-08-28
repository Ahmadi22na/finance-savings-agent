# رشيد (Rasheed) — Finance Savings Agent

تطبيق موبايل لإدارة المصاريف والتوفير، مع وكيل ذكاء اصطناعي (رشيد) بشخصية مرحة وبنّاءة
يساعد المستخدم — خصوصًا أصحاب الدخل المتغير (طلاب، فريلانسرز) — على تتبع مصاريفه
وتحقيق أهدافه المالية بدون احتكاك.

## حالة المشروع

✅ **Sprint 0 مكتمل** — الأساس التقني للـ Backend:
- Auth كامل (تسجيل / دخول / JWT)
- 6 جداول قاعدة بيانات (users, categories, goals, transactions, agent_interactions, agent_actions)
- Alembic migrations
- Docker جاهز للتشغيل

✅ **Sprint 1 مكتمل** — Manual Quick-log + Goals:
- تصنيفات افتراضية مبذورة (10 تصنيفات بأيقونات وكلمات مفتاحية)
- Quick-log بمسارين: أيقونة مباشرة (category_id) أو نص ذكي (note) يُصنَّف تلقائيًا
- محرك تصنيف ذكي مبدئي (Rule-based) خلف واجهة قابلة للاستبدال بـ Gemini لاحقًا بدون تغيير الـ API
- Goals CRUD كامل (إنشاء / عرض / إضافة تقدم مع تعليم "منجز" تلقائي)

✅ **Sprint 2 مكتمل** — دخول رشيد بالكامل:
- 3 شخصيات (رشيد الحكيم / المنضبط / الطاقة) كجدول قابل للتوسع + System Prompt فعلي لكل شخصية
- Onboarding endpoint: يربط نوع الدخل + الشخصية المختارة + أول هدف بطلب واحد
- محرك الحالة المزاجية (Mood Engine): neutral/energized/concerned بناءً على سلوك الإنفاق الفعلي وتقدم الهدف
- ربط Gemini API فعليًا (`google-genai` SDK) — **رشيد يرد فعليًا بشخصيته المختارة** (مُختبر مع مفتاح حقيقي)
- `/agent/chat`: محادثة حرة مع رشيد
- `/agent/nudge`: منطق استباقي فعلي — رشيد "يبادر" بالحديث لما يستاهل (مش neutral)، مع Cooldown 12 ساعة يمنع الإزعاج

33 اختبار ناجح (pytest)، بما فيها اختبارات الـ Nudge بمزود وهمي (Fake Provider) بدون استدعاء Gemini الحقيقي بالاختبارات.

⏳ **القادم (Sprint 3):** شاشات الموبايل (Flutter) — تحويل كل الـ Backend الجاهز لتجربة مستخدم فعلية

راجع [rasheed-architecture-roadmap.md](rasheed-architecture-roadmap.md) للخطة الكاملة.

## تشغيل المشروع محليًا

### المتطلبات
- Docker + Docker Compose

### خطوات التشغيل

```bash
# 1. انسخ ملف البيئة وعدّل القيم (خصوصًا JWT_SECRET_KEY و ANTHROPIC_API_KEY)
cp .env.example .env

# 2. شغّل كل شيء (Backend + PostgreSQL)
docker-compose up --build

# 3. افتح التوثيق التفاعلي (Swagger UI)
# http://localhost:8000/docs
```

### تطبيق الـ Migrations (أول مرة فقط، أو بعد أي تعديل على الـ Models)

```bash
docker-compose exec backend alembic upgrade head
```

### تشغيل الاختبارات

```bash
docker-compose exec backend pytest -v
```

## هيكل المشروع

```
backend/
├── app/
│   ├── main.py              # نقطة الدخول — تجميع الـ Routers فقط
│   ├── config.py            # الإعدادات المركزية (من .env)
│   ├── core/                 # أمان، JWT، Dependencies مشتركة
│   ├── database/             # اتصال قاعدة البيانات
│   ├── models/                # SQLAlchemy Models (الجداول)
│   ├── schemas/               # Pydantic Schemas (شكل الطلبات/الردود)
│   ├── services/               # منطق العمل (Business Logic)
│   ├── api/routes/              # HTTP Endpoints فقط — بدون منطق عمل
│   └── agent/                    # منطق وكيل الذكاء الاصطناعي (رشيد) — لاحقًا Sprint 2
├── alembic/                       # Migrations
└── tests/                          # الاختبارات

mobile/                              # تطبيق Flutter (لسا لم نبدأ فيه)
```

## مبادئ معمارية مهمة تم اتباعها

1. **Service Layer منفصل عن API Layer**: الـ `api/routes` ما فيها منطق عمل إطلاقًا — بس استقبال/إرجاع. كل المنطق بـ `services/`.
2. **Plugin-based data sources**: حقل `Transaction.source` (manual/ocr/sms/open_banking) يسمح بإضافة مصدر بيانات جديد بدون تعديل البنية.
3. **UUID كمفتاح أساسي** بدل Auto-increment — أمان + قابلية للتوسع لاحقًا.
4. **Numeric بدل Float** لكل المبالغ المالية — لتفادي أخطاء التقريب.
5. **AgentAction بحالة "Pending"**: أي اقتراح من رشيد بالتعديل على بيانات المستخدم يحتاج موافقة صريحة قبل التنفيذ — مبدأ أمان أساسي.
