import pytest
from app.celery_worker import celery_app

def pytest_configure(config):
    # integration 마커를 pytest에 공식적으로 등록
    config.addinivalue_line("markers", "integration: mark test as integration test")

@pytest.fixture(scope="session", autouse=True)
def setup_celery_for_testing():
    """
    단위 테스트를 위해 Celery를 동기 모드로 설정합니다.
    통합 테스트(integration 마커)가 있는 파일은 별도로 설정을 덮어씁니다.
    """
    # 기본적으로 모든 테스트에 동기 모드 적용
    celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)
    yield