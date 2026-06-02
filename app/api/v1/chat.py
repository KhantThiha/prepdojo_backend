from fastapi import APIRouter, Query, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import time
import asyncio
from app.services.chat_history_service import ChatHistoryService
from app.tools.definitions import get_quiz_tool


# Assuming these are correctly set up in your project
from app.dependencies import get_qdrant_store, groq_client, get_cached_store, openai_client, supabase_client, embedding_model

# --- Constants and Configuration ---

# Using a fast, capable model for query transformation task
QUERY_TRANSFORMER_MODEL = "llama-3.1-8b-instant" 

# Few-shot examples to guide final answer generation
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "How do I say 'I like sushi'?"
    },
    {
        "role": "assistant",
        "content": "To say \"I like sushi,\" you use the particle `が` with the object you like. The structure is: [Object] + が + 好きです (suki desu).\n- **Romaji:** Sushi ga suki desu.\n- **Translation:** I like sushi.\n- **Note:** While `好き` (suki) translates to \"like,\" it is grammatically a na-adjective, not a verb. This is a common point of confusion for learners."
    }
]

# --- Pydantic Models ---

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

history_service = ChatHistoryService(supabase_client)
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
    Uses an LLM to analyze user's query and decide on a retrieval strategy.
    """
    router_prompt = f"""
You are a router for a Japanese language learning RAG system. Analyze the user's query and decide on the best query transformation strategy.
The user's query is: "{user_query}"

Respond with a JSON object containing two keys: "strategy" and "queries".
- The "strategy" can be one of: "decomposition", "step_back", "fusion", or "direct".
- The "queries" should be a list of strings containing generated queries to be used for vector search.

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
Query: "What is the romaji for `こんにちは`?"
Response: {{"strategy": "direct", "queries": ["What is the romaji for `こんにちは`?"]}}

Now, analyze the query and provide a JSON response:
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
        if "strategy" not in transformed_data or "queries" not in transformed_data:
            raise ValueError("Invalid JSON response from query transformer.")
        return transformed_data
    except Exception as e:
        print(f"Error in query transformation: {e}")
        # Fallback to a direct query strategy on failure
        return {"strategy": "direct", "queries": [user_query]}

def enrich_context(docs: List[Dict], user_level: str) -> str:
    """
    Converts raw Qdrant dictionaries into structured text blocks.
    """
    context_parts = []
    
    for doc in docs:
        # Access dictionary keys directly
        level = doc.get('jlpt_level', 'Unknown')
        
        # Build the block
        block = (
            f"[ENTRY_TYPE: {doc.get('data_type', 'unknown')}]\n"
            f"[LEVEL: {level}]\n"
            f"[KANJI: {doc.get('kanji', '')}]\n"
            f"[READING: {doc.get('reading', '')}]\n"
            f"[MEANING: {doc.get('meaning', '')}]\n"
        )
        
        # Conditional fields
        mnemonic = doc.get('mnemonic', '')
        if mnemonic:
            block += f"[MNEMONIC: {mnemonic}]\n"
            
        components = doc.get('components', '')
        if components:
            block += f"[PARTS: {components}]\n"
            
        # Use sample_sentence if available (Grammar/Vocab)
        sample = doc.get('sample_sentence', '')
        if sample:
            # Truncate long sentences to save tokens
            block += f"[EXAMPLE: {sample[:300]}]\n"
            
        context_parts.append(block)
        
    return "\n\n".join(context_parts)

def retrieve_and_process_context(
    qdrant_store, 
    queries: List[str], 
    user_level: str, 
    topic: str = None, # <--- ACCEPT STRING HERE
    k: int = 5
) -> str:
    """
    Performs search. Supports single topic filtering.
    """
    all_docs = []

    # --- SINGLE TOPIC FILTER (Robust Standard Approach) ---
    if topic:
        # We construct a standard Exact Match filter
        # {"key": "data_type", "match": {"value": "kanji"}}
        filter_condition = {
            "must": [
                {
                    "key": "data_type", 
                    "match": {"value": topic} 
                }
            ]
        }

        # Use LangChain's similarity_search_with_score
        for query in queries:
            results = qdrant_store.similarity_search_with_score(
                query,
                k=k,
                filter=filter_condition
            )
            
            for doc, score in results:
                all_docs.append(doc.metadata)

    # --- FALLBACK ---
    else:
        retriever = qdrant_store.as_retriever(search_kwargs={"k": k})
        
        for query in queries:
            docs = retriever.invoke(query)
            for d in docs:
                all_docs.append(d.metadata)

    # --- DE-DUPLICATION & CONTEXT ENRICHMENT ---
    # (Keep your existing logic here)
    seen_ids = set()
    unique_docs = []
    for doc in all_docs:
        uid = f"{doc.get('kanji', '')}-{doc.get('reading', '')}"
        if uid not in seen_ids:
            seen_ids.add(uid)
            unique_docs.append(doc)

    return enrich_context(unique_docs, user_level)

def build_system_prompt(user_level: str, context: str) -> str:
    """
    Constructs the System Prompt. 
    Relies heavily on enriched context tags [LEVEL], [MNEMONIC], etc.
    """
    
    # Commented out bad few-shot examples. 
    # You can uncomment if needed later.
    # FEW_SHOT_EXAMPLES = []
    
    base_instruction = (
        "You are a strict but kind Japanese teaching English Tutor."
        f"You are teaching a JLPT {user_level} student.\n\n"
        f"student prefer to be taught in Burmese Language.You must teach in English way but follow by burmese translation."
    )
    
    if not context or len(context) < 50:
        # --- FALLBACK MODE ---
        return f"""
{base_instruction}
You could not find specific study materials for the user's query in the knowledge base.

INSTRUCTIONS:
1. Use your internal general knowledge to answer the query.
2. STRICTLY simplify your vocabulary to match a {user_level} level.
3. Do NOT use advanced grammar (N2/N1) to explain a simple concept.
4. If explaining a Kanji, break it down into simple parts (e.g., "It looks like Tree").
5. Always provide Romaji and Hiragana for clarity.
"""
    else:
        # --- RAG MODE ---
        # The system prompt now trusts the tags in context
        return f"""
{base_instruction}
Below are study materials retrieved from the database.
The system has automatically identified the JLPT level and added helpful tags like [MNEMONIC] or [PARTS] for you.

INSTRUCTIONS:
1. CONTEXT HANDLING:
   - Read the [LEVEL] tag in the context.
   - If [LEVEL] is "{user_level}": Use the provided [MEANING], [EXAMPLE], and [GRAMMER_STRUCTURE] to teach the student directly.
   
2. HIGHER LEVEL HANDLING (Clarification):
   - If [LEVEL] is HIGHER than "{user_level}":
     - Start your response with: "⚠️ Note: This is an advanced concept ({user_level}), but here is a simplified explanation."
     - Actively use [MNEMONIC] or [PARTS] fields provided to explain visually or simply.
     - Do NOT use advanced grammar rules found in the text. Instead, provide a simplified analogy appropriate for {user_level}.
   
3. GENERATION:
   - Prioritize helping the student understand the concept over strict grammatical accuracy if it's too advanced.
   - If [ENTRY_TYPE] is 'kanji', focus on meaning and breakdown, not reading.
   - If the user asks for a quiz, use the 'generate_quiz' tool.
   - Generate EXACTLY 5 questions.


=== CONTEXT BEGIN ===
{context}
=== CONTEXT END ===
"""

def build_generation_messages(user_query: str, system_prompt: str) -> List[Dict[str, str]]:
    """
    Constructs final messages.
    """
    # Note: I removed FEW_SHOT_EXAMPLES list insertion here
    # because the System Prompt now handles the style via context.
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]
    
    return messages

async def event_stream_generator(
    llm_messages: List[Dict[str, str]], 
    model: str, 
    tools: List[Dict] = None,
    chat_id: str = None,
    user_id: str = None,
    history_service: ChatHistoryService = None,
    temperature: float = 0.0
):
    """
    Streams OpenAI responses, accumulates tool chunks, and saves to DB.
    """
    try:
        completion = groq_client.chat.completions.create(
            model=model,
            messages=llm_messages,
            stream=True,
            tools=tools,
            temperature=temperature,
        )

        full_text_content = ""
        
        # FIX: Use a Dictionary to accumulate chunks by Tool ID
        # Structure: { "tool_id": { "name": "...", "arguments_str": "..." } }
        tool_calls_accumulator: Dict[str, Dict[str, str]] = {}

        for chunk in completion:
            choice = chunk.choices[0]
            delta = choice.delta

            payload = {
                "id": chunk.id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}]
            }

            # 1. Handle Text
            if delta.content:
                payload["choices"][0]["delta"]["content"] = delta.content
                full_text_content += delta.content

            # 2. Accumulate Tool Calls (The Critical Fix)
            if delta.tool_calls:
                # We still yield the raw stream to the frontend
                payload["choices"][0]["delta"]["tool_calls"] = [
                    {
                        "index": tc.index,
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name if tc.function else None,
                            "arguments": tc.function.arguments if tc.function else None
                        }
                    }
                    for tc in delta.tool_calls
                ]

                # --- BACKEND SAVING LOGIC ---
                for tc in delta.tool_calls:
                    if tc.id:
                        # Initialize entry if new tool call
                        if tc.id not in tool_calls_accumulator:
                            tool_calls_accumulator[tc.id] = {"name": "", "arguments_str": ""}

                        # Accumulate Name
                        if tc.function and tc.function.name:
                            tool_calls_accumulator[tc.id]["name"] = tc.function.name
                        
                        # Accumulate Arguments (String Concatenation)
                        if tc.function and tc.function.arguments:
                            tool_calls_accumulator[tc.id]["arguments_str"] += tc.function.arguments

            if payload["choices"][0]["delta"]:
                yield f"data: {json.dumps(payload)}\n\n"
                asyncio.sleep(0.05)
                
    finally:
        # 3. Save Assistant Message when stream finishes
        if chat_id and history_service:
            try:
                parts = []
                
                # Reconstruct the parts list from our accumulator
                # We iterate through the accumulated data and build the OpenAI-style structure
                # expected by the frontend's `transformParts` function.
                
                parts_to_save = []
                for tc_id, data in tool_calls_accumulator.items():
                    if data["name"]: # Only save if we have a tool name
                        parts_to_save.append({
                            "type": "function",
                            "function": {
                                "name": data["name"],
                                "arguments": data["arguments_str"]
                            }
                        })
                
                if parts_to_save:
                    parts = [{
                        "type": "tool-call",
                        "data": parts_to_save # Save the list of reconstructed calls
                    }]

                # Save the message
                await history_service.save_message(
                    chat_id=chat_id,
                    user_id=user_id,
                    role="assistant",
                    content=full_text_content,
                    parts=parts if parts else None
                )
            except Exception as e:
                print(f"Error saving assistant message to DB: {e}")

    yield "data: [DONE]\n\n"
# --- Main API Endpoint ---

router = APIRouter()

@router.post("/completions")
async def chat_endpoint(request: ChatRequest,x_chat_id: Optional[str] = Header(None, alias="X-Chat-Id"), # Read Header
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"), x_level: Optional[str] = Header(None, alias="X-Level"),x_topic: Optional[str] = Header(None, alias="X-Topic")):
    """
    Main chat endpoint that orchestrates the RAG pipeline.
    """
    # 1. Validate User Level
    if not x_level:
        raise HTTPException(status_code=400, detail="X-Level header is required for RAG.")
    
    #payload = await request.json()
    #chat_req = ChatRequest(**payload)
    # print(x_topic)
    # return 0
    # 2. Get User Query
    llm_messages =  convert_ui_messages(request.messages)
    if not llm_messages or llm_messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Request must contain a user message.")
    user_query = llm_messages[-1]["content"]
    await history_service.save_message(
        chat_id=x_chat_id,
        user_id=x_user_id,
        role="user",
        content=user_query
    )
    
    # 3. Transform Query
    transformed = transform_query(user_query)
    #print(f"Query Transformation Strategy: {transformed['strategy']}")
    #print(f"Generated Queries: {transformed['queries']}")

    # 4. Retrieve & Enrich Context (USING CACHED STORE)
    qdrant_store = get_cached_store()
    context = retrieve_and_process_context(qdrant_store, transformed["queries"], user_level=x_level,topic=x_topic, k=5)
    
    # 5. Build System Prompt (LEVEL AWARE)
    system_prompt = build_system_prompt(user_level=x_level, context=context)
    #print("System Prompt Strategy:", "RAG Mode" if context else "Fallback Mode")

    # 6. Construct Final Messages
    final_messages = build_generation_messages(user_query, system_prompt)
    available_tools = [get_quiz_tool()]
    # 7. Stream Response
    response = StreamingResponse(
        event_stream_generator(
            final_messages,
            request.model,
            tools=available_tools,
            chat_id=x_chat_id,
            user_id=x_user_id, 
            history_service=history_service),
        media_type="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"

    return response