import pytest
from fastapi.testclient import TestClient
from app.main import app
import time

# 파일의 모든 테스트에 integration 마커 적용
pytestmark = pytest.mark.integration

@pytest.fixture(scope="module", autouse=True)
def disable_eager_mode_for_integration():
    """통합 테스트에서는 실제 비동기 모드를 사용합니다."""
    from app.celery_worker import celery_app
    celery_app.conf.update(task_always_eager=False, task_store_eager_result=False)
    yield

DB_INDEXING_WAIT_SECONDS = 3
TASK_STATUS_CHECK_MAX_ATTEMPTS = 25
TASK_STATUS_CHECK_INTERVAL_SECONDS = 1

@pytest.fixture(scope="module")
def client():
    """
    애플리케이션의 lifespan을 포함하여 테스트 클라이언트를 생성하는 Fixture.
    scope="module"이므로, 이 파일의 테스트들이 실행되기 전 딱 한번만 실행됩니다.
    """
    with TestClient(app) as test_client:
        print("\n--- [Fixture] TestClient started, lifespan startup event triggered ---")
        yield test_client
    print("\n--- [Fixture] TestClient closed, lifespan shutdown event triggered ---")


@pytest.fixture(scope="function")
def provide_mock_news():
    """테스트에 사용할 Mock 뉴스 데이터만 제공하는 Fixture."""
    return {
        "news_id": f"test_fixture_{int(time.time())}", # 매번 고유 ID 생성
        "press": "픽스처일보", "title": "픽스처 도시, 테스트 허브로 도약",
        "content": "픽스처 도시는 최근 테스트 자동화에 성공하며 미래 성장 동력을 확보했다.",
        "location": "픽스처시", "category": "TEST"
    }
    
def test_health_check(client: TestClient): # client fixture를 인자로 받습니다.
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_full_rag_pipeline(client: TestClient):
    # Fixture 대신, 테스트 함수가 직접 데이터 생성과 정리를 책임집니다.
    test_news_id = f"test_api_{int(time.time())}"
    mock_news = {
        "news_id": test_news_id, "press": "API테스트일보", "title": "API 테스트 도시, E2E 허브로 도약",
        "content": "API 테스트 도시는 최근 E2E 테스트 자동화에 성공하며 미래 성장 동력을 확보했다.",
        "location": "API테스트시", "category": "API-TEST"
    }
    
    try:
        # --- SETUP ---
        print("\n--- [API Test Setup] Creating test data ---")
        url_chroma = app.url_path_for('add_mock_news_to_chroma')
        url_graph = app.url_path_for('add_mock_news_to_neo4j')
        client.post(url_chroma, json=mock_news).raise_for_status()
        client.post(url_graph, json=mock_news).raise_for_status()
        time.sleep(DB_INDEXING_WAIT_SECONDS)

        # --- TEST EXECUTION ---
        query = {
            "query": f"{mock_news['location']}의 {mock_news['category']} 산업에 대한 소식",
            "location": mock_news['location'],
            "category": mock_news['category']
        }
        generate_url = app.url_path_for('request_report_generation')
        response = client.post(generate_url, json=query)
        assert response.status_code == 202
        task_id = response.json()["task_id"]

        final_result = None
        for _ in range(TASK_STATUS_CHECK_MAX_ATTEMPTS):
            status_url = app.url_path_for('get_report_status', task_id=task_id)
            response = client.get(status_url)
            res_json = response.json()
            if res_json["status"] == "COMPLETED":
                final_result = res_json
                break
            time.sleep(TASK_STATUS_CHECK_INTERVAL_SECONDS)

        # --- ASSERTION ---
        assert final_result is not None, "Task did not complete in time"
        assert final_result["status"] == "COMPLETED"
        assert final_result["result"]["status"] == "SUCCESS"
        report_text = final_result["result"]["report"]
        assert any(keyword in report_text for keyword in ["성공", "도약", "확보", "자동화"])
        
    finally:
        # --- TEARDOWN ---
        print(f"\n--- [API Test Teardown] Cleaning up test data: {test_news_id} ---")
        cleanup_url = app.url_path_for('cleanup_test_news', news_id=test_news_id)
        client.delete(cleanup_url)
