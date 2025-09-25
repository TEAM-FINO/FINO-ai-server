import pytest
from app.celery_worker import celery_app

def pytest_configure(config):
    # integration 마커를 pytest에 공식적으로 등록
    config.addinivalue_line("markers", "integration: mark test as integration test")

@pytest.fixture(scope="session", autouse=True)
def setup_celery_for_testing(request):
    """
    'integration' 마커가 없는 테스트에만 Celery 동기 모드를 적용합니다.
    """
    if "integration" in request.keywords:
        # 통합 테스트에서는 아무 설정도 하지 않음 (실제 비동기 모드 사용)
        yield
    else:
        # 단위 테스트에서는 동기 모드(eager) 사용
        celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)
        yield