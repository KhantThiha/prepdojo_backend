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
    
    class Config:
        env_file = ".env"

settings = Settings()