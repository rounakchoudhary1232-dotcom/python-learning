from datetime import UTC, datetime
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, summary="API liveness check")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="ultron-api", timestamp=datetime.now(UTC))
