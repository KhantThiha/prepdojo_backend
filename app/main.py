from fastapi import FastAPI,Depends
from guard import SecurityConfig
from app.api.v1 import exams, chat
from app.core.config import settings
from dotenv import load_dotenv
from guard.middleware import SecurityMiddleware

from fastapi import Request, Response
from typing import Optional
from app.core.security import get_current_user

load_dotenv()
async def custom_check(request: Request) -> Optional[Response]:
    if request.headers.get("X-Custom-Header") != settings.X_CUSTOM_HEADER:
        return Response("Invalid or missing custom header", status_code=400)
    return None

app = FastAPI(title="Prepdojo API", version="0.1.0")
config = SecurityConfig(
    security_headers={
        "enabled": True,
        "hsts": {
            "max_age": 31536000,  # 1 year
            "include_subdomains": True,
            "preload": False
        },
        "csp": {
            "default-src": ["'self'"],
            "script-src": ["'self'", "https://trusted.cdn.com"],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https:"],
            "connect-src": ["'self'", "https://api.example.com"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"]
        },
        "frame_options": "DENY",
        "content_type_options": "nosniff",
        "xss_protection": "1; mode=block",
        "referrer_policy": "strict-origin-when-cross-origin",
        "permissions_policy": "geolocation=(), microphone=(), camera=()",
        "custom": {
            "X-Custom-Header": settings.X_CUSTOM_HEADER
        }
    },
    custom_request_check=custom_check,
    blocked_user_agents=["curl", "wget"],
    auto_ban_threshold=5,
    auto_ban_duration=86400,
    custom_log_file="security.log",
    rate_limit=30,
    #enforce_https=True,
    #enable_cors=True,
    cors_allow_origins=["*"],
    cors_allow_methods=["GET", "POST"],
    cors_allow_headers=["*"],
    #cors_allow_credentials=True,
    #cors_expose_headers=["X-Custom-Header"],
    cors_max_age=600,
    #block_cloud_providers={"AWS", "GCP", "Azure"},
)

app.include_router(exams.router, prefix="/api/v1", tags=["exams"])
app.include_router(chat.router,prefix="/api/v1/chat",tags=["chat"],dependencies=[Depends(get_current_user)])
#app.add_middleware(SecurityMiddleware, config=config)

@app.get("/")
async def health():
    return {"status": "ok"}