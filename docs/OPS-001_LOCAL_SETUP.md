# 로컬 환경 설정

> **문서 번호**: OPS-001
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

이 문서는 FINO AI Server 프로젝트의 로컬 개발 환경 설정 방법을 안내합니다.

---

## 2. 사전 요구사항

### 2.1 필수 소프트웨어

| 소프트웨어 | 최소 버전 | 권장 버전 | 비고 |
|------------|----------|----------|------|
| Docker | 24.0+ | 최신 | Docker Desktop 권장 |
| Docker Compose | 2.20+ | 최신 | Docker Desktop에 포함 |
| Python | 3.11+ | 3.13 | 로컬 개발 시 |
| Git | 2.30+ | 최신 | - |

### 2.2 하드웨어 요구사항

| 환경 | CPU | RAM | GPU | 저장공간 |
|------|-----|-----|-----|---------|
| 최소 | 4코어 | 16GB | - | 50GB |
| 권장 | 8코어+ | 32GB+ | NVIDIA GPU | 100GB+ |

> **Note**: vLLM 서버는 NVIDIA GPU가 필요합니다. GPU가 없는 환경(M1 Mac 등)에서는 Ollama 또는 외부 LLM API를 사용해야 합니다.

---

## 3. 설치 및 설정

### 3.1 저장소 클론

```bash
git clone <repository-url>
cd FINO-ai-server
```

### 3.2 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env
```

**.env 파일 수정**:

```bash
# 데이터베이스 연결 설정
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password   # 변경 필요

# ChromaDB 설정
CHROMA_HOST=chromadb

# vLLM 설정
VLLM_BASE_URL=http://vllm-server:8000/v1

# Google Search API 설정
GOOGLE_API_KEY=your_google_api_key    # 변경 필요
GOOGLE_CSE_ID=your_cse_id             # 변경 필요
ENABLE_GOOGLE_API=true

# Celery 설정
CELERY_BROKER_URL=pyamqp://guest@rabbitmq//
CELERY_RESULT_BACKEND=redis://redis:6379/0

# FINO 서버 주소
FINO_SERVER_URL=http://be_fino:8080

# 개발 설정
ENV_MODE=development
LOG_LEVEL=DEBUG
ENABLE_FILE_LOGGING=false
```

### 3.3 Docker Compose 실행

```bash
# 전체 서비스 실행
docker compose --env-file .env up -d

# 또는 빌드와 함께 실행
docker compose --env-file .env up -d --build
```

### 3.4 서비스 상태 확인

```bash
# 컨테이너 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f fino-ai-server
docker compose logs -f celery-worker
```

---

## 4. 서비스 접속 정보

### 4.1 대시보드 URL

| 서비스 | URL | 용도 | 인증 |
|--------|-----|------|------|
| API Server | http://localhost:8001/docs | Swagger UI | - |
| Flower | http://localhost:5555 | Celery 모니터링 | - |
| Neo4j Browser | http://localhost:7474 | 그래프 DB | neo4j / 설정값 |
| RabbitMQ | http://localhost:15672 | 메시지 큐 | guest / guest |
| RedisInsight | http://localhost:5540 | Redis 관리 | - |
| ChromaDB | http://localhost:8000 | 벡터 DB | - |

### 4.2 내부 포트

| 서비스 | 내부 포트 | 외부 포트 |
|--------|----------|----------|
| fino-ai-server | 8001 | 8001 |
| vllm-server | 8000 | 8002 |
| chromadb | 8000 | 8000 |
| neo4j | 7687, 7474 | 7687, 7474 |
| rabbitmq | 5672, 15672 | 5672, 15672 |
| redis | 6379 | 6379 |
| flower | 5555 | 5555 |
| redisinsight | 5540 | 5540 |

---

## 5. 개발 워크플로우

### 5.1 로컬 개발 서버 실행

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt

# FastAPI 서버 실행 (핫 리로드)
uvicorn app.main:app --reload --port 8001
```

### 5.2 Celery Worker 로컬 실행

```bash
# Worker 실행
celery -A app.celery_worker.celery_app worker --loglevel=info -P solo

# Beat 실행 (스케줄러)
celery -A app.celery_worker.celery_app beat --loglevel=info
```

### 5.3 테스트 실행

```bash
# 전체 테스트
pytest tests/ -v

# 특정 테스트 파일
pytest tests/test_api_integration.py -v

# 커버리지 포함
pytest tests/ -v --cov=app --cov-report=html
```

---

## 6. 테스트 데이터

### 6.1 테스트 데이터 주입

```bash
# Neo4j + ChromaDB에 테스트 데이터 추가
docker exec -it fino-ai-server python scripts/seed_data.py
```

### 6.2 데모 리포트 생성

```bash
# 수동 리포트 생성 테스트
docker exec -it fino-ai-server python scripts/generate_demo_report.py
```

### 6.3 Mock API 사용

개발 모드(`ENV_MODE=development`)에서는 Mock API를 사용할 수 있습니다:

```bash
# ChromaDB에 테스트 문서 추가
curl -X POST http://localhost:8001/api/v1/dev/news/mock_chroma \
  -H "Content-Type: application/json" \
  -d '{"title": "테스트 뉴스", "content": "내용..."}'

# Neo4j에 테스트 뉴스 생성
curl -X POST http://localhost:8001/api/v1/dev/news/mock_graph \
  -H "Content-Type: application/json" \
  -d '{"location": "춘천", "category": "경제"}'
```

---

## 7. 트러블슈팅

### 7.1 일반적인 문제

#### 환경 변수 미인식

```
WARN: The "NEO4J_PASSWORD" variable is not set.
```

**해결**:
```bash
# --env-file 옵션 추가
docker compose --env-file .env up -d
```

#### vLLM GPU 오류 (M1 Mac)

```
Error: could not select device driver "nvidia" with capabilities: [[gpu]]
```

**해결**: M1 Mac에서는 vLLM 대신 Ollama 사용 권장

```yaml
# docker-compose.yml에서 vllm-server 대신 Ollama 사용
ollama:
  image: ollama/ollama
  ports:
    - "11434:11434"
```

#### Neo4j 연결 실패

```
ServiceUnavailable: Unable to retrieve routing information
```

**해결**:
```bash
# Neo4j 컨테이너 상태 확인
docker logs fino-ai-server-neo4j-1

# Neo4j 헬스체크 대기 후 재시작
docker compose restart fino-ai-server celery-worker
```

#### Celery Worker 연결 실패

```
[ERROR] Cannot connect to amqp://guest@rabbitmq//
```

**해결**:
```bash
# RabbitMQ 상태 확인
docker logs rabbitmq

# RabbitMQ 재시작
docker compose restart rabbitmq
```

### 7.2 로그 확인

```bash
# 전체 로그
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f fino-ai-server
docker compose logs -f celery-worker
docker compose logs -f neo4j
```

### 7.3 컨테이너 재시작

```bash
# 전체 재시작
docker compose restart

# 특정 서비스 재시작
docker compose restart fino-ai-server celery-worker

# 전체 중지 후 재시작
docker compose down
docker compose --env-file .env up -d
```

### 7.4 볼륨 초기화

```bash
# 주의: 모든 데이터 삭제됨
docker compose down -v
docker compose --env-file .env up -d
```

---

## 8. 유용한 명령어

### 8.1 Docker Compose

```bash
# 상태 확인
docker compose ps
docker compose ps -a  # 중지된 컨테이너 포함

# 로그
docker compose logs -f <service>
docker compose logs --tail=100 <service>

# 실행 중인 컨테이너 접속
docker exec -it fino-ai-server bash
docker exec -it celery-worker bash

# 리소스 사용량
docker stats
```

### 8.2 Neo4j Cypher

```bash
# Neo4j 컨테이너에서 Cypher 실행
docker exec -it fino-ai-server-neo4j-1 cypher-shell -u neo4j -p <password>

# 뉴스 수 확인
MATCH (n:News) RETURN count(n);

# 지역별 뉴스 수
MATCH (l:Location)<-[:IS_IN_LOCATION]-(n:News)
RETURN l.name, count(n)
ORDER BY count(n) DESC;
```

### 8.3 Redis

```bash
# Redis CLI 접속
docker exec -it redis redis-cli

# 키 목록
KEYS *

# Celery Task 결과 확인
GET celery-task-meta-<task-id>
```

---

## 9. M1 Mac 특별 가이드

### 9.1 vLLM 대안: Ollama

```bash
# Ollama 설치 (Mac)
brew install ollama

# Ollama 실행
ollama serve

# Llama 3 모델 다운로드
ollama pull llama3:8b
```

### 9.2 docker-compose.override.yml

```yaml
# docker-compose.override.yml (M1 Mac용)
version: '3.8'

services:
  # vLLM 비활성화
  vllm-server:
    profiles:
      - gpu-only

  # 의존성 수정
  fino-ai-server:
    depends_on:
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_started
      chromadb:
        condition: service_healthy
      neo4j:
        condition: service_healthy
    environment:
      - VLLM_BASE_URL=http://host.docker.internal:11434/v1
```

---

## 관련 문서

- [ARC-001 시스템 아키텍처](./ARC-001_SYSTEM_ARCHITECTURE.md)
- [DEV-001 코딩 컨벤션](./DEV-001_CODING_CONVENTION.md)
- [TRB-001 일반 오류](./TRB-001_COMMON_ERRORS.md)
