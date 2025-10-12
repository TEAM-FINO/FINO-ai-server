import logging
import logging.config
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logging_config import get_logging_config
from app.api.v1 import reports, mock_data
from app.services.graph_service import graph_service
from app.services.health_service import check_all_services

def setup_logging():
    """애플리케이션 로깅을 설정합니다."""
    # 설정 딕셔너리 가져오기
    logging_config = get_logging_config(
        log_level=settings.LOG_LEVEL,
        env_mode=settings.ENV_MODE
    )
    
    # dictConfig 적용
    logging.config.dictConfig(logging_config)
    
    # 초기화 로그
    logger = logging.getLogger("app")
    logger.info(f"🔧 Logging configured: level={settings.LOG_LEVEL.upper()}, mode={settings.ENV_MODE}")
    
    if settings.ENV_MODE == 'production':
        logger.info("📊 JSON logging enabled for production")

# 로깅 설정 실행
setup_logging()
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = logging.getLogger("app.main")
    # --- 애플리케이션 시작 ---
    logger.info("🚀 Application startup...")
    try:
        graph_service.connect()
        logger.info("✓ Neo4j connection established")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Neo4j: {e}", exc_info=True)
        raise
    yield
    # --- 애플리케이션 종료 ---
    logger.info("🛑 Application shutdown...")
    graph_service.close()
    logger.info("✓ Neo4j connection closed")

app = FastAPI(
    title="FINO AI Server",
    description="""
        FINO 프로젝트의 AI 분석 서버
        - RAG 기반 리포트 생성: 지역, 카테고리를 바탕으로 뉴스 데이터를 분석하여 리포트를 비동기적으로 생성합니다.
        - 관리 도구: 테스트 데이터 주입 및 DB 상태 조회를 위한 엔드포인트를 제공합니다.
        """,
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/health", tags=["System"])
def liveness_check():
    """
    Liveness Probe: 서비스 프로세스가 살아있는지 확인합니다.
    
    Kubernetes liveness probe에서 사용됩니다.
    이 엔드포인트는 항상 200을 반환해야 합니다.
    """
    return {"status": "ok", "env_mode": settings.ENV_MODE}


@app.get("/health/ready", tags=["System"])
def readiness_check():
    """
    Readiness Probe: 서비스가 요청을 처리할 준비가 되었는지 확인합니다.
    
    모든 의존 서비스(Neo4j, ChromaDB, Celery)의 상태를 확인하고,
    하나라도 unhealthy면 503 Service Unavailable을 반환합니다.
    
    Kubernetes readiness probe 및 로드밸런서에서 사용됩니다.
    """
    health_status = check_all_services()
    
    if health_status.get("overall") != "healthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status
        )
    
    return health_status

# 기본 라우터 포함
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])

# 개발 모드일 때만 테스트용/관리자용 라우터 포함
if settings.ENV_MODE == "development":
    logger = logging.getLogger("app.main")
    logger.info("🔧 Running in development mode. Including mock data routes.")
    app.include_router(mock_data.router, prefix="/api/v1/dev", tags=["Developer Tools"])