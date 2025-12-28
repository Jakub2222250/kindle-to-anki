# platforms/openai_platform.py
import os
from openai import OpenAI

from .chat_completion_platform import ChatCompletionPlatform

class OpenAIPlatform(ChatCompletionPlatform):
    id = "openai"
    name = "OpenAI"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        self._credentials_valid = None

    def call_api(self, model: str, prompt: str, **kwargs) -> str:
        """
        Call OpenAI ChatCompletion API.
        messages: list of dicts [{"role": "user", "content": "..."}]
        kwargs: optional OpenAI parameters (temperature, max_tokens, etc.)
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized - API key missing")
        messages = [{"role": "user", "content": prompt}]
        
        response = self.client.chat.completions.create(
            model=model, 
            messages=messages, 
            **kwargs
        )
        return response.choices[0].message.content

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
