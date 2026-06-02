from typing import List, Optional
from uuid import UUID
from supabase import Client
from app.models.schemas import GeneratedQuestion
import random

class ExamRepository:
    def __init__(self, client: Client):
        """
        Initialize the repository with a Supabase client instance.
        """
        self.client = client

    def save_generated_exam(
        self, 
        level: str, 
        questions: List[GeneratedQuestion], 
        user_id: Optional[UUID] = None
    ) -> str:
        
        questions_data = [q.dict() for q in questions]
        
        exam_payload = {
            "level": level,
            "questions": questions_data
        }
        
        if user_id:
            exam_payload["user_id"] = str(user_id)
            
        # Use self.client instead of global 'supabase'
        exam_response = self.client.table("exams").insert(exam_payload).execute()
        exam_id = exam_response.data[0]['id']
        
        bank_rows = []
        for q in questions_data:
            bank_rows.append({
                "exam_id": exam_id,
                "level": level,
                "section": q.get('section'),
                "sub_type": q.get('sub_type'),
                "question_data": q
            })
            
        if bank_rows:
            self.client.table("question_bank").insert(bank_rows).execute()
            
        return exam_id

    def get_exam_by_id(self, exam_id: str):
        response = self.client.table("exams").select("*").eq("id", exam_id).execute()
        if response.data:
            return response.data[0]
        return None

    def get_exam_raw(self, exam_id: str):
        """
        Retrieves the raw exam data from the database.
        """
        response = self.client.table("exams").select("*").eq("id", exam_id).execute()
        if not response.data:
            return None
        return response.data[0]

    def get_random_exam(self, level: str):
        """
        Fetches a batch of recent exams for a given level and returns one at random.
        
        Future enhancement: Add a 'sort' parameter to return the most recent one instead.
        """
        # 1. Fetch the 10 most recent exams for this level
        # We use .order to get the newest ones, making 'most recent' logic easy later
        response = self.client.table("exams") \
            .select("*") \
            .eq("level", level) \
            .order("created_at", desc=True) \
            .limit(10) \
            .execute()
            
        exams = response.data
        
        if not exams:
            return None
            
        # 2. Pick one randomly
        # Later, you can change this logic to return exams[0] for "Most Recent"
        random_exam = random.choice(exams)
        
        return random_exam