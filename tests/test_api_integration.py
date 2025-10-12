import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import Mock

# 파일의 모든 테스트에 integration 마커 적용
pytestmark = pytest.mark.integration

@pytest.fixture(scope="module", autouse=True)
def setup_celery_eager_mode():
    """API-Celery 통합 테스트: Eager 모드로 Mock 적용"""
    from app.celery_worker import celery_app
    celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)
    yield

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        print("\n--- [Fixture] TestClient started ---")
        yield test_client
    print("\n--- [Fixture] TestClient closed ---")

def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
# 워크플로우 호출 검증 테스트 
def test_manual_report_workflow_dispatch(client: TestClient, mocker):
    """(통합 테스트) 수동 생성 API가 Celery 워크플로우 Task를 올바르게 호출하는지 검증합니다."""
    mock_task = Mock()
    mock_task.id = "mock-task-id-123"
    mock_workflow_task = mocker.patch("app.api.v1.reports.generate_report_workflow.delay", return_value=mock_task)

    # 수동 생성 API를 호출
    request_body = {
        "location": "통합테스트시",
        "start_date": "2025-10-01",
        "end_date": "2025-10-07",
        "report_type": "manual_test"
    }
    generate_url = app.url_path_for('request_manual_report_generation')
    response = client.post(generate_url, json=request_body)

    # API 응답 및 Task 호출 여부를 검증
    assert response.status_code == 202
    assert response.json()["task_id"] == "mock-task-id-123"
    mock_workflow_task.assert_called_once()