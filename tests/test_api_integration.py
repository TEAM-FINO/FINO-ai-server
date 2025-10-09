import pytest
from fastapi.testclient import TestClient
from app.main import app

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

def test_report_generation_with_mocks(client: TestClient, mocker):
    """
    API와 Celery Task 간의 통신 흐름을 테스트합니다.
    내부 로직은 Mock을 사용하여 빠르게 검증합니다.
    """
    # Mock 설정
    mock_news_data = [
        {"news_id": "TEST01", "title": "통합테스트 뉴스 1", "category": "경제"},
        {"news_id": "TEST02", "title": "통합테스트 뉴스 2", "category": "사회"},
    ]
    mocker.patch(
        "app.celery_worker.graph_service.get_all_news_by_location",
        return_value=mock_news_data
    )
    mocker.patch(
        "app.celery_worker.generate_executive_summary",
        return_value="## 헤드라인 브리핑\n[Mocked] 거시적 요약"
    )
    mocker.patch(
        "app.celery_worker.generate_categorical_analysis",
        return_value="### [Mocked] 분야별 분석"
    )
    
    # 리포트 생성 요청
    request_body = {
        "location": "통합테스트시",
        "categories": ["경제", "사회"]
    }
    generate_url = app.url_path_for('request_report_generation')
    response = client.post(generate_url, json=request_body)
    
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    assert task_id is not None
    
    # Eager 모드에서는 즉시 완료됨
    status_url = app.url_path_for('get_report_status', task_id=task_id)
    response = client.get(status_url)
    result = response.json()
    
    # 결과 검증
    assert result["status"] == "COMPLETED"
    assert result["result"]["status"] == "SUCCESS"
    assert "[Mocked] 거시적 요약" in result["result"]["report"]
    assert "[Mocked] 분야별 분석" in result["result"]["report"]
    
    print("\n--- Integration Test (with Mocks) successful! ---")