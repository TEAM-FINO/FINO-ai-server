from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1 import reports, mock_data
from app.services.graph_service import graph_service
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 애플리케이션 시작 ---
    print("Application startup...")
    graph_service.connect() # Neo4j 드라이버 연결
    yield
    # --- 애플리케이션 종료 ---
    print("Application shutdown...")
    graph_service.close() # Neo4j 드라이버 연결 종료

app = FastAPI(
    title="FINO AI Server",
    description="""
        FINO 프로젝트의 AI 분석 서버
        - RAG 기반 리포트 생성: 사용자의 질문과 필터(지역, 카테고리)를 바탕으로 뉴스 데이터를 분석하여 개인화된 리포트를 비동기적으로 생성합니다.
        - 관리 도구: 테스트 데이터 주입 및 DB 상태 조회를 위한 엔드포인트를 제공합니다.
        """,
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}

# 기본 라우터 포함
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])

# 개발 모드일 때만 테스트용/관리자용 라우터 포함
if settings.ENV_MODE == "development":
    print("Running in development mode. Including mock data routes.")
    app.include_router(mock_data.router, prefix="/api/v1/dev", tags=["Developer Tools"])