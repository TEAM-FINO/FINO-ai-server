# 코딩 컨벤션

> **문서 번호**: DEV-001
> **버전**: 1.0
> **최종 수정일**: 2025-01-13
> **작성자**: FINO AI Team
> **검토자**: -

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-01-13 | FINO AI Team | 최초 작성 |

---

## 1. 개요

이 문서는 FINO AI Server 프로젝트의 Python/FastAPI 코딩 컨벤션을 정의합니다. 일관된 코드 스타일을 유지하여 가독성과 유지보수성을 높이는 것이 목표입니다.

---

## 2. 기본 원칙

### 2.1 Python 버전

```
Python 3.13+
```

### 2.2 스타일 가이드

```
- PEP 8 준수
- 최대 줄 길이: 100자
- 들여쓰기: 4 spaces (탭 금지)
- 문자열: 쌍따옴표("") 기본, f-string 권장
```

---

## 3. 네이밍 규칙

### 3.1 규칙 표

| 구분 | 규칙 | 예시 |
|------|------|------|
| 파일명 | snake_case | `report_chain.py` |
| 패키지명 | snake_case | `services`, `api` |
| 클래스 | PascalCase | `ReportService`, `ExecutiveSummary` |
| 함수/메서드 | snake_case | `generate_report()`, `get_news_by_id()` |
| 변수 | snake_case | `news_data`, `task_id` |
| 상수 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `TOP_N_EXECUTIVE` |
| Private | 언더스코어 접두사 | `_internal_method()`, `_helper_func()` |

### 3.2 명명 규칙 상세

**클래스명**:
```python
# Good
class ReportService:
class ExecutiveSummary:
class NewsInfo:

# Bad
class reportService:    # PascalCase 아님
class Report_Service:   # 언더스코어 사용 금지
```

**함수명**:
```python
# Good
def generate_report():
def get_news_by_location():
def _rank_news_by_trending():  # private function

# Bad
def generateReport():   # camelCase 금지
def GetNews():          # PascalCase 금지
```

**변수명**:
```python
# Good
news_data = []
task_id = "abc123"
is_valid = True
max_retries = 3

# Bad
newsData = []       # camelCase 금지
TaskId = "abc123"   # PascalCase 금지
```

---

## 4. Import 규칙

### 4.1 Import 순서

```python
# 1. 표준 라이브러리
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

# 2. 서드파티 라이브러리
from fastapi import APIRouter, HTTPException, Depends
from celery import Celery, group, chain
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

# 3. 로컬 모듈
from app.core.config import settings
from app.services.graph_service import graph_service
from app.chains.report_chain import generate_executive_summary
```

### 4.2 Import 스타일

```python
# Good - 명시적 import
from typing import List, Dict, Optional
from datetime import datetime

# Acceptable - 모듈 import
import logging
import json

# Bad - 와일드카드 import 금지
from typing import *
from app.services import *
```

---

## 5. Type Hints

### 5.1 필수 적용 대상

```python
# 함수 파라미터 및 반환값
def generate_report(location: str, start_date: datetime) -> Dict[str, Any]:
    pass

# 클래스 속성
class ReportConfig:
    max_retries: int = 3
    timeout: float = 600.0
```

### 5.2 Type Hints 예시

```python
from typing import List, Dict, Optional, Any, Union, Callable

# 기본 타입
def get_name() -> str:
    return "name"

# 컬렉션 타입
def get_news_list() -> List[Dict[str, Any]]:
    return []

# Optional (None 가능)
def find_news(news_id: str) -> Optional[Dict[str, Any]]:
    return None

# Union (여러 타입 가능)
def process(data: Union[str, bytes]) -> str:
    pass

# Callable
def register_callback(callback: Callable[[str], None]) -> None:
    pass
```

---

## 6. Docstring

### 6.1 Google 스타일 Docstring

```python
def generate_categorical_analysis(
    category_news: List[NewsInfo],
    category_name: str
) -> Dict[str, Any]:
    """특정 카테고리 뉴스를 바탕으로 분야별 분석을 생성합니다.

    Args:
        category_news: 해당 카테고리의 뉴스 목록
        category_name: 분석할 카테고리 이름 (예: '경제', '사회')

    Returns:
        분석 결과를 담은 딕셔너리
        - category: 카테고리 이름
        - analysis_text: 분석 텍스트

    Raises:
        ValueError: category_news가 비어있는 경우
        LLMError: LLM 호출 실패 시

    Example:
        >>> result = generate_categorical_analysis(news_list, "경제")
        >>> print(result["analysis_text"])
    """
    pass
```

### 6.2 클래스 Docstring

```python
class GraphService:
    """Neo4j 그래프 데이터베이스 서비스.

    뉴스 데이터의 조회, 생성, 관계 관리를 담당합니다.

    Attributes:
        driver: Neo4j 드라이버 인스턴스
        database: 사용할 데이터베이스 이름

    Example:
        >>> service = GraphService()
        >>> service.connect()
        >>> news = service.get_all_news_by_location("춘천", start, end)
    """
    pass
```

---

## 7. FastAPI 규칙

### 7.1 라우터 정의

```python
from fastapi import APIRouter, HTTPException, status

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)
```

### 7.2 엔드포인트 작성

```python
@router.post(
    "/generate/manual",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="리포트 생성 요청",
    description="지정된 지역과 기간에 대한 리포트 생성을 요청합니다."
)
async def generate_report_manual(
    request: ReportRequest
) -> ReportResponse:
    """리포트 생성 워크플로우를 시작합니다."""
    try:
        task = generate_report_workflow.delay(
            request.location,
            request.start_date.isoformat(),
            request.end_date.isoformat(),
            request.report_type
        )
        return ReportResponse(
            task_id=task.id,
            status="WORKFLOW_DISPATCHED"
        )
    except Exception as e:
        logger.error(f"Failed to dispatch workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start report generation"
        )
```

### 7.3 Pydantic 모델

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ReportRequest(BaseModel):
    """리포트 생성 요청 모델."""

    location: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="분석 대상 지역"
    )
    start_date: datetime = Field(
        ...,
        description="분석 시작일"
    )
    end_date: datetime = Field(
        ...,
        description="분석 종료일"
    )
    report_type: str = Field(
        default="manual",
        description="리포트 타입 (manual, weekly, monthly)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "춘천",
                "start_date": "2025-01-01T00:00:00",
                "end_date": "2025-01-07T00:00:00",
                "report_type": "weekly"
            }
        }
```

---

## 8. Celery Task 규칙

### 8.1 Task 정의

```python
@celery_app.task(
    bind=True,                      # self 접근 가능
    name='reports.analyze_category', # 명시적 이름 (필수)
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True
)
def analyze_single_category(
    self,
    category_news: List[Dict],
    category_name: str
) -> Dict[str, Any]:
    """단일 카테고리 분석을 수행합니다."""
    task_id = self.request.id
    attempt = self.request.retries + 1

    logger.info(
        f"[{task_id}] Analyzing '{category_name}' "
        f"(attempt {attempt}/{self.max_retries + 1})"
    )

    try:
        result = generate_categorical_analysis(category_news, category_name)
        logger.info(f"✓ Category '{category_name}' completed")
        return {"status": "SUCCESS", "data": result}
    except Exception as e:
        logger.error(f"✗ Category '{category_name}' failed: {e}")
        raise
```

### 8.2 워크플로우 패턴

```python
from celery import chain, group

# 순차 실행
sequential = chain(task1.s(), task2.s(), task3.s())

# 병렬 실행
parallel = group(task1.s(), task2.s(), task3.s())

# 복합 패턴 (병렬 후 순차)
workflow = chain(
    group(*category_tasks),      # 병렬
    assemble_final_report.s()    # 순차
)
```

---

## 9. 에러 처리

### 9.1 예외 처리 규칙

```python
# Good - 명시적 예외 타입
try:
    result = json.loads(response)
except json.JSONDecodeError as e:
    logger.error(f"JSON parsing failed: {e}")
    raise ValueError(f"Invalid JSON response: {e}")

# Bad - bare except 금지
try:
    result = json.loads(response)
except:  # 절대 금지
    pass
```

### 9.2 커스텀 예외

```python
class ReportGenerationError(Exception):
    """리포트 생성 중 발생하는 예외."""
    pass

class LLMResponseError(Exception):
    """LLM 응답 관련 예외."""

    def __init__(self, message: str, raw_response: str = None):
        super().__init__(message)
        self.raw_response = raw_response
```

---

## 10. 금지 사항

### 10.1 절대 금지

```python
# [X] 하드코딩된 설정값
url = "http://localhost:8000"  # 금지
url = settings.VLLM_BASE_URL   # 올바름

# [X] print() 문
print("Debug message")         # 금지
logger.debug("Debug message")  # 올바름

# [X] bare except
except:                        # 금지
except Exception as e:         # 올바름

# [X] 와일드카드 import
from module import *           # 금지

# [X] 민감 정보 로깅
logger.info(f"API Key: {api_key}")  # 금지
logger.info("API call successful")   # 올바름
```

### 10.2 주의 사항

```python
# [!] 동기 블로킹 코드를 async 함수에서 직접 호출 금지
async def bad_example():
    result = requests.get(url)  # 금지 - 블로킹

async def good_example():
    async with httpx.AsyncClient() as client:
        result = await client.get(url)  # 올바름

# [!] SQL/Cypher 인젝션 방지
# 금지
query = f"MATCH (n:News {{id: '{user_input}'}})"

# 올바름
query = "MATCH (n:News {id: $news_id})"
result = session.run(query, news_id=user_input)
```

---

## 11. 코드 포맷팅

### 11.1 권장 도구

```bash
# Black (포맷터)
black --line-length 100 app/

# isort (import 정렬)
isort --profile black app/

# flake8 (린터)
flake8 --max-line-length 100 app/

# mypy (타입 체크)
mypy app/
```

### 11.2 설정 파일 예시

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py313']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_ignores = true
```

---

## 관련 문서

- [DEV-002 로그 규칙](./DEV-002_LOGGING_RULES.md)
- [DEV-003 Git 규칙](./DEV-003_GIT_RULES.md)
- [ARC-001 시스템 아키텍처](./ARC-001_SYSTEM_ARCHITECTURE.md)
