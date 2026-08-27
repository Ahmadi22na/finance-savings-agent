"""
AI Provider Interface (نفس فلسفة BaseCategorizer بالضبط).

كل منطق رشيد (الـ Chat، الـ Nudges) بيتعامل مع هالواجهة فقط،
وما بيعرف ولا بيهتم أي مزود ذكاء اصطناعي فعليًا خلفها (Gemini اليوم، أي حل تاني لاحقًا).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AgentReply:
    text: str
    raw_error: str | None = None  # موجود بس لما في مشكلة — يساعدنا نصحّح بسرعة بدون ما نكسر تجربة المستخدم


class BaseAIProvider(ABC):
    @abstractmethod
    def generate_reply(self, system_prompt: str, user_message: str) -> AgentReply:
        """
        يرسل System Prompt (شخصية رشيد المختارة) + رسالة المستخدم، ويرجّع رد نصي.
        أي خطأ اتصال أو مصادقة لازم يُلتقط هون ويترجم لرسالة عربية واضحة،
        مش يطلع كـ Exception خام للمستخدم.
        """
        raise NotImplementedError
