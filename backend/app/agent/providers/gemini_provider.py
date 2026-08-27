"""
تطبيق Gemini لواجهة BaseAIProvider.

ملاحظة مهمة (أغسطس 2026): جوجل بتنتقل حاليًا من مفاتيح "AIza" لمفاتيح "AQ." الجديدة،
وبعض الحسابات بتواجه خطأ 401 (ACCESS_TOKEN_TYPE_UNSUPPORTED) حتى مع الطريقة الرسمية —
هذا مش خطأ بالكود عندنا، مشكلة معروفة وموثقة من جوجل نفسها. لهيك منلتقط هالخطأ
تحديدًا ومنرجع رسالة عربية واضحة تشرح الوضع، بدل ما المستخدم يشوف Exception خام.
"""
from google import genai
from google.genai.errors import ClientError, ServerError

from app.agent.providers.base import BaseAIProvider, AgentReply
from app.config import settings


class GeminiProvider(BaseAIProvider):
    def __init__(self):
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_reply(self, system_prompt: str, user_message: str) -> AgentReply:
        try:
            response = self._client.models.generate_content(
                model=settings.AGENT_MODEL,
                contents=user_message,
                config={"system_instruction": system_prompt},
            )
            return AgentReply(text=response.text)

        except ClientError as e:
            if "ACCESS_TOKEN_TYPE_UNSUPPORTED" in str(e) or "401" in str(e):
                return AgentReply(
                    text="رشيد مش قادر يوصل لعقله الذكي هلأ 🤖 — في مشكلة معروفة من جوجل بخصوص "
                         "نوع مفتاح الـ API الجديد، جرب تحدّث مكتبة google-genai أو تواصل مع فريق التطوير.",
                    raw_error=str(e),
                )
            return AgentReply(
                text="صار في مشكلة مؤقتة برشيد، جرب كمان شوي 🙏",
                raw_error=str(e),
            )

        except ServerError as e:
            return AgentReply(
                text="خدمة الذكاء الاصطناعي مشغولة هلأ، جرب كمان شوي 🙏",
                raw_error=str(e),
            )
