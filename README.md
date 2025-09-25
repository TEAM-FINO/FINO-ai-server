# FINO AI Server
FINO 프로젝트의 AI 분석 및 리포트 생성 마이크로서비스입니다.

## 역할
- Neo4j, ChromaDB, LLM(Llama 3)을 활용한 다단계 RAG 파이프라인을 통해 개인화된 뉴스 리포트를 생성합니다.
- 모든 작업은 Celery를 통해 비동기적으로 처리됩니다.

## 기술 스택
- **Framework**: FastAPI
- **AI/ML**: LangChain, vLLM, SentenceTransformers
- **Databases**: Neo4j, ChromaDB
- **Async Tasks**: Celery, RabbitMQ, Redis
- **Containerization**: Docker, Docker Compose

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

### 주요 엔드포인트
API 문서 (Swagger UI): http://localhost:8001/docs
Celery 모니터링 (Flower): http://localhost:5555

### 테스트 방법
컨테이너 내부에서 아래 명령어를 실행하여 테스트를 수행할 수 있습니다.
```bash
docker exec -it fino-ai-server bash
pytest
```