import sys
import pathlib
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator, ValidationError, ConfigDict
from typing import Optional

class Settings(BaseSettings):
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: Optional[str] = None 
    
    CHROMA_HOST: str
    
    VLLM_BASE_URL: str
    
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_CSE_ID: str
    ENABLE_GOOGLE_API: bool
    
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    FINO_SERVER_URL: str
    
    ENV_MODE: str
    LOG_LEVEL: str
    
    ENABLE_FILE_LOGGING: bool
    
    VLLM_MODEL_NAME: str = "TechxGenus/Meta-Llama-3-8B-Instruct-GPTQ"
    EMBEDDING_MODEL_NAME: str = 'distiluse-base-multilingual-cased-v1'
    CHROMA_COLLECTION_NAME: str = "fino_news_documents"

    NEO4J_PASSWORD_FILE: Optional[str] = None
    GOOGLE_API_KEY_FILE: Optional[str] = None

    @model_validator(mode='after')
    def load_secrets_from_files(self) -> 'Settings':
        if self.NEO4J_PASSWORD_FILE:
            try:
                secret_path = pathlib.Path(self.NEO4J_PASSWORD_FILE)
                self.NEO4J_PASSWORD = secret_path.read_text().strip()
            except Exception as e:
                raise ValueError(f"Could not read secret from NEO4J_PASSWORD_FILE: {e}")
        
        if self.GOOGLE_API_KEY_FILE:
            try:
                secret_path = pathlib.Path(self.GOOGLE_API_KEY_FILE)
                self.GOOGLE_API_KEY = secret_path.read_text().strip()
            except Exception as e:
                raise ValueError(f"Could not read secret from GOOGLE_API_KEY_FILE: {e}")
                
        if not self.NEO4J_PASSWORD:
            raise ValueError("NEO4J_PASSWORD or NEO4J_PASSWORD_FILE must be set")
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY or GOOGLE_API_KEY_FILE must be set")
            
        return self

    @field_validator('NEO4J_URI')
    @classmethod
    def validate_neo4j_uri(cls, v: str) -> str:
        if not (v.startswith('bolt://') or v.startswith('neo4j://')):
            raise ValueError('NEO4J_URI must start with bolt:// or neo4j://')
        return v
    
    @field_validator('ENABLE_GOOGLE_API')
    @classmethod
    def validate_enable_google_api(cls, v: bool | str) -> bool:
        """문자열 'true'/'false'를 bool로 변환"""
        if isinstance(v, str):
            if v.lower() in ('true', '1', 'yes'):
                return True
            elif v.lower() in ('false', '0', 'no'):
                return False
            else:
                raise ValueError(f'ENABLE_GOOGLE_API must be true/false, got: {v}')
        return v
    
    @field_validator('ENV_MODE')
    @classmethod
    def validate_env_mode(cls, v: str) -> str:
        valid_modes = ['development', 'production']
        v_lower = v.lower()
        if v_lower not in valid_modes:
            raise ValueError(f'ENV_MODE must be one of {valid_modes}, got: {v}')
        return v_lower
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f'LOG_LEVEL must be one of {valid_levels}, got: {v}')
        return v_upper
    
    @field_validator('ENABLE_FILE_LOGGING')
    @classmethod
    def validate_enable_file_logging(cls, v: bool | str) -> bool:
        """문자열 'true'/'false'를 bool로 변환"""
        if isinstance(v, str):
            if v.lower() in ('true', '1', 'yes'):
                return True
            elif v.lower() in ('false', '0', 'no'):
                return False
            else:
                raise ValueError(f'ENABLE_FILE_LOGGING must be true/false, got: {v}')
        return v
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False
    )

try:
    settings = Settings()
except ValidationError as e:
    print("=" * 60)
    print("❌ CONFIGURATION ERROR: Missing or invalid environment variables")
    print("=" * 60)
    for error in e.errors():
        field = " -> ".join(str(loc) for loc in error['loc'])
        print(f"  • {field}: {error['msg']}")
    print("=" * 60)
    print("Please check your .env file and ensure all required variables are set.")
    sys.exit(1)