from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .db.base import Base, engine, migrate_schema
from .db import models  # noqa: F401 Ensure all ORM models are registered in Base.metadata
from .api.v1.health import router as health_router
from .api.v1.roles import router as roles_router
from .api.v1.candidates import router as candidates_router
from .api.v1.interviews import router as interviews_router

# Initialize database tables and migrate schemas
Base.metadata.create_all(bind=engine)
migrate_schema(engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="HireFlow — AI Candidate Screening & Interview Intelligence Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global standardized error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "detail": "An unexpected system error occurred. Details recorded in audit logs." if not settings.DEBUG else str(exc),
            "path": request.url.path
        }
    )

# Mount API routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(roles_router, prefix=settings.API_V1_PREFIX)
app.include_router(candidates_router, prefix=settings.API_V1_PREFIX)
app.include_router(interviews_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    return {
        "project": "HireFlow",
        "description": "AI Candidate Screening & Interview Intelligence Agent",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health"
    }
