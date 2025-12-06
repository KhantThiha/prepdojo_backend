from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from uuid import uuid4
import json

# Assuming these are correctly set up in your project
from app.dependencies import get_qdrant_store, groq_client

# --- Constants and Configuration ---

# Using a fast, capable model for the query transformation task
QUERY_TRANSFORMER_MODEL = "llama-3.1-8b-instant" 

# Few-shot examples to guide the final answer generation
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "How do I say 'I like sushi'?"
    },
    {
        "role": "assistant",
        "content": "To say \"I like sushi,\" you use the particle `が` with the object you like. The structure is: [Object] + が + 好きです (suki desu).\n- **Romaji:** Sushi ga suki desu.\n- **Translation:** I like sushi.\n- **Note:** While `好き` (suki) translates to \"like,\" it's grammatically a na-adjective, not a verb. This is a common point of confusion for learners."
    },
    {
        "role": "user",
        "content": "What is the te-form of `行きます` (ikimasu)?"
    },
    {
        "role": "assistant",
        "content": "The te-form of `行きます` (ikimasu - to go) is `行って` (itte).\n- This is an irregular conjugation. The `き` (ki) sound changes to `っ` (small tsu) before adding `て` (te).\n- **Example sentence:** `学校に行って、勉強します。` (Gakkou ni itte, benkyou shimasu.)\n- **Translation:** I will go to school and study."
    }
]


# --- Pydantic Models (Unchanged) ---

class UIPart(BaseModel):
    type: str
    text: str | None = None
    url: str | None = None

class UIMessage(BaseModel):
    id: str
    role: str
    parts: List[UIPart]

class RawMessage(BaseModel):
    role: str
    content: str | None = None
    id: str | None = None
    parts: List[UIPart] | None = None

class ChatRequest(BaseModel):
    messages: List[RawMessage]
    model: str


# --- Modular Helper Functions ---

def convert_ui_messages(messages: List[RawMessage]) -> List[Dict[str, str]]:
    """Converts UI message format to a simple LLM message format."""
    llm_messages = []
    for msg in messages:
        if msg.parts:
            merged = "\n".join(
                part.text for part in msg.parts if part.type == "text" and part.text
            )
            if merged:
                llm_messages.append({"role": msg.role, "content": merged})
        elif msg.content:
            llm_messages.append({"role": msg.role, "content": msg.content})
    return llm_messages

def transform_query(user_query: str) -> Dict[str, Any]:
    """
    Uses an LLM to analyze the user's query and decide on a retrieval strategy.
    It generates one or more queries for vector search.
    """
    router_prompt = f"""
You are a router for a Japanese language learning RAG system. Analyze the user's query and decide on the best query transformation strategy.
The user's query is: "{user_query}"

Respond with a JSON object containing two keys: "strategy" and "queries".
- The "strategy" can be one of: "decomposition", "step_back", "fusion", or "direct".
- The "queries" should be a list of strings containing the generated queries to be used for vector search.

Example 1 (Decomposition):
Query: "Explain keigo"
Response: {{"strategy": "decomposition", "queries": ["What is keigo?", "Explain sonkeigo", "Explain kenjougo"]}}

Example 2 (Step-Back):
Query: "Why is `ga` used here?"
Response: {{"strategy": "step_back", "queries": ["Why is `ga` used here?", "What are the principles for using the particle `ga`?"]}}

Example 3 (Fusion):
Query: "how to count"
Response: {{"strategy": "fusion", "queries": ["Japanese counting system", "How to use josuushi counters", "Japanese numbers 1-10"]}}

Example 4 (Direct):
Query: "What is the romaji for こんにちは?"
Response: {{"strategy": "direct", "queries": ["What is the romaji for こんにちは?"]}}

Now, analyze the query and provide the JSON response:
"""

    try:
        response = groq_client.chat.completions.create(
            model=QUERY_TRANSFORMER_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                {"role": "user", "content": router_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        transformed_data = json.loads(response.choices[0].message.content)
        # Ensure the expected keys are present
        if "strategy" not in transformed_data or "queries" not in transformed_data:
            raise ValueError("Invalid JSON response from query transformer.")
        return transformed_data
    except Exception as e:
        print(f"Error in query transformation: {e}")
        # Fallback to a direct query strategy on failure
        return {"strategy": "direct", "queries": [user_query]}

def retrieve_and_process_context(qdrant_store, queries: List[str], k: int = 5) -> str:
    """
    Performs vector search for each query and merges the results.
    For now, it uses a simple merge. A more advanced version would use re-ranking.
    """
    all_docs = []
    retriever = qdrant_store.as_retriever(search_kwargs={"k": k})
    
    # Perform search for each query
    for query in queries:
        docs = retriever.invoke(query)
        all_docs.extend(docs)

    # Simple de-duplication and merging
    # A more robust approach would involve re-ranking (e.g., Reciprocal Rank Fusion)
    seen_content = set()
    unique_docs = []
    for doc in all_docs:
        if doc.page_content not in seen_content:
            seen_content.add(doc.page_content)
            unique_docs.append(doc)
            
    # Join the content of the top N unique documents
    context = "\n\n".join(doc.page_content for doc in unique_docs[:k])
    return context

def build_generation_messages(user_query: str, context: str) -> List[Dict[str, str]]:
    """
    Constructs the final list of messages for the LLM generation step,
    including the system prompt, context, and few-shot examples.
    """
    system_msg_content = (
        "You are a helpful Japanese tutor. Answer the user's question based ONLY on the provided lesson materials. "
        "If the answer cannot be found in the materials, say: 'I could not find the answer in the provided materials.'\n\n"
        f"=== CONTEXT BEGIN ===\n{context}\n=== CONTEXT END ==="
    )

    # Start with few-shot examples
    messages = list(FEW_SHOT_EXAMPLES)
    
    # Add the system message with the retrieved context
    messages.insert(0, {"role": "system", "content": system_msg_content})
    
    # Add the current user query
    messages.append({"role": "user", "content": user_query})
    
    return messages

def event_stream_generator(llm_messages: List[Dict[str, str]], model: str):
    """Generator function to stream the LLM response."""
    completion = groq_client.chat.completions.create(
        model=model,
        messages=llm_messages,
        stream=True,
        # You can add other parameters like temperature, max_tokens, etc.
    )
    for chunk in completion:
        choice = chunk.choices[0]
        delta = choice.delta
        if delta and delta.content:
            payload = {
                "id": chunk.id or str(uuid4()),
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"content": delta.content}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(payload)}\n\n"
    yield "data: [DONE]\n\n"


# --- Main API Endpoint ---

router = APIRouter()

@router.post("/completions")
async def chat_endpoint(request: Request, x_level: str = Header(None, alias="X-Level")):
    """
    Main chat endpoint that orchestrates the RAG pipeline.
    """
    if not x_level:
        raise HTTPException(status_code=400, detail="X-Level header is required for RAG.")

    payload = await request.json()
    chat_req = ChatRequest(**payload)

    # 1. Get the last user message
    llm_messages = convert_ui_messages(chat_req.messages)
    if not llm_messages or llm_messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Request must contain a user message.")
    user_query = llm_messages[-1]["content"]

    # 2. Transform the user's query into one or more search queries
    transformed = transform_query(user_query)
    print(f"Query Transformation Strategy: {transformed['strategy']}")
    print(f"Generated Queries: {transformed['queries']}")

    # 3. Retrieve relevant context from Qdrant
    qdrant_store = get_qdrant_store(x_level)
    context = retrieve_and_process_context(qdrant_store, transformed["queries"], k=5)
    print("Retrieved Context:", context[:200] + "...") # Log first 200 chars

    # 4. Build the final prompt for the generation LLM
    final_messages = build_generation_messages(user_query, context)
    print("Final LLM Messages:", final_messages)

    # 5. Stream the response from the generation LLM
    return StreamingResponse(
        event_stream_generator(final_messages, chat_req.model),
        media_type="text/event-stream"
    )