# FINO AI Server
FINO 프로젝트의 AI 분석 및 리포트 생성 마이크로서비스입니다.

<br>

## 역할
- 지역 뉴스를 AI로 분석하여, **'전체 동향 요약'**과 **'분야별 심층 분석'**으로 구성된 맞춤형 리포트를 생성합니다.
- 모든 리포트 생성 과정은 Celery를 통해 안정적으로 비동기 처리됩니다.

<br>

## 기술 스택
- **Framework**: FastAPI
- **AI/ML**: LangChain, vLLM, SentenceTransformers
- **Databases**: Neo4j, ChromaDB
- **Async Tasks & Tools**: Celery, RabbitMQ, Redis, RedisInsight
- **Containerization**: Docker, Docker Compose

<br>

## 주요 엔드포인트 및 관리 도구
- **API 문서 (Swagger UI)**: `http://localhost:8001/docs`
- **Celery 모니터링 (Flower)**: `http://localhost:5555`
- **Vector DB (ChromaDB API)**: `http://localhost:8000`
- **Graph DB (Neo4j Browser)**: `http://localhost:7474` (ID: `neo4j`, PW: `.env` 파일에 설정)
- **Message Queue (RabbitMQ UI)**: `http://localhost:15672` (ID/PW: `guest`)
- **Key-Value DB (RedisInsight)**: `http://localhost:5540`

<br>

## 실행 방법

### 1. 사전 준비
- Docker Desktop 설치
- NVIDIA GPU 및 드라이버, NVIDIA Container Toolkit 설치

### 2. 환경 변수 설정
프로젝트 루트에 `.env` 파일을 생성하고 내용을 채워주세요.

### 3. 서비스 실행
프로젝트 루트 디렉토리에서 아래 명령어를 실행하세요.
```bash
docker-compose up --build -d
```

### 테스트 방법
컨테이너 내부에서 아래 명령어를 실행하여 테스트를 수행할 수 있습니다.
```bash
docker exec -it fino-ai-server bash
pytest
```