from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    query:str = Field(..., min_length=1, description="The user's question")

class Source(BaseModel):
    lesson_id: str
    text_snippet: str
    relevance_score: Optional[float] = None # Reranker can provide this

class MessageVersion(BaseModel):
    id: str
    content: str
class ChatResponse(BaseModel):
    key: str
    from_: str = Field(..., alias="from")   # Map "from" → from_
    versions: List[MessageVersion]