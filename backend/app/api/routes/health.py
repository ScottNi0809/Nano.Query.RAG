from fastapi import APIRouter

from app.services.vectorstore_service import get_vectorstore_service

router = APIRouter()


@router.get("/health")
async def health_check():
    vectorstore_status = get_vectorstore_service().health_check()
    overall_status = "ok" if vectorstore_status.get("status") == "ok" else "degraded"

    return {
        "status": overall_status,
        "service": "wtg-query-rag",
        "chroma": vectorstore_status,
    }