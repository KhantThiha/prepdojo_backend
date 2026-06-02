from fastapi import APIRouter, Depends, HTTPException, Query
from app.graph.workflow import create_graph
from app.graph.state import ExamState
from app.dependencies import get_exam_repository
from app.repositories.exam_repository import ExamRepository
from app.models.dtos import FrontendExamResponse
from app.services.mapper import map_to_frontend_question

router = APIRouter()
jlpt_graph = create_graph()

@router.get("/exam")
async def exam():
    # placeholder: real impl will call VectorStore + LLM service
    return {"title": "サンプルレビュー"}


@router.post("/exams/generate-question")
def generate_exam(jlpt_level: str = "N3",repo: ExamRepository = Depends(get_exam_repository)):
    initial_state: ExamState = {
        "jlpt_level": jlpt_level,
        "task_queue": [],
        "current_task": None,
        "generated_question": None,
        "validation_feedback": "",
        "is_valid": False,
        "retry_count": 0,
        "final_exam": []
    }
    try:
        result = jlpt_graph.invoke(initial_state)
        final_questions = result.get("final_exam", [])
        
        if not final_questions:
            raise HTTPException(status_code=500, detail="No questions generated.")

        # Use the injected 'repo' instance
        exam_id = repo.save_generated_exam(jlpt_level, final_questions, user_id=None)
        
        return {
            "status": "success",
            "exam_id": str(exam_id),
            "level": jlpt_level,
            "total_questions": len(final_questions),
            "exam": [q.dict() for q in result["final_exam"]]
        }
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exam/random", response_model=FrontendExamResponse)
def get_random_exam(
    level: str = Query("N3", description="JLPT Level (e.g., N3, N4)"),
    repo: ExamRepository = Depends(get_exam_repository)
):
    """
    Retrieves a random exam for a specific level.
    Suitable for a 'Quick Practice' feature.
    """
    # 1. Fetch a random exam from the repository
    db_exam = repo.get_random_exam(level)
    
    if not db_exam:
        raise HTTPException(status_code=404, detail=f"No exams found for level {level}")
    
    # 2. Map Questions to Frontend Format
    raw_questions = db_exam.get('questions', [])
    frontend_questions = [map_to_frontend_question(q) for q in raw_questions]
    
    # 3. Return Response
    return FrontendExamResponse(
        id=db_exam['id'],
        level=db_exam['level'],
        questions=frontend_questions
    )

@router.get("/exam/{exam_id}", response_model=FrontendExamResponse)
def get_exam(
    exam_id: str, 
    repo: ExamRepository = Depends(get_exam_repository)
):
    """
    Retrieves an exam and transforms it into the format expected by the Frontend.
    """
    # 1. Fetch Raw Data
    db_exam = repo.get_exam_raw(exam_id)
    
    if not db_exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # 2. Map Questions
    raw_questions = db_exam.get('questions', [])
    frontend_questions = [map_to_frontend_question(q) for q in raw_questions]
    
    # 3. Return Response
    return FrontendExamResponse(
        id=db_exam['id'],
        level=db_exam['level'],
        questions=frontend_questions
    )

