from pydantic import BaseModel
from typing import List, Optional

class FrontendQuestion(BaseModel):
    id: str
    section: str # e.g., "vocabulary" (lowercase)
    text: str
    options: List[str] # Array of strings, not objects
    correctIndex: int # 0, 1, 2, 3 (not "A", "B", "C", "D")
    explanation: str
    passage: Optional[str] = None
    passageTitle: Optional[str] = None
    audioUrl: Optional[str] = None

class FrontendExamResponse(BaseModel):
    id: str
    level: str
    questions: List[FrontendQuestion]