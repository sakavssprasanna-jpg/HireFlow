import os
from typing import List
from pydantic_settings import BaseSettings
from .domain.enums import AIMode

class Settings(BaseSettings):
    PROJECT_NAME: str = "HireFlow"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./hireflow.db"
    
    # AI Provider Settings
    DEFAULT_AI_MODE: AIMode = AIMode.OFFLINE_FALLBACK
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
