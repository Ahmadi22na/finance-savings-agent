# agent/

⚠️ أهم مجلد أمنيًا بكل المشروع (قسم 4 و 10).

هون بينحط:
- Extraction logic (استخراج بيانات من نص حر)
- Pydantic Validator (تحقق رقمي قبل عرض أي اقتراح)
- Action Proposal builder (JSON schema بحالة pending)

قاعدة صارمة: الـ LLM ما بيكتب مباشرة عالـ database أبدًا.
كل تعديل يمر بـ: Observe → Analyze → Explain → Suggest →
Show Expected Impact → Ask for Confirmation → Execute

أي Pull Request يمس هاد المجلد يحتاج مراجعة إلزامية من شخص ثانٍ
قبل الدمج — بدون استثناء (قسم 9، مبدأ 9).
