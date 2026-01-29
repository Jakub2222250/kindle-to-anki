# platforms/gemini_platform.py
import os
import time
from kindle_to_anki.logging import get_logger
from google import genai

from .chat_completion_platform import ChatCompletionPlatform

# Track last 429 time per model for rate limiting
_rate_limit_tracker: dict[str, float] = {}
RATE_LIMIT_COOLDOWN_SECONDS = 60


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

    def _wait_for_rate_limit(self, model: str):
        """Wait if we hit a 429 recently for this model."""
        last_429_time = _rate_limit_tracker.get(model)
        if last_429_time:
            elapsed = time.time() - last_429_time
            remaining = RATE_LIMIT_COOLDOWN_SECONDS - elapsed
            if remaining > 0:
                get_logger().info(f"Rate limit cooldown: waiting {remaining:.1f}s for {model}")
                time.sleep(remaining)
            del _rate_limit_tracker[model]

    def call_api(self, model: str, prompt: str, **kwargs) -> str:
        """
        Call Gemini API.
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized - API key missing")

        self._wait_for_rate_limit(model)

        try:
            response = self.client.models.generate_content(model=model, contents=prompt, **kwargs)
            return response.text
        except Exception as e:
            # Check for rate limit error (429) by examining the error message/code
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                _rate_limit_tracker[model] = time.time()
                get_logger().warning(f"Rate limit hit (429) for {model}, will cooldown on next call")
            raise

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
