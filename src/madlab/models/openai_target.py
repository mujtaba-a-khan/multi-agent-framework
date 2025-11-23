"""
OpenAI API target wrapper.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .targets import BaseTarget


class OpenAIAuthError(RuntimeError):
    """Raised when no API key is available for the OpenAI target."""


class OpenAIResponseError(RuntimeError):
    """Raised when the OpenAI API response is malformed."""


def _default_base_url() -> str:
    """
    Resolve the OpenAI-compatible base URL from environment variables.

    Returns:
        Base URL string; defaults to the official endpoint if none is set.
    """
    return os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"


@dataclass
class OpenAITarget(BaseTarget):
    """
    Minimal wrapper around OpenAI's Chat Completions endpoint.
    """

    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 512
    top_p: float = 1.0
    timeout: float = 30.0
    base_url: Optional[str] = None
    base_url_env: Optional[str] = "OPENAI_BASE_URL"
    api_key_env: Optional[str] = "OPENAI_API_KEY"
    api_key: Optional[str] = None
    system_prompt: str = "You are a helpful and safe assistant."
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Validate credentials and build the API endpoint URL.
        """
        env_var = self.api_key_env or "OPENAI_API_KEY"
        api_key = self.api_key or (env_var and os.getenv(env_var))
        if not api_key:
            raise OpenAIAuthError(
                f"Missing API key: set '{env_var}' or pass `api_key` to OpenAITarget."
            )
        self._api_key = api_key
        base_url_env = self.base_url_env or "OPENAI_BASE_URL"
        base_url = self.base_url or os.getenv(base_url_env) or _default_base_url()
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"

    def _messages(self, prompt: str) -> List[Dict[str, str]]:
        """
        Build chat messages for the API call.

        Args:
            prompt: User prompt string.

        Returns:
            List of role/content dicts.
        """
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the chat completions endpoint with retries.

        Args:
            payload: JSON payload for the API.

        Returns:
            Parsed JSON response.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        response = httpx.post(self._endpoint, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def generate(self, prompt: str) -> str:
        """
        Generate a model response for a prompt.

        Args:
            prompt: User prompt string.

        Returns:
            Model-generated text.
        """
        payload = {
            "model": self.model,
            "messages": self._messages(prompt),
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        data = self._call_api(payload)
        try:
            choice = data["choices"][0]
            message = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAIResponseError(f"Unexpected OpenAI response: {data}") from exc
        return message.strip()
