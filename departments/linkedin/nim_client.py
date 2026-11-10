"""NVIDIA NIM API Client for the LinkedIn Department.
Wraps the OpenAI-compatible chat completions endpoint with automatic model fallback,
reasoning token extraction, and retry resilience.
"""

from dataclasses import dataclass, field
import json
import logging
import time
from typing import Any, Optional
import requests

from .config import config, LinkedInConfig

logger = logging.getLogger("departments.linkedin.nim")


@dataclass
class NIMResponse:
    content: str
    reasoning: Optional[str] = None
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw: dict = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class NIMClient:
    """Synchronous client for NVIDIA NIM API."""

    def __init__(self, cfg: Optional[LinkedInConfig] = None):
        self.cfg = cfg or config

    def _get_headers(self) -> dict[str, str]:
        if not self.cfg.api_key:
            raise ValueError(
                "NVIDIA_NIM_API_KEY is not set. Please add it to .env or environment."
            )
        return {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "JARVIS-OS-LinkedIn-Department/1.0",
        }

    def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        system_prompt: Optional[str] = None,
    ) -> NIMResponse:
        """Generate a chat completion using NVIDIA NIM with automatic model fallback."""
        target_model = model or self.cfg.model_primary
        fallback_models = [
            m for m in [self.cfg.model_deep_reasoning, self.cfg.model_flagship] if m != target_model
        ]
        candidate_models = [target_model] + fallback_models

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        last_error = None

        for current_model in candidate_models:
            for attempt in range(1, self.cfg.max_retries + 1):
                try:
                    payload = {
                        "model": current_model,
                        "messages": full_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": top_p,
                    }
                    url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"

                    resp = requests.post(
                        url,
                        headers=self._get_headers(),
                        json=payload,
                        timeout=self.cfg.timeout_seconds,
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        choice = data.get("choices", [{}])[0]
                        message_obj = choice.get("message", {})
                        content = message_obj.get("content") or ""
                        reasoning = message_obj.get("reasoning_content")

                        # If content is empty because reasoning tokens consumed all max_tokens,
                        # fall back to reasoning content if available
                        if not content and reasoning:
                            content = reasoning

                        usage = data.get("usage", {})
                        return NIMResponse(
                            content=content.strip(),
                            reasoning=reasoning,
                            model=current_model,
                            prompt_tokens=usage.get("prompt_tokens", 0),
                            completion_tokens=usage.get("completion_tokens", 0),
                            total_tokens=usage.get("total_tokens", 0),
                            raw=data,
                            success=True,
                        )

                    # Non-200 status code
                    err_text = resp.text
                    last_error = f"HTTP {resp.status_code} ({current_model}): {err_text[:300]}"
                    logger.warning("NIM call attempt %d failed: %s", attempt, last_error)

                    if resp.status_code in (400, 404, 410):
                        # Client / Model error, skip retrying this specific model
                        break

                    time.sleep(1.0 * attempt)

                except requests.RequestException as e:
                    last_error = f"RequestException ({current_model}): {str(e)}"
                    logger.warning("NIM call attempt %d error: %s", attempt, last_error)
                    time.sleep(1.5 * attempt)

            logger.info("Falling back from %s to next candidate...", current_model)

        return NIMResponse(
            content="",
            model=target_model,
            success=False,
            error=last_error or "All NIM candidate models failed.",
        )


# Global default client
nim_client = NIMClient()
