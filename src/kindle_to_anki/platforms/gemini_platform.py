# platforms/gemini_platform.py
import os
import google.generativeai as genai

from .chat_completion_platform import ChatCompletionPlatform


class GeminiPlatform(ChatCompletionPlatform):
    id = "gemini"
    name = "Gemini"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.client = genai
        self._credentials_valid = None

    def call_api(self, model: str, prompt: str, **kwargs) -> str:
        """
        Call Gemini API.
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized - API key missing")

        model_instance = self.client.GenerativeModel(model)
        response = model_instance.generate_content(prompt, **kwargs)
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
            list(self.client.list_models())
            self._credentials_valid = True
        except Exception:
            self._credentials_valid = False
        return self._credentials_valid
