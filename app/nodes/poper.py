from app.graph.state import ExamState

def pop_task_node(state: ExamState):
    """
    Takes the next task from the queue and sets it as the current task.
    """
    if not state["task_queue"]:
        return {"current_task": None}
    
    # Remove the first item from the list
    next_task = state["task_queue"][0]
    remaining_queue = state["task_queue"][1:]
    
    #print(f"--- Popping Task: {next_task['type']} ({next_task['section_name']}) ---")
    
    return {
        "current_task": next_task,
        "task_queue": remaining_queue,
        # Reset validation state for the new task
        "generated_questions": None,
        "is_valid": False,
        "retry_count": 0,
        "validation_feedback": ""
    }