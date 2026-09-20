import os
import time
import json
from typing import Type, TypeVar, Optional, Any
import httpx
from pydantic import BaseModel, ValidationError

from .base import (
    BaseLLMProvider,
    ProviderMetadata,
    ProviderResponse,
    ProviderError,
    ProviderRateLimitError,
    ProviderSchemaValidationError
)
from ..domain.enums import AIMode
from ..config import settings

T = TypeVar("T", bound=BaseModel)

class GroqProvider(BaseLLMProvider):
    """
    Groq provider utilizing low-latency inference via OpenAI-compatible REST endpoints.
    """

    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None, model_name: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
        self.model_name = model_name
        self.provider_name = "Groq"

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            model_name=self.model_name,
            ai_mode=AIMode.LIVE_GROQ,
            is_fallback=False
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError("GROQ_API_KEY is not configured", provider=self.provider_name, error_code="MISSING_API_KEY")

        start_time = time.perf_counter()

        # Generate JSON schema definition to include in prompt
        schema_json = json.dumps(schema.model_json_schema())
        system_content = (
            (system_instruction + "\n\n" if system_instruction else "") +
            f"You are a strict, objective technical assistant. "
            f"You MUST output valid JSON conforming exactly to this JSON schema:\n{schema_json}\n"
            f"Do not include any surrounding markdown code blocks, explanations, or prologue. Respond with raw JSON only."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.GROQ_API_URL, headers=headers, json=payload)
        except Exception as e:
            raise ProviderError(f"Network error communicating with Groq: {str(e)}", provider=self.provider_name)

        duration_ms = (time.perf_counter() - start_time) * 1000

        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"Groq API rate limit reached: {response.text}",
                provider=self.provider_name,
                error_code="RATE_LIMIT_EXCEEDED"
            )
        elif response.status_code != 200:
            raise ProviderError(
                f"Groq API error HTTP {response.status_code}: {response.text}",
                provider=self.provider_name
            )

        resp_data = response.json()
        choices = resp_data.get("choices", [])
        if not choices:
            raise ProviderError("Empty choices received from Groq API", provider=self.provider_name)

        raw_content = choices[0].get("message", {}).get("content", "")

        # Token usage
        usage = resp_data.get("usage", {})
        tokens_prompt = usage.get("prompt_tokens")
        tokens_completion = usage.get("completion_tokens")

        # Validate against schema
        try:
            parsed_data = schema.model_validate_json(raw_content)
        except (ValidationError, ValueError, json.JSONDecodeError) as err:
            raise ProviderSchemaValidationError(
                f"Groq response did not conform to schema {schema.__name__}: {str(err)}",
                provider=self.provider_name
            )

        metadata = ProviderMetadata(
            provider_name=self.provider_name,
            model_name=self.model_name,
            ai_mode=AIMode.LIVE_GROQ,
            is_fallback=False,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            latency_ms=round(duration_ms, 2)
        )

        return ProviderResponse(
            data=parsed_data,
            metadata=metadata,
            raw_output=raw_content
        )
