import os
from fastapi import Depends
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from groq import Groq
from openai import OpenAI
from supabase import Client, create_client

from app.repositories.exam_repository import ExamRepository

from .core.config import settings

# --- Clients & Models ---
groq_client = Groq(api_key=settings.groq_api_key)

# Embedding Model (Used inside get_qdrant_store)
embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key
)

openai_client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_api_base
)

# Qdrant Vector Store
def get_qdrant_store()->QdrantVectorStore:
    client = QdrantClient(
            url=settings.qdrant_host,
            api_key=settings.qdrant_api_key,
            prefer_grpc=False,
            timeout=60
            )
    collection_name = f"jlpt_knowledge_base"
    
    vector_store=QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embedding_model, # Pass the embedder here
    )
    return vector_store

_qdrant_store_cache = None

def get_cached_store():
    global _qdrant_store_cache
    if _qdrant_store_cache is None:
        _qdrant_store_cache = get_qdrant_store()
    return _qdrant_store_cache

supabase_client = create_client(settings.supabase_url, settings.supabase_key)

def get_supabase_client():
    """
    Dependency that provides a Supabase client.
    """
    return create_client(settings.supabase_url, settings.supabase_key)
def get_exam_repository(client = Depends(get_supabase_client)) -> ExamRepository:
    """
    Dependency that provides an initialized ExamRepository.
    It automatically injects the Supabase client for you.
    """
    return ExamRepository(client)