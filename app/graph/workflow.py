from langgraph.graph import StateGraph, END
from app.graph.state import ExamState
from app.nodes.manager import manager_node
from app.nodes.poper import pop_task_node
from app.nodes.generator import generator_node
from app.nodes.validator import validator_node

# --- ROUTER FUNCTIONS ---

def route_after_validation(state: ExamState) -> str:
    """
    Determines the next step based on validation.
    """
    # Fail-safe
    if state["retry_count"] >= 3:
        print("--- Max attempts reached. Moving on. ---")
        return "pop_task"

    if state["is_valid"]:
        return "pop_task"
    
    # Natural Decision Logic
    if state.get("needs_new_point"):
        print("--- Router: The point is bad (too easy/hard). Swapping data. ---")
        return "set_reroll_mode"
    else:
        print("--- Router: The sentence is wrong. Retrying. ---")
        return "generator"

def set_reroll_mode(state: ExamState):
    """Helper to tell the generator to fetch new data."""
    return {"generation_mode": "reroll"}

def create_graph():
    workflow = StateGraph(ExamState)
    
    # Nodes
    workflow.add_node("manager", manager_node)
    workflow.add_node("pop_task", pop_task_node)
    workflow.add_node("generator", generator_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("set_reroll_mode", set_reroll_mode)
    
    workflow.set_entry_point("manager")
    
    # Edges
    workflow.add_edge("manager", "pop_task")
    
    workflow.add_conditional_edges(
        "pop_task",
        lambda s: "generator" if s.get("current_task") else END,
        {"generator": "generator", END: END}
    )
    
    workflow.add_edge("generator", "validator")
    
    # Clean Routing
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "pop_task": "pop_task",
            "generator": "generator", 
            "set_reroll_mode": "set_reroll_mode" 
        }
    )
    
    workflow.add_edge("set_reroll_mode", "generator")
    
    return workflow.compile()