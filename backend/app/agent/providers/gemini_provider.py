"""
تطبيق Gemini لواجهة BaseAIProvider.

ملاحظة مهمة (أغسطس 2026): جوجل بتنتقل حاليًا من مفاتيح "AIza" لمفاتيح "AQ." الجديدة،
وبعض الحسابات بتواجه خطأ 401 (ACCESS_TOKEN_TYPE_UNSUPPORTED) حتى مع الطريقة الرسمية —
هذا مش خطأ بالكود عندنا، مشكلة معروفة وموثقة من جوجل نفسها. لهيك منلتقط هالخطأ
تحديدًا ومنرجع رسالة عربية واضحة تشرح الوضع، بدل ما المستخدم يشوف Exception خام.

ملاحظة ثانية (سبتمبر 2026): أحيانًا الموديل بيرجّع 503 UNAVAILABLE مؤقت بسبب
ضغط استخدام عالمي على جوجل نفسها (مش مشكلة بحسابنا أو كودنا) — جوجل حرفيًا
بتقول "جرب كمان شوي" برسالة الخطأ. لهيك منعيد المحاولة تلقائيًا بضع مرات
بفاصل بسيط قبل ما نستسلم ونرجّع رسالة اعتذار للمستخدم.
"""
import logging
import time

from google import genai
from google.genai.errors import ClientError, ServerError

from app.agent.providers.base import BaseAIProvider, AgentReply, ConversationTurn
from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES_ON_SERVER_ERROR = 3
RETRY_DELAY_SECONDS = 2  # بين المحاولات: 2 ثانية ثم 4 (تأخير متزايد بسيط)


class GeminiProvider(BaseAIProvider):
    def __init__(self):
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_reply(
        self,
        system_prompt: str,
        user_message: str,
        history: list[ConversationTurn] | None = None,
    ) -> AgentReply:
        # Gemini بيفهم المحادثة كقائمة "أدوار" (Turns) — "user" للمستخدم
        # و"model" لرشيد. بدون هالبنية، ما عنده أي طريقة يعرف فيها شو
        # انحكى قبل هالرسالة، حتى لو أرسلناها بنفس الـ HTTP request.
        contents = []
        for turn in (history or []):
            role = "user" if turn.is_from_user else "model"
            contents.append({"role": role, "parts": [{"text": turn.text}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        return self._generate(system_prompt, contents)

    def analyze_image(
        self,
        system_prompt: str,
        user_message: str,
        image_bytes: bytes,
        mime_type: str,
    ) -> AgentReply:
        contents = [{
            "role": "user",
            "parts": [
                {"text": user_message},
                {"inline_data": {"mime_type": mime_type, "data": image_bytes}},
            ],
        }]
        return self._generate(system_prompt, contents)

    def _generate(self, system_prompt: str, contents: list[dict]) -> AgentReply:
        """
        منطق مشترك بين generate_reply وanalyze_image:
        - أخطاء العميل (401/403/429...): ما بنعيد المحاولة، بنرجّع رسالة عربية مناسبة لنوع الخطأ
          وبنسجّل الخطأ الحقيقي بالـ logs (الرسالة للمستخدم عامة، والتفاصيل للمطوّر).
        - 503 وأمثالها (ازدحام مؤقت عند جوجل): إعادة محاولة بتأخير متزايد، وبعدها لو في
          AGENT_FALLBACK_MODEL بنجرّبه، وإلا رسالة اعتذار.
        - 404 (الموديل مش متوفر/انسحب): ننتقل للموديل البديل إن وجد.
        """
        models = [settings.AGENT_MODEL]
        fallback = settings.AGENT_FALLBACK_MODEL
        if fallback and fallback != settings.AGENT_MODEL:
            models.append(fallback)

        last_error: Exception | None = None

        for model_index, model in enumerate(models):
            has_next_model = model_index < len(models) - 1

            for attempt in range(1, MAX_RETRIES_ON_SERVER_ERROR + 1):
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=contents,
                        config={"system_instruction": system_prompt},
                    )
                    return AgentReply(text=response.text)

                except ClientError as e:
                    code = getattr(e, "code", None)
                    logger.warning("Gemini client error (model=%s, code=%s): %s", model, code, e)
                    if code == 404 and has_next_model:
                        last_error = e
                        break  # الموديل مش متوفر — جرّب البديل
                    return self._client_error_reply(code, str(e))

                except ServerError as e:
                    last_error = e
                    logger.warning(
                        "Gemini server error (model=%s, attempt=%s/%s): %s",
                        model, attempt, MAX_RETRIES_ON_SERVER_ERROR, e,
                    )
                    if attempt < MAX_RETRIES_ON_SERVER_ERROR:
                        time.sleep(RETRY_DELAY_SECONDS * attempt)

            if has_next_model:
                logger.warning("Gemini: switching from %s to fallback model %s", model, models[model_index + 1])

        return AgentReply(
            text="خدمة الذكاء الاصطناعي مشغولة هلأ، جرب كمان شوي 🙏",
            raw_error=str(last_error),
        )

    @staticmethod
    def _client_error_reply(code: int | None, text: str) -> AgentReply:
        if "ACCESS_TOKEN_TYPE_UNSUPPORTED" in text:
            message = (
                "رشيد مش قادر يوصل لعقله الذكي هلأ 🤖 — في مشكلة معروفة من جوجل بخصوص "
                "نوع مفتاح الـ API الجديد، جرب تحدّث مكتبة google-genai أو تواصل مع فريق التطوير."
            )
        elif code in (401, 403) or "API_KEY_INVALID" in text or "API key not valid" in text or (
            code is None and "401" in text
        ):
            message = "رشيد مش قادر يوصل لعقله الذكي هلأ 🤖 — مفتاح الـ API مش مقبول، تواصل مع فريق التطوير."
        elif code == 429 or "RESOURCE_EXHAUSTED" in text:
            message = "رشيد وصل لحد الاستخدام المسموح هلأ، جرب بعد شوي 🙏"
        else:
            message = "صار في مشكلة مؤقتة برشيد، جرب كمان شوي 🙏"
        return AgentReply(text=message, raw_error=text)
