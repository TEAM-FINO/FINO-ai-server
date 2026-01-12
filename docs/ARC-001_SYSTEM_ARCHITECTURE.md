# 시스템 아키텍처

> **문서 번호**: ARC-001
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

FINO AI Server는 지역 뉴스를 AI로 분석하여 맞춤형 리포트를 생성하는 마이크로서비스입니다. RAG(Retrieval-Augmented Generation) 기반의 분석 파이프라인을 통해 지역별 동향 요약 및 분야별 심층 분석을 제공합니다.

### 1.1 핵심 기능

| 기능 | 설명 |
|------|------|
| RAG 기반 리포트 생성 | 벡터 검색 + LLM 분석 |
| Executive Summary | 지역 전체 핵심 이슈 분석 |
| 카테고리별 분석 | 분야별 병렬 심층 분석 |
| 화제성 랭킹 | Google API 기반 트렌드 점수 |
| 자동 스케줄링 | 주간/월간 리포트 자동 생성 |

### 1.2 설계 원칙

```
1. 비동기 우선 (Async First)
   - 모든 I/O 작업은 비동기 처리
   - Celery를 통한 백그라운드 작업 분리

2. 장애 격리 (Fault Isolation)
   - 서비스별 독립적인 컨테이너
   - 자동 재시도 및 지수 백오프

3. 확장성 (Scalability)
   - Celery Worker 수평 확장 가능
   - 카테고리별 병렬 처리

4. 관측성 (Observability)
   - 구조화된 로깅
   - 헬스체크 엔드포인트
   - Flower 모니터링
```

---

## 2. 시스템 아키텍처

### 2.1 전체 구성도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FINO AI Server                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │   Client    │───▶│  FastAPI    │───▶│   Celery    │                      │
│  │  (FINO BE)  │    │   Server    │    │   Worker    │                      │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘                      │
│                            │                   │                             │
│                            ▼                   ▼                             │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                       Service Layer                              │        │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │        │
│  │  │  Graph   │  │  Vector  │  │   LLM    │  │  Google  │        │        │
│  │  │ Service  │  │ Service  │  │ Service  │  │   API    │        │        │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │        │
│  └───────┼─────────────┼─────────────┼─────────────┼───────────────┘        │
│          │             │             │             │                         │
│          ▼             ▼             ▼             ▼                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐                 │
│  │   Neo4j   │  │ ChromaDB  │  │   vLLM    │  │  Google   │                 │
│  │  (Graph)  │  │  (Vector) │  │  Server   │  │ Search API│                 │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                    Message & Cache Layer                         │        │
│  │  ┌───────────────────────┐    ┌───────────────────────┐         │        │
│  │  │      RabbitMQ         │    │        Redis          │         │        │
│  │  │   (Message Broker)    │    │   (Result Backend)    │         │        │
│  │  └───────────────────────┘    └───────────────────────┘         │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 컴포넌트 구성

| 컴포넌트 | 역할 | 기술 스택 | 포트 |
|----------|------|-----------|------|
| fino-ai-server | REST API 서버 | FastAPI, Uvicorn | 8001 |
| celery-worker | 비동기 작업 처리 | Celery | - |
| celery-beat | 스케줄 작업 관리 | Celery Beat | - |
| vllm-server | LLM 추론 서버 | vLLM | 8002 |
| chromadb | 벡터 데이터베이스 | ChromaDB | 8000 |
| neo4j | 그래프 데이터베이스 | Neo4j Enterprise | 7687, 7474 |
| rabbitmq | 메시지 브로커 | RabbitMQ | 5672, 15672 |
| redis | 캐시 및 결과 저장소 | Redis | 6379 |
| flower | Celery 모니터링 | Flower | 5555 |
| redisinsight | Redis 관리 도구 | RedisInsight | 5540 |

---

## 3. 데이터 흐름

### 3.1 리포트 생성 흐름

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Client  │────▶│ FastAPI │────▶│ Celery  │────▶│  Neo4j  │
│         │     │         │     │ Worker  │     │ (조회)  │
└─────────┘     └─────────┘     └────┬────┘     └─────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ Google   │    │ ChromaDB │    │  vLLM    │
              │ API      │    │ (RAG)    │    │ (분석)   │
              │ (랭킹)   │    │          │    │          │
              └──────────┘    └──────────┘    └──────────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     ▼
                              ┌──────────┐
                              │  FINO    │
                              │  Server  │
                              │  (전송)  │
                              └──────────┘
```

### 3.2 비동기 작업 흐름

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  RabbitMQ   │────▶│   Celery    │
│  (Request)  │     │   (Queue)   │     │   Worker    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │    Redis    │
                                        │  (Result)   │
                                        └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   Client    │
                                        │ (Polling)   │
                                        └─────────────┘
```

---

## 4. 컴포넌트 상세

### 4.1 FastAPI Server (fino-ai-server)

**역할**: REST API 엔드포인트 제공, 요청 검증, Celery Task 디스패치

**주요 엔드포인트**:

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/health` | GET | Liveness Probe |
| `/health/ready` | GET | Readiness Probe |
| `/api/v1/reports/generate/manual` | POST | 리포트 생성 요청 |
| `/api/v1/reports/status/{task_id}` | GET | 작업 상태 조회 |
| `/api/v1/reports/admin/*` | GET | 관리자 도구 |

**설정**:

```yaml
컨테이너: fino-ai-server
포트: 8001
헬스체크: /health/ready (30초 간격)
의존성: rabbitmq, redis, vllm-server, chromadb, neo4j
```

### 4.2 Celery Worker

**역할**: 비동기 리포트 생성 작업 처리

**주요 Task**:

| Task | 역할 | 재시도 |
|------|------|--------|
| `generate_report_workflow` | 전체 워크플로우 관리 | 2회 |
| `analyze_single_category` | 카테고리별 분석 | 3회 |
| `assemble_final_report` | 결과 조립 및 전송 | 2회 |
| `dispatch_weekly_reports` | 주간 리포트 배치 | 3회 |
| `dispatch_monthly_reports` | 월간 리포트 배치 | 3회 |

**설정**:

```yaml
컨테이너: celery-worker
Prefetch: 1 (공정한 작업 분배)
타임아웃: soft 600s, hard 720s
재시도: 지수 백오프 (60s → 120s → 240s)
```

### 4.3 Celery Beat

**역할**: 주기적 작업 스케줄링

**스케줄**:

| 작업 | 주기 | 시간 |
|------|------|------|
| 주간 리포트 | 매주 월요일 | 04:00 |
| 월간 리포트 | 매월 1일 | 05:00 |

### 4.4 vLLM Server

**역할**: 대형 언어 모델 추론 서버

**설정**:

```yaml
모델: TechxGenus/Meta-Llama-3-8B-Instruct-GPTQ
양자화: gptq_marlin
GPU 메모리: 90%
OpenAI 호환 API: /v1/chat/completions
```

### 4.5 ChromaDB

**역할**: 벡터 데이터베이스, 의미론적 검색

**설정**:

```yaml
컬렉션: news_embeddings
임베딩 모델: distiluse-base-multilingual-cased-v1
검색 후보: 3개/쿼리
```

### 4.6 Neo4j

**역할**: 그래프 데이터베이스, 뉴스-지역-카테고리 관계 관리

**스키마**:

```cypher
(:Location)-[:IS_IN_LOCATION]->(:News)-[:HAS_CATEGORY]->(:Category)
```

---

## 5. 보안 아키텍처

### 5.1 컨테이너 보안

```yaml
# Docker 보안 설정
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # 최소 권한
```

### 5.2 시크릿 관리

```yaml
# Docker Secrets
secrets:
  neo4j_password:
    environment: "NEO4J_PASSWORD"
  google_api_key:
    environment: "GOOGLE_API_KEY"
```

### 5.3 네트워크 격리

```yaml
# 내부 네트워크 통신
- 서비스 간 통신은 Docker 네트워크 내부
- 외부 노출 포트 최소화
```

---

## 6. 리소스 설정

### 6.1 메모리 할당

| 서비스 | 메모리 | 설명 |
|--------|--------|------|
| vllm-server | shm 4GB | GPU 연산용 공유 메모리 |
| neo4j | 2GB 제한 | JVM 힙 메모리 |
| rabbitmq | 1GB 제한 | 메시지 버퍼 |

### 6.2 연결 풀

| 서비스 | 풀 크기 | 설명 |
|--------|---------|------|
| Neo4j | 최대 20 | 동시 연결 수 |
| RabbitMQ | 2 | Broker 연결 풀 |

---

## 7. 헬스체크

### 7.1 엔드포인트

| 경로 | 용도 | 체크 대상 |
|------|------|----------|
| `/health` | Liveness | 프로세스 생존 |
| `/health/ready` | Readiness | 모든 필수 의존성 |
| `/health/detailed` | 상세 진단 | 선택적 서비스 포함 |

### 7.2 의존성 체크

```python
# Readiness Probe 체크 대상
- Neo4j 연결
- ChromaDB 연결
- RabbitMQ 연결
- Redis 연결
- vLLM 서버 (선택적)
```

---

## 8. 모니터링

### 8.1 대시보드

| 도구 | URL | 용도 |
|------|-----|------|
| Swagger UI | :8001/docs | API 문서 및 테스트 |
| Flower | :5555 | Celery 작업 모니터링 |
| Neo4j Browser | :7474 | 그래프 데이터 시각화 |
| RabbitMQ | :15672 | 메시지 큐 관리 |
| RedisInsight | :5540 | Redis 캐시 조회 |

### 8.2 로깅

```yaml
# 로그 레벨
Development: DEBUG
Production: INFO

# 로그 포맷
Development: 상세 텍스트 포맷
Production: JSON 구조화 포맷
```

---

## 관련 문서

- [ARC-002 워크플로우](./ARC-002_WORKFLOW.md)
- [OPS-001 로컬 환경 설정](./OPS-001_LOCAL_SETUP.md)
- [DEV-001 코딩 컨벤션](./DEV-001_CODING_CONVENTION.md)
