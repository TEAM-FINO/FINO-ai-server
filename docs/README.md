# FINO AI Server - 기술 문서

> **버전**: 1.0.0
> **최종 수정일**: 2025-01-13
> **담당자**: FINO AI Team

---

## 프로젝트 소개

**FINO AI Server**는 지역 뉴스를 AI로 분석하여 맞춤형 리포트를 생성하는 마이크로서비스입니다.

### 핵심 기능

| 기능 | 설명 |
|------|------|
| RAG 기반 리포트 생성 | LangChain + vLLM + ChromaDB 기반 분석 |
| 지역별 동향 요약 | Executive Summary 자동 생성 |
| 분야별 심층 분석 | 카테고리별 병렬 처리 |
| 주기적 리포트 | Celery Beat 스케줄링 (주간/월간) |
| 화제성 랭킹 | Google Search API 활용 |

### 기술 스택

```
┌─────────────────────────────────────────────────────────┐
│  Framework    │  FastAPI 0.127.0, Uvicorn               │
│  AI/ML        │  LangChain 0.3.14, vLLM, SentenceTransformers │
│  Database     │  Neo4j 5.26 (Graph), ChromaDB 1.4.0 (Vector) │
│  Async        │  Celery 5.6.1, RabbitMQ 4.0, Redis 7.4  │
│  External     │  Google Custom Search API               │
└─────────────────────────────────────────────────────────┘
```

---

## 문서 번호 체계

| 접두사 | 분류 | 설명 |
|--------|------|------|
| `ARC` | Architecture | 시스템 아키텍처, 설계 문서 |
| `DEV` | Development | 개발 규칙, 코딩 컨벤션 |
| `OPS` | Operations | 운영, 배포, 환경 설정 |
| `API` | API | API 명세, 인터페이스 문서 |
| `TRB` | Troubleshooting | 장애 대응, 트러블슈팅 |

### 문서 상태

| 상태 | 설명 |
|------|------|
| ✅ Active | 현재 유효한 문서 |
| 📝 Draft | 작성 중 |
| 📋 Planned | 작성 예정 |

---

## 문서 목록

### Architecture (ARC) - 시스템 설계

| 번호 | 문서명 | 설명 | 상태 |
|------|--------|------|------|
| [ARC-001](./ARC-001_SYSTEM_ARCHITECTURE.md) | 시스템 아키텍처 | 전체 시스템 구조 및 컴포넌트 | ✅ Active |
| [ARC-002](./ARC-002_WORKFLOW.md) | 워크플로우 | 리포트 생성 워크플로우 상세 | ✅ Active |
| [ARC-003](./ARC-003_DATABASE.md) | 데이터베이스 | Neo4j, ChromaDB 스키마 | 📋 Planned |

### Development (DEV) - 개발 규칙

| 번호 | 문서명 | 설명 | 상태 |
|------|--------|------|------|
| [DEV-001](./DEV-001_CODING_CONVENTION.md) | 코딩 컨벤션 | Python/FastAPI 코딩 규칙 | ✅ Active |
| [DEV-002](./DEV-002_LOGGING_RULES.md) | 로그 규칙 | 로그 레벨, 포맷, 필수 항목 | ✅ Active |
| [DEV-003](./DEV-003_GIT_RULES.md) | Git 규칙 | 브랜치 전략, 커밋 메시지 | ✅ Active |
| [DEV-004](./DEV-004_ERROR_HANDLING.md) | 에러 핸들링 | 예외 처리, 재시도 전략 | 📋 Planned |

### Operations (OPS) - 운영

| 번호 | 문서명 | 설명 | 상태 |
|------|--------|------|------|
| [OPS-001](./OPS-001_LOCAL_SETUP.md) | 로컬 환경 설정 | 개발 환경 구성 가이드 | ✅ Active |
| [OPS-002](./OPS-002_DEPLOYMENT.md) | 배포 가이드 | Docker Compose 배포 | 📋 Planned |
| [OPS-003](./OPS-003_MONITORING.md) | 모니터링 | Flower, 헬스체크 | 📋 Planned |

### API (API) - 인터페이스

| 번호 | 문서명 | 설명 | 상태 |
|------|--------|------|------|
| [API-001](./API-001_REST_API.md) | REST API | API 엔드포인트 명세 | 📋 Planned |

### Troubleshooting (TRB) - 장애 대응

| 번호 | 문서명 | 설명 | 상태 |
|------|--------|------|------|
| [TRB-001](./TRB-001_COMMON_ERRORS.md) | 일반 오류 | 자주 발생하는 오류 및 해결법 | 📋 Planned |

---

## Quick Start

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd FINO-ai-server

# 환경 변수 설정
cp .env.example .env
# .env 파일 수정
```

### 2. Docker Compose 실행

```bash
docker compose --env-file .env up -d
```

### 3. 서비스 확인

| 서비스 | URL | 설명 |
|--------|-----|------|
| API Server | http://localhost:8001/docs | Swagger UI |
| Flower | http://localhost:5555 | Celery 모니터링 |
| Neo4j Browser | http://localhost:7474 | 그래프 DB |
| RabbitMQ | http://localhost:15672 | 메시지 큐 관리 |
| RedisInsight | http://localhost:5540 | Redis 관리 |

---

## Quick Links

| 문서 | 설명 |
|------|------|
| [CLAUDE.md](../CLAUDE.md) | AI 코드 어시스턴트 규칙 |
| [docker-compose.yml](../docker-compose.yml) | 인프라 구성 |
| [requirements.txt](../requirements.txt) | Python 의존성 |

---

## 연락처

| 역할 | 담당 | 연락처 |
|------|------|--------|
| Tech Lead | - | - |
| Backend | - | - |
| AI/ML | - | - |

---

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0.0 | 2025-01-13 | FINO AI Team | 최초 작성 |
