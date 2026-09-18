"""
تطبيق Gemini لواجهة BaseAIProvider.

ملاحظة مهمة (أغسطس 2026): جوجل بتنتقل حاليًا من مفاتيح "AIza" لمفاتيح "AQ." الجديدة،
وبعض الحسابات بتواجه خطأ 401 (ACCESS_TOKEN_TYPE_UNSUPPORTED) حتى مع الطريقة الرسمية —
هذا مش خطأ بالكود عندنا، مشكلة معروفة وموثقة من جوجل نفسها. لهيك منلتقط هالخطأ
تحديدًا ومنرجع رسالة عربية واضحة تشرح الوضع، بدل ما المستخدم يشوف Exception خام.
"""
from google import genai
from google.genai.errors import ClientError, ServerError

from app.agent.providers.base import BaseAIProvider, AgentReply, ConversationTurn
from app.config import settings


class GeminiProvider(BaseAIProvider):
    def __init__(self):
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_reply(
        self,
        system_prompt: str,
        user_message: str,
        history: list[ConversationTurn] | None = None,
    ) -> AgentReply:
        try:
            # Gemini بيفهم المحادثة كقائمة "أدوار" (Turns) — "user" للمستخدم
            # و"model" لرشيد. بدون هالبنية، ما عنده أي طريقة يعرف فيها شو
            # انحكى قبل هالرسالة، حتى لو أرسلناها بنفس الـ HTTP request.
            contents = []
            for turn in (history or []):
                role = "user" if turn.is_from_user else "model"
                contents.append({"role": role, "parts": [{"text": turn.text}]})
            contents.append({"role": "user", "parts": [{"text": user_message}]})

            response = self._client.models.generate_content(
                model=settings.AGENT_MODEL,
                contents=contents,
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
