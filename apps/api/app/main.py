import logging
import uuid
from collections.abc import Awaitable, Callable
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from .api import health_router, mvp_router, trading_router, upgrades_router
from .config import get_settings
from .migrations import upgrade_database
from .logging import configure_logging

configure_logging()
settings = get_settings()
app = FastAPI(title="ULTRON API", version="0.1.0", docs_url="/docs" if settings.environment != "production" else None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "X-Request-ID"])
logger = logging.getLogger(__name__)

@app.on_event("startup")
def initialize_database() -> None:
    upgrade_database()


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    logger.info("request_complete method=%s path=%s status=%s request_id=%s", request.method, request.url.path, response.status_code, request_id)
    return response


app.include_router(health_router, prefix="/api/v1")
app.include_router(mvp_router, prefix="/api/v1")
app.include_router(upgrades_router, prefix="/api/v1")
app.include_router(trading_router, prefix="/api/v1")
