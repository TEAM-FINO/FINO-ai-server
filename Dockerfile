# ===== Stage 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /app

# 시스템 의존성 설치 
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지를 /opt/venv에 가상환경으로 설치
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 모델 다운로드 스크립트 복사 및 실행
COPY scripts/download_model.py scripts/download_model.py
ENV HF_HOME=/app/cache
RUN python scripts/download_model.py


# ===== Stage 2: Runtime =====
FROM python:3.11-slim AS runtime

WORKDIR /app

# Health check용 curl 설치
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p /var/run/celery
RUN mkdir -p /var/log/fino-ai

# Builder에서 가상환경 복사
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 모델 캐시 복사
COPY --from=builder /app/cache /app/cache

# 애플리케이션 소스 코드 복사
COPY . .

# 환경변수 설정
ENV HF_HOME=/app/cache

# 권한 설정
RUN chown -R appuser:appuser /app && \
    chown -R appuser:appuser /var/run/celery && \
    chown -R appuser:appuser /app/cache && \
    chown -R appuser:appuser /var/log/fino-ai

USER appuser

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]