# platforms/chat_completion_platform.py
from abc import ABC, abstractmethod

class ChatCompletionPlatform(ABC):
    """
    Abstract base class for chat-completion style APIs.
    """

    @abstractmethod
    def call_api(self, model: str, messages: list[dict], **kwargs) -> str:
        """
        Sends messages to the platform and returns a string response.
        messages: list of dicts, e.g. [{"role": "user", "content": "..."}]
        kwargs: optional platform-specific parameters
        """
        pass

    @abstractmethod
    def validate_credentials(self):
        """
        Optional: verify that API keys or auth are set correctly.
        """
        pass
