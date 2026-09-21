from fastapi import APIRouter, HTTPException

from models.schemas import ChatMessage
from services.rasa_service import chat_with_rasa

router = APIRouter(prefix="/api/llm", tags=["LLM Chat"])


@router.post("/chat")
async def chat(msg: ChatMessage):
    try:
        response = await chat_with_rasa(
            msg.message,
            sender_id=msg.sender_id,
            context=msg.context,
            lang=msg.lang,
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
