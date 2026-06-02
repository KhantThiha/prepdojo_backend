from app.graph.state import ExamState
from app.services.llm import llm
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import json
import os
from datetime import datetime

class ValidationResult(BaseModel):
    is_valid: bool = Field(description="True if the question is perfect")
    feedback: str = Field(description="Feedback on why it is valid or invalid")
    needs_new_point: bool = Field(description="True if the target grammar/vocab is inappropriate and we need to fetch a new one")

class BatchValidationResult(BaseModel):
    results: list[ValidationResult] = Field(description="List of validation results corresponding to each question in the batch")

def validator_node(state: ExamState):
    """
    Evaluates a batch of generated JLPT questions.
    Returns partial successes and determines if more questions are needed.
    """
    if not state.get("generated_questions"):
        return {
            "is_valid": False, 
            "needs_new_point": True, # If no question generated, assume bad data
            "validation_feedback": "Generation failed."
        }
    
    print("--- Validating Question Batch ---")
    
    questions = state["generated_questions"]
    level = state["jlpt_level"]
    
    # 1. Format Questions for the Prompt
    questions_text = ""
    for idx, q in enumerate(questions):
        questions_text += f"\n--- Question {idx+1} ---\n"
        questions_text += f"Text: {q.question_text}\n"
        if getattr(q, 'passage_text', None):
            questions_text += f"Passage Text: {q.passage_text}\n"
        if getattr(q, 'dialogue_script', None):
            questions_text += f"Dialogue Script: {q.dialogue_script}\n"
        questions_text += f"Section: {q.section}, Sub-type: {q.sub_type}\n"
        questions_text += f"Options: {[o.text for o in q.options]}\n"
        questions_text += f"Correct Label: {q.correct_answer_label}\n"
        questions_text += f"Explanation: {q.explanation_en}\n"
    
    # 2. Construct the Prompt
    prompt = ChatPromptTemplate.from_template(
        """
        You are a strict JLPT examiner. Evaluate the following {level} questions.
        
        {questions_text}
        
        Criteria for each question:
        1. Is the section and sub_type appropriate for {level}? (Not too easy, not too hard).
        2. Is the correct answer actually correct?
        3. Are the distractors (wrong answers) plausible but incorrect?
        
        If a question is perfect, set is_valid to true.
        If a question is INVALID, explain why in feedback and set needs_new_point to true if the grammar/vocab itself is inappropriate, false if just the sentence/options need fixing.
        
        Output must be a BatchValidationResult containing the evaluation for EACH question in the exact same order as provided.
        """
    )
    
    # 3. Invoke the LLM
    structured_llm = llm.with_structured_output(BatchValidationResult)
    chain = prompt | structured_llm
    
    result_batch = chain.invoke({"level": level, "questions_text": questions_text})
    
    passed_questions = []
    failed_feedbacks = []
    needs_new_point_any = False
    
    # 4. Process Results
    if result_batch and result_batch.results:
        # Match each result to its corresponding question
        for idx, (q, res) in enumerate(zip(questions, result_batch.results)):
            if res.is_valid:
                passed_questions.append(q)
            else:
                context_feedback = f"Q{idx+1}: {res.feedback}"
                failed_feedbacks.append(context_feedback)
                if res.needs_new_point:
                    needs_new_point_any = True
                
                # Persistently save the validation feedback for rejected questions
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": level,
                    "section": q.section,
                    "sub_type": q.sub_type,
                    "question_text": q.question_text,
                    "passage_text": q.passage_text,
                    "dialogue_script": q.dialogue_script,
                    "options": [o.text for o in q.options],
                    "correct_answer": q.correct_answer_label,
                    "feedback": res.feedback,
                    "needs_new_point": res.needs_new_point
                }
                
                log_dir = "logs"
                os.makedirs(log_dir, exist_ok=True)
                with open(os.path.join(log_dir, "validation_failures.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
    else:
        # Fallback if parsing completely fails
        failed_feedbacks.append("Validation parser returned empty results.")
        needs_new_point_any = True
        
    print(f"--- Validation Complete: {len(passed_questions)}/{len(questions)} Passed ---")
    
    updates = {}
    
    # Save successes
    if passed_questions:
        print("--- Adding passed questions to final exam ---")
        current_list = state.get("final_exam", [])
        updates["final_exam"] = current_list + passed_questions
        
    # Update state tasks and check if we are done with this subtype
    current_task = dict(state.get("current_task", {}))
    remaining = max(0, current_task.get("count", 1) - len(passed_questions))
    current_task["count"] = remaining
    updates["current_task"] = current_task
    
    if remaining == 0:
        updates["is_valid"] = True
        updates["validation_feedback"] = "All questions passed."
        updates["needs_new_point"] = False
    else:
        updates["is_valid"] = False
        updates["validation_feedback"] = "\n".join(failed_feedbacks)
        updates["needs_new_point"] = needs_new_point_any
        
    return updates