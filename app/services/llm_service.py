from app.core.config import settings
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=settings.VLLM_MODEL_NAME,
    openai_api_base=settings.VLLM_BASE_URL,
    openai_api_key="EMPTY",
    temperature=0.7,
)