from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import exams, chat
from app.core.config import settings
from app.core.security import get_current_user

app = FastAPI(title="Prepdojo API", version="0.1.0")

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Custom-Header"],
)

@app.middleware("http")
async def custom_header_check(request: Request, call_next):
    if request.headers.get("X-Custom-Header") != settings.X_CUSTOM_HEADER:
        return Response("Invalid or missing custom header", status_code=400)
    return await call_next(request)

app.include_router(exams.router, prefix="/api/v1", tags=["exams"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"], dependencies=[Depends(get_current_user)])

@app.get("/")
async def health():
    return {"status": "ok"}
