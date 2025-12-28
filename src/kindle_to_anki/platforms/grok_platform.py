# platforms/grok_platform.py
import os
from openai import OpenAI

from .chat_completion_platform import ChatCompletionPlatform

class GrokPlatform(ChatCompletionPlatform):
    id = "grok"
    name = "Grok"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("XAI_API_KEY")
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.x.ai/v1")
        self._credentials_valid = None

    def call_api(self, model: str, prompt: str, **kwargs) -> str:
        """
        Call Grok ChatCompletion API.
        """
        if not self.client:
            raise RuntimeError("Grok client not initialized - API key missing")
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
