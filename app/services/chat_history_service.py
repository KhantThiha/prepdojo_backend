import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from supabase import Client, create_client
# from app.core.config import settings # Uncomment if you use this

# 1. Class Definition starts
class ChatHistoryService:

    # 2. Indent __init__ (4 spaces)
    def __init__(self, supabase_client: Client):
        self.client = supabase_client

    # 3. Indent save_message (4 spaces) - IT MUST BE ALIGNED WITH __INIT__
    async def save_message(
        self,
        chat_id: str,
        user_id: str,
        role: str,
        content: str,
        parts: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        
        message_id = str(uuid.uuid4())
        
        data_payload = {
            "id": message_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }

        if parts:
            data_payload["parts"] = parts
        if metadata:
            data_payload["metadata"] = metadata

        # Insert into Supabase
        # Ensure your table name is correct here: "messages"
        response = self.client.table("messages").insert(data_payload).execute()
        
        return response.data[0]

    # 4. Indent other methods similarly
    async def get_history(self, chat_id: str) -> List[Dict]:
        response = self.client.table("messages") \
            .select("*") \
            .eq("chat_id", chat_id) \
            .order("created_at", desc=True) \
            .execute()
        
        return response.data