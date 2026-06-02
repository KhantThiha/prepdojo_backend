from app.core.exam_config import get_exam_tasks
from app.core.config import settings # Import settings
from app.graph.state import ExamState

def manager_node(state: ExamState):
    level = state['jlpt_level']
    
    # Use the MOCK_MODE setting from config
    is_mock = settings.MOCK_MODE
    
    print(f"--- Manager: Planning {level} Exam (Mock Mode: {is_mock}) ---")
    
    # Pass the mock flag to the function
    task_queue = get_exam_tasks(level, mock=is_mock)
    
    print(f"--- Manager: Generated {len(task_queue)} tasks ---")
    
    return {"task_queue": task_queue}