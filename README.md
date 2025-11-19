# FINO AI Server
FINO 프로젝트의 AI 분석 및 리포트 생성 마이크로서비스입니다.

<br>

## 역할
- 지역 뉴스를 AI로 분석하여, '**전체 동향 요약**'과 '**분야별 심층 분석**'으로 구성된 맞춤형 리포트를 생성합니다.
- 모든 리포트 생성 과정은 Celery를 통해 안정적으로 비동기 처리됩니다.

<br>

## 아키텍처 개요
- **워크플로우 기반 자동 생성**: `Celery Beat`가 주기적으로 **리포트 생성 워크플로우(Workflow)** 를 실행합니다.
- **동적 대상 선정**: 워크플로우의 첫 단계에서, `Neo4j` DB에 등록된 모든 서비스 지역 목록을 동적으로 조회합니다.
- **분산형 AI 분석**: 각 지역별로 AI 분석 Task가 개별적으로 실행됩니다.
    1. **'지역 전체 핵심 이슈 분석'** Task가 먼저 실행됩니다.
    2. **'분야별 심층 분석'** Task들이 각 카테고리별로 **병렬 실행**되어 안정성과 속도를 높입니다. (실패 시 개별 재시도)
    3. 모든 분석이 완료되면, **'최종 조립'** Task가 결과물들을 하나의 구조화된 JSON 리포트로 완성합니다.

<br>

## 기술 스택
- **Framework**: FastAPI
- **AI/ML**: LangChain, vLLM, SentenceTransformers
- **Databases**: Neo4j, ChromaDB
- **Async Tasks**: Celery, RabbitMQ, Redis
- **Containerization**: Docker, Docker Compose

<br>

## 주요 엔드포인트 및 관리 도구

### API & Health Checks
- **API 문서 (Swagger UI)**: `http://localhost:8001/docs`
- **Liveness Probe**: `http://localhost:8001/health` (컨테이너 생존 확인)
- **Readiness Probe**: `http://localhost:8001/health/ready` (DB/Broker 연결 상태 등 서비스 준비 완료 확인)

### 관리 도구
- **Celery 모니터링 (Flower)**: `http://localhost:5555`
- **Graph DB (Neo4j Browser)**: `http://localhost:7474` 
- **Message Queue (RabbitMQ UI)**: `http://localhost:15672` (ID/PW: `guest`)
- **Key-Value DB (RedisInsight)**: `http://localhost:5540`

<br>

## 실행 방법

### 1. 사전 준비
- Docker Desktop 설치
- NVIDIA GPU 및 드라이버, NVIDIA Container Toolkit 설치 (GPU 사용 시)

### 2. 환경 변수 설정
프로젝트 루트에 `.env` 파일을 생성하고 내용을 채워주세요.

### 3. 서비스 실행
프로젝트 루트 디렉토리에서 아래 명령어를 실행하세요.
```bash
docker-compose up --build -d
```
**참고:** 컨테이너 시작 시 entrypoint.sh가 자동으로 Neo4j 필수 인덱스를 생성합니다.

### 4. 테스트 및 검증
**자동화 테스트 (Unit/Integration/E2E)**
```bash
docker exec -it fino-ai-server pytest
```

**수동 데모 리포트 생성** 실제 뉴스 데이터를 주입하고 전체 파이프라인을 검증합니다.
```bash
# 1. 테스트 데이터(Mock News) 주입
docker exec -it fino-ai-server python scripts/seed_data.py

# 2. 데모 리포트 생성 요청 및 결과 확인
docker exec -it fino-ai-server python scripts/generate_demo_report.py
```
