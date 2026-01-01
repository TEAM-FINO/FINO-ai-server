FROM python:3.13-slim-bookworm AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/download_model.py scripts/download_model.py
ENV HF_HOME=/app/cache
RUN python scripts/download_model.py



FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

RUN mkdir -p /var/run/celery && \
    mkdir -p /var/log/fino-ai && \
    mkdir -p /app/cache

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=builder /app/cache /app/cache

COPY --chown=root:root . .

RUN chmod +x /app/scripts/entrypoint.sh && \
    chmod +x /app/scripts/download_model.py && \
    chmod +x /app/scripts/create_neo4j_indexes.py && \
    chmod -R 555 /app/app /app/scripts

RUN chown -R appuser:appuser /var/run/celery && \
    chown -R appuser:appuser /var/log/fino-ai && \
    chown -R appuser:appuser /app/cache

ENV HF_HOME=/app/cache

USER appuser

EXPOSE 8001

ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]