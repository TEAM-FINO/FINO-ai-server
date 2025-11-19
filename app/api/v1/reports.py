from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from celery.result import AsyncResult
from celery.states import PENDING, SUCCESS, FAILURE, REVOKED, STARTED
from datetime import datetime, time
from app.celery_worker import celery_app, generate_report_workflow
from app.schemas.report_schemas import ManualReportRequest, ReportGenerationResponse, ReportStatusResponse 
from app.services.vectorstore_service import collection, embedding_model
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
        
        # 워크플로우 Task 시작
        task = generate_report_workflow.delay(
            location=request.location,
            start_date_iso=start_datetime.isoformat(),
            end_date_iso=end_datetime.isoformat(),
            report_type=request.report_type
        )
        
        # 기본 응답 데이터
        response_data = {
            "task_id": task.id,
            "message": "Report generation workflow has been started.",
            "status": "WORKFLOW_DISPATCHED"  # 기본 상태
        }
        
        # Eager 모드(동기 실행)인 경우에만 즉시 결과 확인 가능
        if celery_app.conf.task_always_eager:
            try:
                workflow_result = task.get(timeout=1)  # 1초 타임아웃
                if workflow_result and isinstance(workflow_result, dict):
                    response_data["workflow_task_id"] = workflow_result.get("workflow_task_id")
                    response_data["status"] = workflow_result.get("status", "WORKFLOW_STARTED")
            except Exception as e:
                # Eager 모드에서도 에러가 발생할 수 있음
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Workflow execution failed: {str(e)}"
                )
        else:
            # 비동기 모드: Task ID만 반환 (결과는 나중에 /status 엔드포인트로 확인)
            # workflow_task_id는 워크플로우 내부에서 생성되므로 지금은 알 수 없음
            response_data["status"] = "WORKFLOW_DISPATCHED"
        
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
            
            if isinstance(result_data, dict):
                workflow_status = result_data.get("status")
                
                # WORKFLOW_STARTED 상태인 경우, 하위 chain의 진행 상황 확인
                if workflow_status == "WORKFLOW_STARTED":
                    workflow_task_id = result_data.get("workflow_task_id")
                    if workflow_task_id:
                        # 하위 워크플로우 상태 확인
                        workflow_task = AsyncResult(workflow_task_id, app=celery_app)
                        workflow_state = workflow_task.state
                        
                        if workflow_state == SUCCESS:
                            # 하위 워크플로우도 완료됨
                            workflow_result = workflow_task.get()
                            return ReportStatusResponse(
                                status="COMPLETED",
                                result=workflow_result,
                                message="Full workflow completed successfully."
                            )
                        elif workflow_state == FAILURE:
                            return ReportStatusResponse(
                                status="FAILED",
                                result={"error": str(workflow_task.info)},
                                message="Workflow failed."
                            )
                        elif workflow_state in [STARTED, PENDING]:
                            return ReportStatusResponse(
                                status="PROCESSING",
                                result=result_data,
                                message="Workflow is still in progress."
                            )
                
                # SKIPPED 또는 FAILED 상태
                elif workflow_status in ["SKIPPED", "FAILED"]:
                    return ReportStatusResponse(
                        status=workflow_status,
                        result=result_data,
                        message=result_data.get("reason", "Workflow did not complete.")
                    )
            
            # 일반적인 성공 케이스
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
def inspect_chromadb_collection(limit: int = 100,offset: int = 0,include_documents: bool = False):
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
        
# Pydantic 모델 추가 (타입 안정성)
class ChromaDocument(BaseModel):
    """ChromaDB 단일 문서 응답 모델"""
    id: str
    metadata: Optional[dict] = None
    document: Optional[str] = None

class ChromaCollectionResponse(BaseModel):
    """ChromaDB 컬렉션 조회 응답 모델"""
    total_count: int
    returned_count: int
    offset: int
    limit: int
    documents: List[ChromaDocument]

@router.get(
    "/admin/chromadb/documents",
    response_model=ChromaCollectionResponse,
    tags=["Admin Tools"],
    summary="ChromaDB 문서 조회 (가독성 향상)",
    description="ChromaDB 컬렉션의 데이터를 사람이 읽기 쉬운 형태로 조회합니다."
)
def get_chromadb_documents(
    limit: int = 25,
    offset: int = 0,
    include_documents: bool = True,
    search_query: Optional[str] = None
) -> ChromaCollectionResponse:
    """
    ChromaDB 문서를 통합된 객체 리스트로 반환합니다.
    
    Args:
        limit: 한 번에 가져올 문서 개수 (기본 25, 최대 100)
        offset: 건너뛸 문서 개수 (페이지네이션)
        include_documents: 문서 내용 포함 여부 (기본 True)
        search_query: (선택) 메타데이터 title 필터링 (부분 일치)
    
    Returns:
        ChromaCollectionResponse: 통합된 문서 리스트
    
    Example:
        GET /api/v1/reports/admin/chromadb/documents?limit=10&offset=0&search_query=춘천
    """
    try:
        # Limit 제한 (과도한 요청 방지)
        limit = min(limit, 100)
        
        # 전체 개수 확인
        total_count = collection.count()
        
        if offset >= total_count:
            return ChromaCollectionResponse(
                total_count=total_count,
                returned_count=0,
                offset=offset,
                limit=limit,
                documents=[]
            )
        
        # ChromaDB 조회
        include_fields = ["metadatas"]
        if include_documents:
            include_fields.append("documents")
        
        try:
            db_data = collection.get(
                include=include_fields,
                limit=limit,
                offset=offset
            )
        except TypeError:
            # Fallback for older ChromaDB versions
            all_data = collection.get(include=include_fields)
            db_data = {
                "ids": all_data['ids'][offset:offset+limit],
                "metadatas": all_data.get('metadatas', [])[offset:offset+limit],
                "documents": all_data.get('documents', [])[offset:offset+limit] if include_documents else None
            }
        
        # 데이터 통합 및 필터링
        formatted_documents = []
        ids = db_data.get('ids', [])
        metadatas = db_data.get('metadatas', [])
        documents = db_data.get('documents')
        
        for i, doc_id in enumerate(ids):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            document = documents[i] if documents and i < len(documents) else None
            
            # 검색 쿼리 필터링 (title 기준)
            if search_query:
                title = metadata.get('title', '')
                if search_query.lower() not in title.lower():
                    continue
            
            formatted_documents.append(
                ChromaDocument(
                    id=doc_id,
                    metadata=metadata,
                    document=document
                )
            )
        
        return ChromaCollectionResponse(
            total_count=total_count,
            returned_count=len(formatted_documents),
            offset=offset,
            limit=limit,
            documents=formatted_documents
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB 데이터 조회 중 오류 발생: {str(e)}"
        )


@router.get(
    "/admin/chromadb/search",
    tags=["Admin Tools"],
    summary="ChromaDB 유사도 검색",
    description="텍스트 쿼리로 유사한 문서를 검색합니다."
)
def search_chromadb(
    query: str,
    n_results: int = 5
) -> Dict[str, Any]:
    """
    벡터 유사도 검색으로 관련 문서를 찾습니다.
    
    Args:
        query: 검색할 텍스트 (예: "춘천 데이터센터")
        n_results: 반환할 결과 개수 (기본 5, 최대 20)
    
    Returns:
        유사도 점수와 함께 정렬된 문서 리스트
    """
    try:
        n_results = min(n_results, 20)
        
        # 쿼리 임베딩
        query_vector = embedding_model.encode([query]).tolist()
        
        # 벡터 검색
        results = collection.query(
            query_embeddings=query_vector,
            n_results=n_results,
            include=["metadatas", "documents", "distances"]
        )
        
        # 결과 통합
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                "id": results['ids'][0][i],
                "metadata": results['metadatas'][0][i],
                "document": results['documents'][0][i],
                "similarity_score": 1 - results['distances'][0][i]  # Distance → Similarity
            })
        
        return {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 중 오류 발생: {str(e)}"
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