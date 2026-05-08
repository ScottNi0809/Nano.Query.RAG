from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.services.rag_service import get_rag_service

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    stream: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


@router.post("/chat")
async def chat(request: ChatRequest):
    rag_service = get_rag_service()

    try:
        if request.stream:
            return EventSourceResponse(rag_service.stream_answer(request.question))

        result = await rag_service.answer(request.question)
        return ChatResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc