import os
import time
import json
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel, ValidationError

try:
    from google import genai
    from google.genai import types, errors
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

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

class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini provider implementing structured extraction via the official google-genai SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        if not _GENAI_AVAILABLE:
            raise ProviderError("google-genai library is not installed", provider="Gemini")

        self.api_key = api_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.provider_name = "GoogleGemini"
        self._client = None

    def _get_client(self) -> "genai.Client":
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is not configured", provider="Gemini", error_code="MISSING_API_KEY")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            model_name=self.model_name,
            ai_mode=AIMode.LIVE_GEMINI,
            is_fallback=False
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None
    ) -> ProviderResponse:
        client = self._get_client()
        start_time = time.perf_counter()

        config_kwargs: dict = {
            "response_mime_type": "application/json",
            "response_schema": schema
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                raise ProviderRateLimitError(
                    f"Gemini API rate limit exceeded: {err_str}",
                    provider=self.provider_name,
                    error_code="RATE_LIMIT_EXCEEDED"
                )
            raise ProviderError(f"Gemini API call failed: {err_str}", provider=self.provider_name)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Extract tokens if present in usage_metadata
        tokens_prompt = None
        tokens_completion = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_prompt = getattr(response.usage_metadata, "prompt_token_count", None)
            tokens_completion = getattr(response.usage_metadata, "candidates_token_count", None)

        raw_text = response.text or ""

        # Validate against schema
        try:
            if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, schema):
                data = response.parsed
            else:
                data = schema.model_validate_json(raw_text)
        except (ValidationError, ValueError, json.JSONDecodeError) as err:
            raise ProviderSchemaValidationError(
                f"Gemini response did not conform to schema {schema.__name__}: {str(err)}",
                provider=self.provider_name
            )

        metadata = ProviderMetadata(
            provider_name=self.provider_name,
            model_name=self.model_name,
            ai_mode=AIMode.LIVE_GEMINI,
            is_fallback=False,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            latency_ms=round(duration_ms, 2)
        )

        return ProviderResponse(
            data=data,
            metadata=metadata,
            raw_output=raw_text
        )
