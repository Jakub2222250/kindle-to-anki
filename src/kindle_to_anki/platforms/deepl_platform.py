# platforms/deepl_platform.py
import os
import requests


class DeepLPlatform:
    id = "deepl"
    name = "DeepL"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("DEEPL_API_KEY")
        self.base_url = None
        if self.api_key:
            # Use free API if key ends with :fx
            if self.api_key.endswith(":fx"):
                self.base_url = "https://api-free.deepl.com/v2"
            else:
                self.base_url = "https://api.deepl.com/v2"
        self._credentials_valid = None

    def translate(self, texts: list[str], target_lang: str, source_lang: str = None) -> list[str]:
        """
        Translate a list of texts using DeepL API.
        Returns list of translated texts in same order.
        """
        if not self.api_key:
            raise RuntimeError("DeepL API key missing")
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "text": texts,
            "target_lang": target_lang,
        }
        if source_lang:
            data["source_lang"] = source_lang

        response = requests.post(f"{self.base_url}/translate", headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return [t["text"] for t in result["translations"]]

    def validate_credentials(self):
        """Verify API key by checking usage."""
        if self._credentials_valid is not None:
            return self._credentials_valid
        if not self.api_key:
            self._credentials_valid = False
            return False
        try:
            headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}
            response = requests.get(f"{self.base_url}/usage", headers=headers)
            self._credentials_valid = response.status_code == 200
        except Exception:
            self._credentials_valid = False
        return self._credentials_valid
