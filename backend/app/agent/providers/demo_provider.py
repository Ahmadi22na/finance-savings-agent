"""
مزوّد Demo (R12): بيشتغل بدون إنترنت وبدون مفتاح Gemini، لعرض المشروع حتى لو الخدمة وقعت.

كيف تفعّله: AI_PROVIDER=demo بملف .env ثم إعادة إنشاء الـ container.
مهم: الردود جاهزة ومبنية على كلمات مفتاحية (مش ذكاء اصطناعي حقيقي) — لا تعرضها كأنها Gemini حي.
بيدعم نفس السيناريوهات الي بتعتمد عليها الواجهة: محادثة (مع اقتراح تسجيل دخل أو هدف عبر نفس
بروتوكول الكتل)، رسالة مبادرة (Nudge)، تصنيف المصاريف (JSON)، وقراءة الفواتير (OCR).
"""
import json
import re

from app.agent.providers.base import AgentReply, BaseAIProvider, ConversationTurn

_OPTION_PATTERN = re.compile(r"^- ([0-9a-fA-F\-]{36}): (.+)$", re.MULTILINE)
_NOTE_PATTERN = re.compile(r':\s*"([^"]*)"')
_NUMBER_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")
_LETTER_FOLDING = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"})


def _normalize(text: str) -> str:
    return text.translate(_ARABIC_DIGITS).translate(_LETTER_FOLDING).replace(",", ".").lower()


def _words(*words: str) -> tuple[str, ...]:
    return tuple(_normalize(w) for w in words)


# (جزء من اسم التصنيف، كلمات مفتاحية) — بالترتيب
CATEGORY_KEYWORDS = [
    ("ترفيه", _words("سهرة", "سينما", "لعبة", "ملاهي", "بلايستيشن")),
    ("مطاعم", _words("غدا", "عشا", "فطور", "قهوة", "كافيه", "مطعم", "شاورما", "فلافل", "برجر", "بيتزا", "عصير", "ساندويش")),
    ("مواصلات", _words("تكسي", "باص", "اوبر", "كريم", "بنزين", "مواصلات")),
    ("بقالة", _words("خضار", "فواكه", "سوبرماركت", "بقالة", "اغراض", "خبز", "لحمة", "دجاج")),
    ("تسوق", _words("لبس", "ملابس", "حذاء", "جزمة", "اكسسوارات")),
    ("صحة", _words("صيدلية", "دكتور", "دواء", "مستشفى", "عيادة")),
    ("فواتير", _words("فاتورة", "انترنت", "كهرباء", "اشتراك", "سبوتيفاي", "نتفلكس", "تعبئة", "رصيد")),
    ("حلاقة", _words("حلاقة", "حلاق", "صالون")),
]

INCOME_WORDS = _words("اجاني", "اجا لي", "جاني", "استلمت", "قبضت", "حصلت على", "نزل لي", "نزلولي", "وصلني", "وصلتني")
GOAL_WORDS = _words("اجمع", "ادخر", "اوفر", "وفر", "هدف", "اشتري", "اجيب")
PROGRESS_WORDS = _words("كم باقي", "باقيلي", "وين وصلت", "كيف هدفي", "تقدمي")
SPENDING_WORDS = _words("مصاريف", "صرفت", "مصروفي", "انفاق")
TIPS_WORDS = _words("نصيحة", "كيف اوفر", "توفير", "وفرلي")
GREETING_WORDS = _words("مرحبا", "اهلا", "هلا", "السلام", "صباح", "مساء")


def _first_number(text: str) -> float | None:
    match = _NUMBER_PATTERN.search(text)
    return float(match.group(1)) if match else None


def _block(name: str, payload: dict) -> str:
    return f"<<<{name}>>>{json.dumps(payload, ensure_ascii=False)}<<<END>>>"


class DemoProvider(BaseAIProvider):
    def generate_reply(
        self,
        system_prompt: str,
        user_message: str,
        history: list[ConversationTurn] | None = None,
    ) -> AgentReply:
        if "رد بصيغة JSON فقط" in system_prompt:
            return AgentReply(text=self._category_json(user_message))
        if user_message.startswith("بادر إنت بالحديث"):
            return AgentReply(text=self._nudge(system_prompt))
        return AgentReply(text=self._chat(user_message))

    def analyze_image(self, system_prompt: str, user_message: str, image_bytes: bytes, mime_type: str) -> AgentReply:
        options = _OPTION_PATTERN.findall(user_message)
        chosen = next((cid for cid, name in options if "بقاله" in _normalize(name)), options[0][0] if options else None)
        return AgentReply(text=json.dumps(
            {"amount": 12.5, "category_id": chosen, "note": "سوبرماركت (فاتورة تجريبية)"}, ensure_ascii=False,
        ))

    # ------------------------------------------------------------------ داخلي

    @staticmethod
    def _nudge(system_prompt: str) -> str:
        if "concerned" in system_prompt:
            return "لاحظت إنك صرفت أكتر من المعتاد هالأسبوع، ولا يهمك، خطوة صغيرة اليوم بترجّعك على المسار 🌱"
        return "ما شاء الله، هدفك صار قريب! كمّل بنفس الحماس 🔥"

    @staticmethod
    def _category_json(message: str) -> str:
        options = _OPTION_PATTERN.findall(message)
        note_match = _NOTE_PATTERN.search(message)
        note = _normalize(note_match.group(1)) if note_match else ""
        for key, words in CATEGORY_KEYWORDS:
            if any(word in note for word in words):
                for category_id, name in options:
                    if key in _normalize(name):
                        return json.dumps(
                            {"category_id": category_id, "confidence": 0.85, "reasoning": f"الوصف أقرب لتصنيف {name}"},
                            ensure_ascii=False,
                        )
        return json.dumps({"category_id": None, "confidence": 0.0, "reasoning": "ما لقيت تصنيف مناسب"}, ensure_ascii=False)

    @staticmethod
    def _chat(message: str) -> str:
        text = _normalize(message)
        amount = _first_number(text)

        if amount is not None and any(word in text for word in INCOME_WORDS):
            marker = _block("INCOME_LOG_PROPOSAL", {"amount": amount, "note": "دخل ذكره المستخدم بالمحادثة"})
            return f"تمام، جهزتلك تسجيل دخل بـ {amount:g} دينار. افتح أيقونة الاقتراحات وأكّده لما تكون جاهز 👌 {marker}"

        if amount is not None and any(word in text for word in GOAL_WORDS):
            marker = _block("GOAL_PROPOSAL", {
                "title": "هدف جديد", "target_amount": amount, "breakdown": [], "is_recurring": False,
            })
            return f"جهزتلك اقتراح هدف بـ {amount:g} دينار. راجعه من أيقونة الاقتراحات وأكّده لو مناسب 🎯 {marker}"

        if any(word in text for word in PROGRESS_WORDS):
            return "إنت ماشي منيح! افتح مسار الهدف وشوف وين وصلت، وكل ما قسّمت دخل جديد على أهدافك بتقرّب أكتر 💪"
        if any(word in text for word in SPENDING_WORDS):
            return (
                "مصاريفك الصغيرة اليومية (قهوة وطلبات) هي اللي بتتجمع أكتر شي. "
                "راقبها من الشاشة الرئيسية وبتلاقي وين تقدر توفّر 👀"
            )
        if any(word in text for word in TIPS_WORDS):
            return (
                "جرّب هالقاعدة: أول ما ينزل دخل، وزّع جزء منه على هدفك قبل ما تصرف. "
                "التوفير الصغير المنتظم أقوى من الكبير المتقطّع ✨"
            )
        if any(word in text for word in GREETING_WORDS):
            return "أهلين فيك! أنا رشيد، جاهز أساعدك بأهدافك ومصاريفك. شو بتحب نبدأ فيه؟"
        return (
            "أنا هلأ بوضع العرض التجريبي 🙂 جرّب تسألني عن هدفك أو مصاريفك، "
            "أو احكيلي إنه اجاك دخل (مثلاً: اجاني 25 دينار اليوم)."
        )
