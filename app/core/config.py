from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # .env 파일에서 자동으로 값을 읽어와 타입 검증까지 수행
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    
    CHROMA_HOST: str
    
    VLLM_BASE_URL: str
    
    GOOGLE_API_KEY: str
    GOOGLE_CSE_ID: str
    ENABLE_GOOGLE_API: bool
    
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    FINO_SERVER_URL: str
    
    ENV_MODE: str
    LOG_LEVEL: str
    
    VLLM_MODEL_NAME: str = "TechxGenus/Meta-Llama-3-8B-Instruct-GPTQ"
    EMBEDDING_MODEL_NAME: str = 'distiluse-base-multilingual-cased-v1'
    CHROMA_COLLECTION_NAME: str = "fino_news_documents"

    class Config:
        env_file = ".env"

settings = Settings()