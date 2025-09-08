from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "FINO AI 서버에 오신 것을 환영합니다!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}