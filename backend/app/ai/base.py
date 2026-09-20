from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, Field
from ..domain.enums import AIMode

T = TypeVar("T", bound=BaseModel)

class ProviderMetadata(BaseModel):
    provider_name: str
    model_name: str
    ai_mode: AIMode
    is_fallback: bool = False
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    latency_ms: Optional[float] = None

class ProviderResponse(BaseModel):
    data: Any
    metadata: ProviderMetadata
    raw_output: Optional[str] = None

class ProviderError(Exception):
    """Base exception for AI provider errors."""
    def __init__(self, message: str, provider: str, error_code: str = "PROVIDER_ERROR"):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code

class ProviderRateLimitError(ProviderError):
    """Raised when an external API rate limit (e.g. HTTP 429) is encountered."""
    pass

class ProviderSchemaValidationError(ProviderError):
    """Raised when model output fails to parse into the requested Pydantic schema."""
    pass

class BaseLLMProvider(ABC):
    """Abstract interface for pluggable AI model providers."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None
    ) -> ProviderResponse:
        """Generate structured JSON adhering to the specified Pydantic schema."""
        pass

    @abstractmethod
    def get_metadata(self) -> ProviderMetadata:
        """Return provider and model metadata."""
        pass
