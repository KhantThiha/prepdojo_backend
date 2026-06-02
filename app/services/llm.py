from langchain_groq import ChatGroq
from app.core.config import settings


llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.7,
    max_tokens=None,
    reasoning_format="parsed",
    timeout=None,
    max_retries=2,
    api_key=settings.groq_api_key
)