import pytest
import logging.config
from app.core.logging_config import get_logging_config
from app.celery_worker import celery_app

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: API-Celery integration tests with mocks")
    config.addinivalue_line("markers", "e2e: End-to-end tests with real async workers")

@pytest.fixture(scope="session", autouse=True)
def setup_celery_for_testing():
    """
    기본적으로 모든 단위 테스트에 동기 모드 적용.
    integration과 e2e 마커가 있는 테스트는 각자 설정을 덮어씁니다.
    """
    celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)
    yield
    
@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """테스트용 로깅 설정"""
    test_config = get_logging_config(log_level="ERROR", env_mode="development")
    # 테스트 중에는 콘솔 출력 최소화
    test_config['loggers']['app']['level'] = 'ERROR'
    logging.config.dictConfig(test_config)