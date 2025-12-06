from fastapi import APIRouter, Depends
from app.schemas.lesson import LessonResponse
from app.services.vectorstore import VectorStore

router = APIRouter()

@router.post("/review")
async def review(req: LessonResponse):
    # placeholder: real impl will call VectorStore + LLM service
    return {"lesson_id": req.lesson_id, "title": "サンプルレビュー"}
