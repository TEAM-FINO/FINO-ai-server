from fastapi import APIRouter, status, HTTPException
from celery.result import AsyncResult
from celery.states import PENDING, SUCCESS, FAILURE, REVOKED, STARTED
from datetime import datetime, time
from app.celery_worker import celery_app, generate_report_workflow
from app.schemas.report_schemas import ManualReportRequest, ReportGenerationResponse, ReportStatusResponse 
from app.services.vectorstore_service import collection
from app.services.health_service import check_all_services

router = APIRouter()

@router.post("/generate/manual",
             response_model=ReportGenerationResponse,
             status_code=status.HTTP_202_ACCEPTED,
             summary="(수동) 리포트 생성 워크플로우 실행",
             description="개발/테스트 목적으로, 지정된 지역과 기간의 리포트 생성 워크플로우를 수동으로 실행합니다.")
def request_manual_report_generation(request: ManualReportRequest):
    """수동 리포트 생성 요청을 처리합니다."""
    try:
        # Pydantic의 date 타입을 Celery가 인식하는 datetime ISO 문자열로 변환
        start_datetime = datetime.combine(request.start_date, time.min)
        end_datetime = datetime.combine(request.end_date, time.max)
        
        # 기간 유효성 검증
        if start_datetime > end_datetime:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before or equal to end_date"
            )
        
        # 너무 먼 미래 날짜 방지
        if end_datetime > datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date cannot be in the future"
            )
        
        task = generate_report_workflow.delay(
            location=request.location,
            start_date_iso=start_datetime.isoformat(),
            end_date_iso=end_datetime.isoformat(),
            report_type=request.report_type
        )
        
        # 워크플로우 Task의 결과를 즉시 확인 (WORKFLOW_STARTED 반환)
        # eager 모드가 아니면 None일 수 있음
        workflow_result = None
        if task.ready():
            workflow_result = task.get()
        
        response_data = {
            "task_id": task.id,
            "message": "Report generation workflow has been started."
        }
        
        # 워크플로우가 시작한 하위 chain ID도 반환
        if workflow_result and isinstance(workflow_result, dict):
            if "workflow_task_id" in workflow_result:
                response_data["workflow_task_id"] = workflow_result["workflow_task_id"]
            response_data["status"] = workflow_result.get("status", "WORKFLOW_STARTED")
        
        return ReportGenerationResponse(**response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start report generation: {str(e)}"
        )


@router.get("/status/{task_id}",
            response_model=ReportStatusResponse,
            summary="리포트 생성 상태 및 결과 조회",
            description="작업 ID를 사용하여 리포트 생성 상태와 최종 결과를 조회합니다.")
def get_report_status(task_id: str):
    """Task 상태를 조회하고 결과를 반환합니다."""
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        # 상태별 분기 처리
        task_state = task_result.state
        
        if task_state == PENDING:
            # Task가 아직 시작 안 됨 또는 존재하지 않음
            return ReportStatusResponse(
                status="PENDING",
                message="Task is waiting to be processed or does not exist."
            )
        
        elif task_state == STARTED:
            # Task 실행 중
            return ReportStatusResponse(
                status="STARTED",
                message="Task is currently being processed."
            )
        
        elif task_state == SUCCESS:
            # 성공적으로 완료
            result_data = task_result.get()
            return ReportStatusResponse(
                status="COMPLETED",
                result=result_data,
                message="Task completed successfully."
            )
        
        elif task_state == FAILURE:
            # 실패
            error_info = {
                "error": str(task_result.info),  # 예외 정보
                "traceback": task_result.traceback  # 스택 트레이스
            }
            return ReportStatusResponse(
                status="FAILED",
                result=error_info,
                message="Task failed with an error."
            )
        
        elif task_state == REVOKED:
            # 취소됨
            return ReportStatusResponse(
                status="REVOKED",
                message="Task was revoked (cancelled)."
            )
        
        else:
            # 기타 상태 (RETRY 등)
            return ReportStatusResponse(
                status=task_state,
                message=f"Task is in state: {task_state}"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve task status: {str(e)}"
        )

# ChromaDB 내부 데이터 확인용 API 
@router.get("/news/inspect_chroma", tags=["Admin Tools"])
def inspect_chromadb_collection(
    limit: int = 100,
    offset: int = 0,
    include_documents: bool = False
):
    """
    (관리자/개발자용) ChromaDB 컬렉션의 데이터를 조회합니다.
    
    - limit: 한 번에 가져올 최대 개수 (기본 100, 최대 1000)
    - offset: 건너뛸 개수 (페이지네이션용)
    - include_documents: 문서 내용 포함 여부 (기본 False)
    """
    try:
        # limit 제한 (너무 큰 요청 방지)
        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit cannot exceed 1000"
            )
            
        # 전체 개수 먼저 확인
        total_count = collection.count()
        
        # offset이 전체 개수를 초과하면 빈 결과 반환
        if offset >= total_count:
            return {
                "total_count": total_count,
                "returned_count": 0,
                "offset": offset,
                "limit": limit,
                "data": {"ids": [], "metadatas": []}
            }
        
        # 요청된 범위만 가져오기
        include_fields = ["metadatas"]
        if include_documents:
            include_fields.append("documents")
        
        # 모든 데이터를 가져온 후 슬라이싱
        # ChromaDB v0.4.0+ 에서는 limit/offset 지원
        try:
            data = collection.get(
                include=include_fields,
                limit=limit,
                offset=offset
            )
        except TypeError:
            # 구버전 ChromaDB는 limit/offset 미지원 - fallback
            all_data = collection.get(include=include_fields)
            start_idx = offset
            end_idx = offset + limit
            
            data = {
                "ids": all_data['ids'][start_idx:end_idx],
                "metadatas": all_data['metadatas'][start_idx:end_idx],
            }
            if include_documents:
                data["documents"] = all_data['documents'][start_idx:end_idx]

        
        return {
            "total_count": total_count,
            "returned_count": len(data['ids']),
            "offset": offset,
            "limit": limit,
            "data": data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to inspect ChromaDB: {str(e)}"
        )
        
        
@router.get("/admin/db_stats", tags=["Admin Tools"])
def get_database_statistics():
    """(관리자용) 데이터베이스 통계를 조회합니다."""
    from app.services.graph_service import graph_service
    return graph_service.get_database_stats()


@router.get("/admin/health", tags=["Admin Tools"])
def get_detailed_health():
    """
    (관리자용) 서비스 연결 상태를 상세히 조회합니다.
    
    이 엔드포인트는 관리 목적으로 더 자세한 정보를 제공합니다.
    Kubernetes readiness probe는 /health/ready를 사용하세요.
    """
    return check_all_services()