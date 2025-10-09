from pydantic import BaseModel
from typing import Optional, List

class ReportRequest(BaseModel):
    location: str
    categories: Optional[List[str]] = None
    # period: str # 'weekly', 'monthly' 
  
class ReportGenerationResponse(BaseModel):
    task_id: str
    message: str

class ReportStatusResponse(BaseModel):
    status: str
    result: Optional[dict] = None
    
# Mock 데이터 주입 시 사용할 뉴스 문서 스키마
class NewsDocument(BaseModel):
    news_id: str
    press: str
    title: str
    content: str
    location: str # Neo4j에 관계를 맺기 위해 필요
    category: str # Neo4j에 관계를 맺기 위해 필요