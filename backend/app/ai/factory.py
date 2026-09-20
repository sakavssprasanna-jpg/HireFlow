import os
import logging
from typing import Optional
from .base import BaseLLMProvider
from .offline_fallback import OfflineFallbackProvider
from .gemini_provider import GeminiProvider
from .groq_provider import GroqProvider
from ..domain.enums import AIMode
from ..config import settings

logger = logging.getLogger("hireflow.ai.factory")

def get_llm_provider(mode: Optional[AIMode] = None) -> BaseLLMProvider:
    """
    Factory function to retrieve the configured AI provider.
    Automatically falls back to OfflineFallbackProvider if live provider keys are absent
    or live dependencies fail, guaranteeing zero downtime and zero test brittleness.
    """
    target_mode = mode or settings.DEFAULT_AI_MODE

    if target_mode == AIMode.LIVE_GEMINI:
        gemini_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                return GeminiProvider(api_key=gemini_key)
            except Exception as e:
                logger.warning(f"Failed to initialize GeminiProvider ({e}); falling back to OfflineFallbackProvider.")
        else:
            logger.info("GEMINI_API_KEY is not set; using OfflineFallbackProvider.")

    elif target_mode == AIMode.LIVE_GROQ:
        groq_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            try:
                return GroqProvider(api_key=groq_key)
            except Exception as e:
                logger.warning(f"Failed to initialize GroqProvider ({e}); falling back to OfflineFallbackProvider.")
        else:
            logger.info("GROQ_API_KEY is not set; using OfflineFallbackProvider.")

    return OfflineFallbackProvider()
