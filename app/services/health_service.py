import logging
from typing import Dict, Any
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

# 타임아웃 예외
class TimeoutError(Exception):
    """타임아웃 발생 시 발생하는 예외"""
    pass

# 스레드 안전 타임아웃 함수
def run_with_timeout(func, timeout_seconds: int, *args, **kwargs):
    """
    함수를 타임아웃과 함께 실행합니다 (스레드 안전).
    
    Args:
        func: 실행할 함수
        timeout_seconds: 타임아웃 시간 (초)
        *args, **kwargs: func에 전달할 인자
    
    Returns:
        함수 실행 결과
    
    Raises:
        TimeoutError: 타임아웃 초과 시
        Exception: func 실행 중 발생한 예외
    """
    result = [None]  # 결과를 저장할 mutable 객체
    exception = [None]  # 예외를 저장할 mutable 객체
    
    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        # 타임아웃 발생 (스레드는 계속 실행 중)
        raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
    
    if exception[0]:
        # 함수 실행 중 예외 발생
        raise exception[0]
    
    return result[0]


# 개별 서비스 Health Check 함수들
def check_neo4j(timeout_seconds: int = 5) -> Dict[str, Any]:
    """
    Neo4j 연결 상태를 확인합니다.
    
    Returns:
        {"status": "healthy|unhealthy|timeout", "error": "...", "response_time_ms": 123}
    """
    from app.services.graph_service import graph_service
    
    start_time = datetime.now()
    result = {"service": "neo4j", "status": "unknown"}
    
    try:
        # 타임아웃과 함께 health_check 실행
        is_healthy = run_with_timeout(
            graph_service.health_check,
            timeout_seconds
        )
        
        if is_healthy:
            result["status"] = "healthy"
        else:
            result["status"] = "unhealthy"
            result["error"] = "Connection check failed"
    
    except TimeoutError as e:
        result["status"] = "timeout"
        result["error"] = str(e)
        logger.error(f"Neo4j health check timed out after {timeout_seconds}s")
    
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
        logger.error(f"Neo4j health check failed: {e}", exc_info=True)
    
    finally:
        # 응답 시간 측정 (밀리초)
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        result["response_time_ms"] = round(elapsed, 2)
    
    return result


def check_chromadb(timeout_seconds: int = 5) -> Dict[str, Any]:
    """ChromaDB 연결 상태를 확인합니다."""
    from app.services.vectorstore_service import collection
    
    start_time = datetime.now()
    result = {"service": "chromadb", "status": "unknown"}
    
    try:
        # 타임아웃과 함께 count 실행
        count = run_with_timeout(
            collection.count,
            timeout_seconds
        )
        
        result["status"] = "healthy"
        result["document_count"] = count
    
    except TimeoutError as e:
        result["status"] = "timeout"
        result["error"] = str(e)
        logger.error(f"ChromaDB health check timed out after {timeout_seconds}s")
    
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
        logger.error(f"ChromaDB health check failed: {e}", exc_info=True)
    
    finally:
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        result["response_time_ms"] = round(elapsed, 2)
    
    return result


def check_celery(timeout_seconds: int = 5) -> Dict[str, Any]:
    """Celery Worker 상태를 확인합니다."""
    from app.celery_worker import celery_app
    
    start_time = datetime.now()
    result = {"service": "celery", "status": "unknown"}
    
    def _ping_workers():
        """Celery Worker에 ping을 보냅니다."""
        inspect = celery_app.control.inspect()
        return inspect.ping()
    
    try:
        # 타임아웃과 함께 ping 실행
        ping_response = run_with_timeout(
            _ping_workers,
            timeout_seconds
        )
        
        if ping_response and isinstance(ping_response, dict):
            result["status"] = "healthy"
            result["active_workers"] = list(ping_response.keys())
            result["worker_count"] = len(ping_response)
        else:
            result["status"] = "unhealthy"
            result["error"] = "No workers responding to ping"
    
    except TimeoutError as e:
        result["status"] = "timeout"
        result["error"] = str(e)
        logger.error(f"Celery health check timed out after {timeout_seconds}s")
    
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
        logger.error(f"Celery health check failed: {e}", exc_info=True)
    
    finally:
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        result["response_time_ms"] = round(elapsed, 2)
    
    return result


def check_redis(timeout_seconds: int = 3) -> Dict[str, Any]:
    """Redis 연결 상태를 확인합니다."""
    import redis
    from app.core.config import settings
    
    start_time = datetime.now()
    result = {"service": "redis", "status": "unknown"}
    
    def _ping_redis():
        """Redis에 ping을 보냅니다."""
        redis_client = redis.from_url(settings.CELERY_RESULT_BACKEND)
        redis_client.ping()
        return True
    
    try:
        # 타임아웃과 함께 ping 실행
        run_with_timeout(_ping_redis, timeout_seconds)
        result["status"] = "healthy"
    
    except TimeoutError as e:
        result["status"] = "timeout"
        result["error"] = str(e)
        logger.error(f"Redis health check timed out after {timeout_seconds}s")
    
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
        logger.error(f"Redis health check failed: {e}", exc_info=True)
    
    finally:
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        result["response_time_ms"] = round(elapsed, 2)
    
    return result

# 통합 Health Check
def check_all_services(include_optional: bool = False) -> Dict[str, Any]:
    """
    모든 의존 서비스의 상태를 확인합니다.
    
    Args:
        include_optional: Redis 등 선택적 서비스도 포함할지 여부
    
    Returns:
        서비스별 상태를 담은 딕셔너리
    """
    health_checks = {
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # 필수 서비스 체크
    critical_services = ["neo4j", "chromadb", "celery"]
    
    health_checks["checks"]["neo4j"] = check_neo4j()
    health_checks["checks"]["chromadb"] = check_chromadb()
    health_checks["checks"]["celery"] = check_celery()
    
    # 선택적 서비스 체크
    if include_optional:
        health_checks["checks"]["redis"] = check_redis()
        critical_services.append("redis")
    
    # 전체 상태 판단
    all_healthy = all(
        health_checks["checks"][service]["status"] == "healthy"
        for service in critical_services
    )
    
    health_checks["overall_status"] = "healthy" if all_healthy else "degraded"
    
    # 응답 시간 통계
    response_times = [
        check["response_time_ms"] 
        for check in health_checks["checks"].values() 
        if "response_time_ms" in check
    ]
    
    if response_times:
        health_checks["metrics"] = {
            "avg_response_time_ms": round(sum(response_times) / len(response_times), 2),
            "max_response_time_ms": max(response_times),
            "total_checks": len(response_times)
        }
    
    return health_checks