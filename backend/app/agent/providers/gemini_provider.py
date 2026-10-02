"""Module documentation."""
import time

from google import genai
from google.genai.errors import ClientError, ServerError

from app.agent.providers.base import BaseAIProvider, AgentReply, ConversationTurn
from app.config import settings

MAX_RETRIES_ON_SERVER_ERROR = 3
RETRY_DELAY_SECONDS = 2


class GeminiProvider(BaseAIProvider):
    def __init__(self):
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_reply(
        self,
        system_prompt: str,
        user_message: str,
        history: list[ConversationTurn] | None = None,
    ) -> AgentReply:



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
        """ generate documentation."""
        last_server_error: ServerError | None = None

        for attempt in range(1, MAX_RETRIES_ON_SERVER_ERROR + 1):
            try:
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

                last_server_error = e
                if attempt < MAX_RETRIES_ON_SERVER_ERROR:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue

        return AgentReply(
            text="خدمة الذكاء الاصطناعي مشغولة هلأ، جرب كمان شوي 🙏",
            raw_error=str(last_server_error),
        )
