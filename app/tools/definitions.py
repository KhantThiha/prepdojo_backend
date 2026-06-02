from typing import List, Dict, Any

# --- Modular Tool Definitions ---

def get_quiz_tool() -> Dict[str, Any]:
    """
    Returns a definition for a Quiz with multiple questions (default 5).
    """
    return {
        "type": "function",
        "function": {
            "name": "generate_quiz",
            "description": "Generates a multiple-choice quiz with several questions. Generate 5 questions by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "description": "A list of quiz questions.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "correct_index": {"type": "integer"},
                                "explanation": {"type": "string"}
                            },
                            "required": ["question", "options", "correct_index", "explanation"]
                        }
                    }
                },
                "required": ["questions"]
            }
        }
    }

# You can add more tools here later, e.g.:
# def get_flashcard_tool() -> Dict[str, Any]: ...