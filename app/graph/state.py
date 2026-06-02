from typing import List, TypedDict, Optional
from app.models.schemas import GeneratedQuestion

class ExamState(TypedDict):
    jlpt_level: str 
    task_queue: List[dict]
    current_task: Optional[dict]
    current_data_payload: Optional[list[dict]] 
    
    # Controls if we keep the data or fetch new data
    generation_mode: str # "standard" or "reroll"
    
    generated_questions: Optional[list[GeneratedQuestion]]
    
    # Validation
    validation_feedback: str
    needs_new_point: bool
    is_valid: bool
    retry_count: int
    
    final_exam: List[GeneratedQuestion]