"""
Health check endpoints.
"""

from fastapi import APIRouter
from src.schemas.responses import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Returns status và available modules.
    """
    return HealthResponse(
        status="healthy", modules=["privacy_guard", "semantic_parser"]
    )
