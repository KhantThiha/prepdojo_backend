from typing import Optional
from pydantic import BaseModel, Field

class QuestionOption(BaseModel):
    label: str = Field(description="The option label (e.g., A, B, C, D)")
    text: str = Field(description="The text for the option")

class GeneratedQuestion(BaseModel):
    question_text: str = Field(description="The Japanese question or sentence with a blank")
    #question_type: str = Field(description="e.g., Grammar, Vocabulary")
    section: str = Field(description="Section: Grammer,Vocabulary,Reading,Listening")
    sub_type: str = Field(description="Sub Type of Jlpt question: eg. Kanji reading, Paraphrases,Sentential grammar 1, etc")
    passage_text: Optional[str] = None
    dialogue_script: Optional[str] = None
    options: list[QuestionOption] = Field(description="List of 4 options")
    correct_answer_label: str = Field(description="The label of the correct answer (e.g., C)")
    explanation_jp: str = Field(description="Explanation in Japanese")
    explanation_en: str = Field(description="Explanation in English")

class GeneratedQuestionBatch(BaseModel):
    questions: list[GeneratedQuestion] = Field(description="List of generated questions matching the requested count")