import os
from fastapi import FastAPI
from pydantic import BaseModel
import openai
from dotenv import load_dotenv

load_dotenv()

class UserQuery(BaseModel):
    query: str

app = FastAPI()

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL")

client = openai.OpenAI(
    base_url=VLLM_BASE_URL,
    api_key="EMPTY" # vLLM 사용 시 API 키는 필요 없지만 형식상 입력
)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FINO AI Server is running!"}

@app.post("/api/v1/chat/direct")
def chat_with_llama3(request: UserQuery):
    try:
        response = client.chat.completions.create(
            model="TechxGenus/Meta-Llama-3-8B-Instruct-GPTQ", # 사용할 모델 이름
            messages=[
                {"role": "system", "content": "You are a helpful assistant for analyzing regional news."},
                {"role": "user", "content": request.query}
            ]
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}