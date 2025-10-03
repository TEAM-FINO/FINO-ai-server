from fastapi import APIRouter, status
from celery.result import AsyncResult
from app.celery_worker import celery_app, generate_report_task
from app.schemas.report_schemas import ReportQuery, ReportGenerationResponse, ReportStatusResponse
from app.services.vectorstore_service import collection, embedding_model
from app.services.graph_service import graph_service
from app.schemas.report_schemas import ReportQuery, ReportGenerationResponse, ReportStatusResponse, NewsDocument

router = APIRouter()

@router.post("/generate",
             response_model=ReportGenerationResponse,
             status_code=status.HTTP_202_ACCEPTED,
             summary="비동기 리포트 생성 요청",
             description="사용자의 쿼리를 받아 리포트 생성을 Celery Worker에게 요청하고 즉시 작업 ID를 반환합니다.")
def request_report_generation(request: ReportQuery):
    task = generate_report_task.delay(request.model_dump(exclude_unset=False)) # (exclude_unset=False)를 사용하여 None 값도 명시적으로 포함
    return ReportGenerationResponse(task_id=task.id, message="Report generation has been started.")


@router.get("/status/{task_id}",
            response_model=ReportStatusResponse,
            summary="리포트 생성 상태 및 결과 조회",
            description="작업 ID를 사용하여 리포트 생성 상태(PENDING/COMPLETED)와 최종 결과를 조회합니다.")
def get_report_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    if task_result.ready():
        return ReportStatusResponse(status="COMPLETED", result=task_result.get())
    else:
        return ReportStatusResponse(status="PENDING")
    
# ChromaDB 내부 데이터 확인용 API
@router.get("/news/inspect_chroma", tags=["Admin Tools"])
def inspect_chromadb_collection():
    """(관리자/개발자용) ChromaDB 컬렉션의 모든 데이터를 조회합니다."""
    try:
        # collection.get()은 모든 데이터를 가져옵니다.
        all_data = collection.get(include=["metadatas", "documents"]) # include=["metadatas", "documents"] 로 필요한 정보만 선택
        return {"count": len(all_data['ids']), "data": all_data}
    except Exception as e:
        return {"error": str(e)} 