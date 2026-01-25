# platforms/gemini_platform.py
import os
from google import genai

from .chat_completion_platform import ChatCompletionPlatform


class GeminiPlatform(ChatCompletionPlatform):
    id = "gemini"
    name = "Gemini"

    def __init__(self, api_key: str = None):
        self._api_key = api_key
        self._client = None
        self._credentials_valid = None

    @property
    def api_key(self):
        if self._api_key is None:
            self._api_key = os.environ.get("GEMINI_API_KEY")
        return self._api_key

    @property
    def client(self):
        if self._client is None and self.api_key:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def call_api(self, model: str, prompt: str, **kwargs) -> str:
        """
        Call Gemini API.
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized - API key missing")

        response = self.client.models.generate_content(model=model, contents=prompt, **kwargs)
        return response.text

    def validate_credentials(self):
        """
        Verify that API key is set correctly by making a simple test call.
        """
        if self._credentials_valid is not None:
            return self._credentials_valid
        if not self.client:
            self._credentials_valid = False
            return False
        try:
            self.client.models.list()
            self._credentials_valid = True
        except Exception:
            self._credentials_valid = False
        return self._credentials_valid
