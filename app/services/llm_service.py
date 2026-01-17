from app.core.config import settings
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=settings.LLM_MODEL_NAME,
    openai_api_key=settings.OPENAI_API_KEY,
    temperature=0.7,
)