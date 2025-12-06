from fastapi import FastAPI
from app.api.v1 import lessons, exams, chat
from app.core.config import settings
app = FastAPI(title="Prepdojo API", version="0.1.0")

app.include_router(lessons.router, prefix="/api/v1/lessons", tags=["lessons"])
app.include_router(exams.router, prefix="/api/v1/exams", tags=["exams"])
app.include_router(chat.router,prefix="/api/v1/chat",tags=["chat"])

@app.get("/")
async def health():
    return {"status": "ok"}