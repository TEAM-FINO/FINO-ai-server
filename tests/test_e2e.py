import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.graph_service import graph_service
import time

# E2E 테스트 마커
pytestmark = pytest.mark.e2e

@pytest.fixture(scope="module", autouse=True)
def setup_celery_async_mode():
    """E2E 테스트: 실제 비동기 Worker 사용"""
    from app.celery_worker import celery_app
    celery_app.conf.update(task_always_eager=False, task_store_eager_result=False)
    yield

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        print("\n--- [Fixture] E2E TestClient started ---")
        yield test_client
    print("\n--- [Fixture] E2E TestClient closed ---")

@pytest.fixture(scope="module")
def setup_test_data():
    """실제 테스트용 데이터를 DB에 생성"""
    print("\n--- Setting up test data in DB ---")
    
    # 테스트용 뉴스 데이터 생성
    from types import SimpleNamespace
    test_news = [
        SimpleNamespace(
            news_id="E2E_TEST_01",
            title="E2E 테스트 뉴스 1 - 경제",
            location="E2E테스트시",
            category="경제"
        ),
        SimpleNamespace(
            news_id="E2E_TEST_02",
            title="E2E 테스트 뉴스 2 - 사회",
            location="E2E테스트시",
            category="사회"
        ),
    ]
    
    for news in test_news:
        graph_service.create_news_graph_data(news)
    
    yield
    
    # 테스트 데이터 정리
    print("\n--- Cleaning up test data ---")
    for news in test_news:
        graph_service.delete_test_data(news.news_id)

TASK_STATUS_CHECK_MAX_ATTEMPTS = 30
TASK_STATUS_CHECK_INTERVAL_SECONDS = 2

def test_async_report_generation_e2e(client: TestClient, setup_test_data):
    """
    실제 비동기 Worker를 사용한 End-to-End 테스트입니다.
    
    주의: 이 테스트를 실행하려면 실제 Celery Worker가 실행 중이어야 합니다:
    $ celery -A app.celery_worker worker --loglevel=info
    """
    print("\n=== Starting E2E Test with Real Async Worker ===")
    
    # 리포트 생성 요청
    request_body = {
        "location": "E2E테스트시",
        "categories": ["경제", "사회"]
    }
    generate_url = app.url_path_for('request_report_generation')
    response = client.post(generate_url, json=request_body)
    
    assert response.status_code == 202, "생성 요청이 성공적으로 접수되어야 합니다."
    task_id = response.json()["task_id"]
    assert task_id is not None, "Task ID가 반환되어야 합니다."
    print(f"Task ID: {task_id}")
    
    # 비동기 작업 완료 대기
    final_result = None
    for i in range(TASK_STATUS_CHECK_MAX_ATTEMPTS):
        print(f"--> Checking status for task {task_id} (Attempt {i+1}/{TASK_STATUS_CHECK_MAX_ATTEMPTS})")
        status_url = app.url_path_for('get_report_status', task_id=task_id)
        response = client.get(status_url)
        res_json = response.json()
        
        print(f"    Status: {res_json['status']}")
        
        if res_json["status"] == "COMPLETED":
            final_result = res_json
            print("    ✅ Task completed!")
            break
        elif res_json["status"] == "FAILED":
            pytest.fail(f"Task failed: {res_json}")
        
        time.sleep(TASK_STATUS_CHECK_INTERVAL_SECONDS)
    
    # 결과 검증
    assert final_result is not None, \
        f"Task가 {TASK_STATUS_CHECK_MAX_ATTEMPTS * TASK_STATUS_CHECK_INTERVAL_SECONDS}초 내에 완료되지 않았습니다."
    assert final_result["status"] == "COMPLETED", "최종 상태는 'COMPLETED'여야 합니다."
    assert final_result["result"]["status"] == "SUCCESS", "Task 실행이 성공해야 합니다."
    
    # 실제 리포트 생성 확인
    report = final_result["result"]["report"]
    assert len(report) > 0, "리포트가 생성되어야 합니다."
    assert "헤드라인 브리핑" in report or "주요 동향" in report, \
        "리포트에 예상된 섹션이 포함되어야 합니다."
    
    print(f"\n생성된 리포트 (일부):\n{report[:200]}...\n")
    print("\n=== E2E Test successful! ===")