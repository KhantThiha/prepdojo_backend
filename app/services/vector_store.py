import random
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
#from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

#embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=settings.OPENAI_API_KEY)
qdrant = QdrantClient(url=settings.qdrant_host,
            api_key=settings.qdrant_api_key,)
COLLECTION_NAME = "jlpt_knowledge_base"

def retrieve_jlpt_content(level: str, content_type: str, count: int = 1) -> list[dict]:
    """
    Retrieves a random batch of items using scroll (no vector search),
    then picks up to `count` items randomly. Ensures true variety across the database.
    """
    
    # 1. Define the Filter (Metadata only)
    query_filter = Filter(
        must=[
            FieldCondition(key="data_type", match=MatchValue(value=content_type)),
            FieldCondition(key="jlpt_level", match=MatchValue(value=level))
        ]
    )
    
    # 2. SCROLL instead of SEARCH
    # This fetches points purely by ID/Order, ignoring vector similarity
    # We fetch a batch of 100 to ensure we have enough variety to pick from
    limit = max(20, count + 10)
    points, _ = qdrant.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=query_filter,
        limit=limit, 
        with_payload=True
    )
    
    if not points:
        raise ValueError(f"No {content_type} found for level {level} in database.")
    
    # 3. Randomly pick up to logic from the batch
    amount_to_pick = min(count, len(points))
    selected_points = random.sample(points, amount_to_pick)
    
    # Log which specific item we picked for debugging
    for idx, p in enumerate(selected_points):
        kanji_or_word = p.payload.get('kanji') or p.payload.get('word', 'Unknown')
        print(f"--- Randomly Retrieved ({content_type}) [{idx+1}/{amount_to_pick}]: {kanji_or_word} ---")
    
    return [p.payload for p in selected_points]