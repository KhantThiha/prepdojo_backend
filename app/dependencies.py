# dependencies.py
import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from groq import Groq
from openai import OpenAI

from .core.config import settings

# --- Clients & Models ---
groq_client = Groq(api_key=settings.groq_api_key)

# Embedding Model (for retrieval)

embedding_model= OpenAIEmbeddings(
    model="text-embedding-3-large",
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key
)
openai_client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_api_base
)

# Qdrant Vector Store
def get_qdrant_store(level: str)->QdrantVectorStore:
    """Initializes and returns a Qdrant vector store for a given level."""
    client = QdrantClient(
            url=settings.qdrant_host,
            api_key=settings.qdrant_api_key,
            prefer_grpc=False,
            timeout=60
            ) # Or use host/api_key for cloud
    collection_name = f"jlpt_{level}_lessons"
    embeddings = embedding_model
    vector_store=QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        
    )
    return vector_store