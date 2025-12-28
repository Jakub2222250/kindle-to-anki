# platforms/grok_platform.py
import os
from openai import OpenAI

from .chat_completion_platform import ChatCompletionPlatform

class GrokPlatform(ChatCompletionPlatform):
    id = "grok"
    name = "Grok"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("XAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY is not set")
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.x.ai/v1")
        self._credentials_valid = None

    def call_api(self, model: str, prompt: str, **kwargs) -> str:
        """
        Call Grok ChatCompletion API.
        """
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
        try:
            self.client.models.list()
            self._credentials_valid = True
        except Exception:
            self._credentials_valid = False
        return self._credentials_valid
