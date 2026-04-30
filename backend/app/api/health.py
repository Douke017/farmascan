from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check del servicio")
async def health_check():
    return {
        "status": "healthy",
        "service": "FarmaScan API",
        "timestamp": datetime.utcnow().isoformat(),
    }
