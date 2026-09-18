"""
AI Provider Interface (نفس فلسفة BaseCategorizer بالضبط).

كل منطق رشيد (الـ Chat، الـ Nudges) بيتعامل مع هالواجهة فقط،
وما بيعرف ولا بيهتم أي مزود ذكاء اصطناعي فعليًا خلفها (Gemini اليوم، أي حل تاني لاحقًا).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """دور وحدة بتاريخ المحادثة — مين قالها (المستخدم أو رشيد) ونصها."""
    is_from_user: bool
    text: str


@dataclass
class AgentReply:
    text: str
    raw_error: str | None = None  # موجود بس لما في مشكلة — يساعدنا نصحّح بسرعة بدون ما نكسر تجربة المستخدم


class BaseAIProvider(ABC):
    @abstractmethod
    def generate_reply(
        self,
        system_prompt: str,
        user_message: str,
        history: list[ConversationTurn] | None = None,
    ) -> AgentReply:
        """
        يرسل System Prompt (شخصية رشيد المختارة) + رسالة المستخدم، ويرجّع رد نصي.

        history (اختياري): آخر كم رسالة من نفس المحادثة، بالترتيب الزمني الصحيح
        (الأقدم أول). بدونها، كل رسالة تُعامل كأنها "أول رسالة" من منظور النموذج —
        وهذا بالضبط كان سبب مشكلة "الرسائل مش مترابطة" يلي لاحظها أحمد.

        أي خطأ اتصال أو مصادقة لازم يُلتقط هون ويترجم لرسالة عربية واضحة،
        مش يطلع كـ Exception خام للمستخدم.
        """
        raise NotImplementedError
