from typing import List
from app.models.dtos import FrontendQuestion
import uuid
def map_to_frontend_question(db_question: dict) -> FrontendQuestion:
    """
    Converts a database question object into the format expected by the Frontend.
    """
    
    # 1. Extract Options
    raw_options = db_question.get('options', [])
    
    # Sort options by label (A, B, C, D) to ensure correctIndex is accurate
    # Just in case the LLM generated them out of order
    sorted_options = sorted(raw_options, key=lambda x: x.get('label', ''))
    
    # Extract just the text strings
    option_texts = [opt.get('text', '') for opt in sorted_options]
    
    # 2. Find Correct Index
    # Backend stores "A", "B", "C" -> we need 0, 1, 2
    correct_label = db_question.get('correct_answer_label', 'A')
    label_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    correct_index = label_map.get(correct_label, 0)
    
    # 3. Normalize Section Name (Backend: "Vocabulary" -> Frontend: "vocabulary")
    section = db_question.get('section', 'general').lower()
    
    # 4. Map Fields
    return FrontendQuestion(

        id=db_question.get('id', str(uuid.uuid4())), # Or use UUID
        section=section,
        text=db_question.get('question_text', ''),
        options=option_texts,
        correctIndex=correct_index,
        explanation=db_question.get('explanation_en', ''), # Or explanation_jp
        passage=db_question.get('passage_text'),
        passageTitle=None, # DB doesn't have this, can be added later
        audioUrl=db_question.get('audio_url')
    )