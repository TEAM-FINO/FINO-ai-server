import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def check_all_services() -> Dict[str, Any]:
    """
    모든 의존 서비스의 상태를 확인합니다.
    
    Returns:
        서비스별 상태를 담은 딕셔너리
    """
    from app.services.graph_service import graph_service
    from app.services.vectorstore_service import collection
    from app.celery_worker import celery_app
    
    health_status = {
        "neo4j": "unknown",
        "chromadb": "unknown",
        "celery": "unknown",
    }
    
    # === Neo4j 체크 ===
    try:
        if graph_service.health_check():
            health_status["neo4j"] = "healthy"
        else:
            health_status["neo4j"] = "unhealthy"
    except Exception as e:
        health_status["neo4j"] = "unhealthy"
        health_status["neo4j_error"] = str(e)
        logger.error(f"Neo4j health check failed: {e}")
    
    # === ChromaDB 체크 ===
    try:
        collection.count()
        health_status["chromadb"] = "healthy"
    except Exception as e:
        health_status["chromadb"] = "unhealthy"
        health_status["chromadb_error"] = str(e)
        logger.error(f"ChromaDB health check failed: {e}")
    
    # === Celery 체크 ===
    try:
        inspect = celery_app.control.inspect()
        ping_response = inspect.ping()
        
        if ping_response and isinstance(ping_response, dict):
            health_status["celery"] = "healthy"
            health_status["celery_workers"] = list(ping_response.keys())
        else:
            health_status["celery"] = "unhealthy"
            health_status["celery_error"] = "No workers responding"
    except Exception as e:
        health_status["celery"] = "unhealthy"
        health_status["celery_error"] = str(e)
        logger.error(f"Celery health check failed: {e}")
    
    # === 전체 상태 판단 ===
    critical_services = ["neo4j", "chromadb", "celery"]
    all_healthy = all(
        health_status.get(service) == "healthy" 
        for service in critical_services
    )
    health_status["overall"] = "healthy" if all_healthy else "degraded"
    
    return health_status