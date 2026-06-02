from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    app_name: str = "Prepdojo"
    debug: bool = True
    database_url: str
    # Groq API Key
    groq_api_key: str = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "YOUR_OPENAI_API_URL")
    # Qdrant Configuration
    qdrant_path: str = os.getenv("QDRANT_PATH", "./qdrant_db")
    qdrant_host: str = os.getenv("QDRANT_HOST", None) # Set for cloud instance
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", None) # Set for cloud instance

    # Model Configuration
    embedding_model_name: str = "text-embedding-3-large"

    supabase_url: str = os.getenv("SUPABASE_URL")
    supabase_key: str = os.getenv("SUPABASE_KEY")
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET")
    
    LANGSMITH_TRACING: str =os.getenv("LANGSMITH_TRACING")
    LANGSMITH_ENDPOINT: str =os.getenv("LANGSMITH_ENDPOINT")
    LANGSMITH_API_KEY: str =os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_PROJECT: str =os.getenv("LANGSMITH_PROJECT")
    X_CUSTOM_HEADER: str =os.getenv("X_CUSTOM_HEADER")
    MOCK_MODE: bool = False
    class Config:
        env_file = ".env"

settings = Settings()