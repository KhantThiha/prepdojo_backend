# app/schema/lesson.py
from pydantic import BaseModel
from typing import Optional

class LessonBase(BaseModel):
    title: str
    description: Optional[str] = None
    level: Optional[str] = "N5"  # JLPT level, default to N5
    lesson_number: Optional[int] = None

class LessonCreate(LessonBase):
    """Schema for creating a new lesson"""
    pass

class LessonResponse(LessonBase):
    id: int

    class Config:
        orm_mode = True
