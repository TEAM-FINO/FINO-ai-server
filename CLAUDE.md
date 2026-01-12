# CLAUDE.md - AI 코드 어시스턴트 규칙

> 이 문서는 Claude Code가 FINO AI Server 프로젝트에서 작업할 때 따라야 할 규칙을 정의합니다.

---

## 프로젝트 개요

- **프로젝트명**: FINO AI Server
- **목적**: 지역 뉴스를 AI로 분석하여 맞춤형 리포트를 생성하는 마이크로서비스
- **기술 스택**:
  - Framework: FastAPI 0.127.0, Uvicorn
  - AI/ML: LangChain 0.3.14, vLLM, SentenceTransformers
  - Database: Neo4j 5.26 (Graph), ChromaDB 1.4.0 (Vector)
  - Async: Celery 5.6.1, RabbitMQ 4.0, Redis 7.4
  - External: Google Custom Search API

---

## 프로젝트 구조

```
FINO-ai-server/
├── app/
│   ├── main.py                    # FastAPI 애플리케이션 진입점
│   ├── celery_worker.py           # Celery Task 정의 및 워크플로우
│   │
│   ├── api/v1/                    # REST API 엔드포인트
│   │   ├── reports.py             # 리포트 생성 API
│   │   └── mock_data.py           # 개발용 테스트 데이터 API
│   │
│   ├── chains/                    # LangChain 분석 파이프라인
│   │   └── report_chain.py        # Executive Summary, 카테고리 분석
│   │
│   ├── services/                  # 비즈니스 로직 및 외부 서비스
│   │   ├── graph_service.py       # Neo4j 그래프 DB
│   │   ├── vectorstore_service.py # ChromaDB 벡터 저장소
│   │   ├── llm_service.py         # LLM 클라이언트
│   │   ├── google_api_service.py  # Google Search API
│   │   ├── health_service.py      # 헬스체크
│   │   └── fino_api_service.py    # FINO 서버 연동
│   │
│   ├── schemas/                   # Pydantic 데이터 모델
│   │   └── report_schemas.py
│   │
│   └── core/                      # 애플리케이션 설정
│       ├── config.py              # 환경 변수 관리
│       └── logging_config.py      # 로깅 설정
│
├── scripts/                       # 유틸리티 스크립트
├── tests/                         # 테스트 코드
├── docs/                          # 기술 문서
├── docker-compose.yml             # 서비스 오케스트레이션
└── requirements.txt               # Python 의존성
```

---

## 필수 규칙

### 1. 코드 스타일

```
- Python 3.13+ 문법 사용
- PEP 8 스타일 가이드 준수
- Type Hints 필수 (함수 파라미터, 반환값)
- Docstring: Google 스타일
- 최대 줄 길이: 100자
- 들여쓰기: 4 spaces
```

### 2. FastAPI 규칙

```python
# 라우터 정의
router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

# 엔드포인트 작성
@router.post("/generate", response_model=ReportResponse, status_code=202)
async def generate_report(request: ReportRequest) -> ReportResponse:
    """리포트 생성을 요청합니다."""
    pass

# 의존성 주입 활용
def get_db() -> Generator[Session, None, None]:
    pass
```

### 3. Celery Task 규칙

```python
# Task 정의 시 필수 설정
@celery_app.task(
    bind=True,
    name='reports.task_name',      # 명시적 이름
    max_retries=3,                  # 재시도 횟수
    default_retry_delay=60,         # 재시도 간격
    autoretry_for=(Exception,),     # 자동 재시도 예외
    retry_backoff=True              # 지수 백오프
)
def task_name(self, param: str) -> dict:
    pass
```

### 4. 네이밍 규칙

| 구분 | 규칙 | 예시 |
|------|------|------|
| 파일명 | snake_case | `report_chain.py` |
| 클래스 | PascalCase | `ReportService` |
| 함수/메서드 | snake_case | `generate_report()` |
| 상수 | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| 변수 | snake_case | `news_data` |
| Pydantic 모델 | PascalCase | `ExecutiveSummary` |
| Celery Task | snake_case | `analyze_single_category` |

### 5. Import 순서

```python
# 1. 표준 라이브러리
import logging
from datetime import datetime
from typing import List, Dict, Optional

# 2. 서드파티 라이브러리
from fastapi import APIRouter, HTTPException
from celery import Celery, group, chain
from pydantic import BaseModel

# 3. 로컬 모듈
from app.core.config import settings
from app.services.graph_service import graph_service
```

---

## 금지 사항

### 절대 하지 말 것

```
[X] 환경 변수를 코드에 하드코딩 (반드시 settings 사용)
[X] 동기 블로킹 코드를 async 함수 내에서 직접 호출
[X] except: (bare except) 사용 - 명시적 예외 타입 지정
[X] print() 문 사용 - logger 사용
[X] TODO 주석만 남기고 구현 미완료 상태로 커밋
[X] 테스트 없이 Celery Task 수정
[X] .env 파일을 Git에 커밋
[X] API 키, 비밀번호 등 민감 정보 로깅
```

### 주의 사항

```
[!] Neo4j 쿼리 작성 시 파라미터 바인딩 필수 (Cypher Injection 방지)
[!] ChromaDB 쿼리 결과는 항상 빈 리스트 체크
[!] LLM 응답은 JSON 파싱 실패 가능성 고려 (재시도 로직)
[!] Google API Rate Limit 고려 (병렬 호출 제한)
```

---

## 로그 규칙

| 레벨 | 사용 상황 | 예시 |
|------|----------|------|
| `ERROR` | 즉시 대응 필요, 작업 실패 | DB 연결 실패, Task 최종 실패 |
| `WARNING` | 잠재적 문제, 재시도 발생 | API Rate Limit, 파싱 재시도 |
| `INFO` | 주요 이벤트, 작업 진행 | 워크플로우 시작/완료, Task 디스패치 |
| `DEBUG` | 디버깅 정보 | 쿼리 파라미터, 중간 결과값 |

### 로그 포맷

```python
# Task 로그
logger.info(f"[{task_id}] Workflow started for '{location}' ({report_type})")

# 성공/실패 표시
logger.info(f"✓ Category '{category_name}' analysis completed successfully.")
logger.error(f"✗ Category '{category_name}' analysis failed: {e}")

# 통계 로그
logger.info(f"Context stats: retrieved={total}, added={added}, final_length={len(ctx)} chars")
```

---

## Git 규칙

### 브랜치 전략

```
main                    # 프로덕션 배포
├── develop             # 개발 통합
│   ├── feat/#이슈번호_기능명
│   ├── fix/#이슈번호_버그명
│   ├── refactor/#이슈번호_대상
│   └── docs/#이슈번호_문서명
```

### 커밋 메시지

```
<type>: <subject>

[Feat]: 새로운 기능 추가
[Fix]: 버그 수정
[Refactor]: 코드 리팩토링
[Docs]: 문서 수정
[Test]: 테스트 코드
[Chore]: 빌드, 설정 변경

예시:
[Feat]: 주기적 리포트 생성 및 운영 고도화 기능 구현
[Fix]: LLM JSON 파싱 실패 시 재시도 로직 추가
```

---

## 자주 사용하는 명령어

```bash
# 로컬 개발 서버 실행
uvicorn app.main:app --reload --port 8001

# Docker Compose 실행
docker compose --env-file .env up -d

# Celery Worker 실행
celery -A app.celery_worker.celery_app worker --loglevel=info -P solo

# Celery Beat 실행
celery -A app.celery_worker.celery_app beat --loglevel=info

# 테스트 실행
pytest tests/ -v

# 테스트 데이터 주입
python scripts/seed_data.py

# 데모 리포트 생성
python scripts/generate_demo_report.py
```

---

## 핵심 워크플로우

```
API 요청 → generate_report_workflow (Main Task)
    │
    ├─ Neo4j 뉴스 조회
    ├─ Executive Summary 생성 (LangChain + vLLM)
    │
    ├─ 병렬 카테고리 분석 (Celery group)
    │   ├─ 화제성 랭킹 (Google API)
    │   ├─ 컨텍스트 확장 (ChromaDB RAG)
    │   └─ 분석 생성 (LangChain + vLLM)
    │
    └─ 최종 리포트 조립 → FINO 서버 전송
```

---

## 환경 변수

```bash
# 필수 환경 변수
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<secret>
CHROMA_HOST=chromadb
VLLM_BASE_URL=http://vllm-server:8000/v1
CELERY_BROKER_URL=pyamqp://guest@rabbitmq//
CELERY_RESULT_BACKEND=redis://redis:6379/0
GOOGLE_API_KEY=<secret>
GOOGLE_CSE_ID=<secret>
ENABLE_GOOGLE_API=true
FINO_SERVER_URL=http://be_fino:8080
ENV_MODE=development
LOG_LEVEL=INFO
```

---

## 문서 참조

- [docs/README.md](./docs/README.md) - 전체 문서 목록
- [docs/ARC-001_SYSTEM_ARCHITECTURE.md](./docs/ARC-001_SYSTEM_ARCHITECTURE.md) - 시스템 아키텍처
- [docs/ARC-002_WORKFLOW.md](./docs/ARC-002_WORKFLOW.md) - 워크플로우 상세
