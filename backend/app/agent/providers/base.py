"""Module documentation."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """Conversationturn documentation."""
    is_from_user: bool
    text: str


@dataclass
class AgentReply:
    text: str
    raw_error: str | None = None


class BaseAIProvider(ABC):
    @abstractmethod
    def generate_reply(
        self,
        system_prompt: str,
        user_message: str,
        history: list[ConversationTurn] | None = None,
    ) -> AgentReply:
        """Generate reply documentation."""
        raise NotImplementedError

    @abstractmethod
    def analyze_image(
        self,
        system_prompt: str,
        user_message: str,
        image_bytes: bytes,
        mime_type: str,
    ) -> AgentReply:
        """Analyze image documentation."""
        raise NotImplementedError
