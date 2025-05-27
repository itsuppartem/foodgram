from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "foodgram"
    
    GEMINI_API_KEY: str = ""
    DJANGO_API_URL: str = "http://localhost:8000/api/"
    DJANGO_AUTH_TOKEN: str = ""
    DJANGO_AUTH_URL: str = "http://localhost:8000/api/auth/token/login/"
    
    API_KEY: str = "123"
    
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    EMBEDDING_MODEL_NAME: str = "ai-forever/sbert_large_nlu_ru"

    class Config:
        env_file = ".env"

settings = Settings() 