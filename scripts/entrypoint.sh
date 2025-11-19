#!/bin/sh
set -e

echo "=========================================="
echo "FINO AI - Entrypoint Script"
echo "Container Type: ${CONTAINER_TYPE:-unknown}"
echo "=========================================="

# api 컨테이너에서만 인덱스 생성
if [ "$CONTAINER_TYPE" = "api" ]; then
    echo "Creating Neo4j indexes (if not exist)..."
    
    # Neo4j 연결 대기 (최대 30초)
    MAX_RETRIES=30
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if python scripts/create_neo4j_indexes.py 2>/dev/null; then
            echo "Neo4j indexes check completed successfully."
            break
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Waiting for Neo4j... (attempt $RETRY_COUNT/$MAX_RETRIES)"
                sleep 1
            else
                echo "WARNING: Failed to create indexes after $MAX_RETRIES attempts."
                echo "Application will start anyway. Please check Neo4j connection."
            fi
        fi
    done
else
    echo "Skipping index creation for container type: $CONTAINER_TYPE"
fi

echo "Starting main process: $*"
echo "=========================================="

exec "$@"