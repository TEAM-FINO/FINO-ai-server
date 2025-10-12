from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date

class ManualReportRequest(BaseModel):
    location: str = Field(..., description="리포트를 생성할 지역명")
    start_date: date = Field(..., description="리포트 기간 시작일 (YYYY-MM-DD)")
    end_date: date = Field(..., description="리포트 기간 종료일 (YYYY-MM-DD)")
    report_type: str = Field(default="manual", description="리포트 유형 (manual, weekly, monthly 등)")

class ReportGenerationResponse(BaseModel):
    task_id: str = Field(..., description="Celery Task ID")
    message: str = Field(..., description="응답 메시지")
    workflow_task_id: Optional[str] = Field(None, description="워크플로우 체인의 Task ID (있는 경우)")  
    status: Optional[str] = Field(None, description="초기 워크플로우 상태")  

class ReportStatusResponse(BaseModel):
    status: str = Field(..., description="Task 상태 (PENDING, STARTED, COMPLETED, FAILED, REVOKED)")
    result: Optional[Any] = Field(None, description="Task 결과 (완료 시)")
    message: Optional[str] = Field(None, description="상태 메시지")
    
# Mock 데이터 주입 시 사용할 뉴스 문서 스키마
class NewsDocument(BaseModel):
    news_id: str
    press: str
    title: str
    content: str
    location: str 
    category: str 
    pubDate: str