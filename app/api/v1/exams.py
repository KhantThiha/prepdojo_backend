from fastapi import APIRouter, Depends


router = APIRouter()

@router.get("/exam")
async def exam():
    # placeholder: real impl will call VectorStore + LLM service
    return {"title": "サンプルレビュー"}
