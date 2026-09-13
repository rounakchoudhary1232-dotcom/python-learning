from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.core.config import get_settings
settings = get_settings()
app = FastAPI(title="JARVIS API", version="0.1.0", docs_url="/docs" if settings.environment != "production" else None)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False, allow_methods=["GET"], allow_headers=["Content-Type", "X-Request-ID"])
app.include_router(health_router, prefix="/api/v1")
