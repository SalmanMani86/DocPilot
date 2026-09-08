from fastapi import APIRouter, Request, status
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check(request: Request) -> HealthResponse:
    """Report whether the API process is accepting requests."""
    settings = request.app.state.settings
    return HealthResponse(
        status="ok", service=settings.app_name, environment=settings.app_env
    )
