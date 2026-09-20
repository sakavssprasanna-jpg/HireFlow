import json
import os
from typing import List, Union
from pydantic import field_validator
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
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://hire-flow-nine-drab.vercel.app",
    ]

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        origins: List[str] = []
        if isinstance(v, str):
            v_clean = v.strip()
            if v_clean.startswith("[") and v_clean.endswith("]"):
                try:
                    parsed = json.loads(v_clean)
                    if isinstance(parsed, list):
                        origins = [str(i).strip().rstrip("/") for i in parsed if str(i).strip()]
                except Exception:
                    pass
            if not origins:
                origins = [i.strip().rstrip("/") for i in v_clean.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            origins = [str(i).strip().rstrip("/") for i in v if str(i).strip()]

        required = [
            "http://localhost:5173",
            "https://hire-flow-nine-drab.vercel.app",
        ]
        for origin in required:
            if origin not in origins:
                origins.append(origin)
        return origins

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()

