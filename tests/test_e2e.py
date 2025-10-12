import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.graph_service import graph_service
import time
from datetime import datetime, timedelta

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

# 테스트 데이터 생성 Fixture 
@pytest.fixture(scope="module")
def setup_test_data():
    """실제 테스트용 데이터를 DB에 생성"""
    print("\n--- Setting up E2E test data in DB ---")
    
    # 테스트 실행 시점을 기준으로 상대 날짜 생성
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    # 테스트용 뉴스 데이터 생성
    from types import SimpleNamespace
    test_news = [
        SimpleNamespace(
            news_id="E2E_01_TODAY",
            title="E2E 경제 뉴스 (오늘)",
            location="E2E테스트시",
            category="경제",
            pubDate=today.strftime('%a, %d %b %Y %H:%M:%S +0900'),
            content="오늘 발생한 경제 관련 뉴스 내용입니다."
        ),
        SimpleNamespace(
            news_id="E2E_02_YESTERDAY",
            title="E2E 사회 뉴스 (어제)",
            location="E2E테스트시",
            category="사회",
            pubDate=yesterday.strftime('%a, %d %b %Y %H:%M:%S +0900'),
            content="어제 발생한 사회 관련 뉴스 내용입니다."
        ),
    ]
    
    for news in test_news:
        graph_service.create_news_graph_data(news)
    
    yield
    
    # 테스트 데이터 정리
    print("\n--- Cleaning up E2E test data ---")
    for news in test_news:
        graph_service.delete_test_data(news.news_id)

TASK_STATUS_CHECK_MAX_ATTEMPTS = 60
TASK_STATUS_CHECK_INTERVAL_SECONDS = 2

# E2E 테스트 함수
def test_async_report_generation_e2e(client: TestClient, setup_test_data):
    """실제 비동기 Worker를 사용하여, 지정된 기간의 리포트가 생성되는지 검증합니다."""
    print("\n=== Starting E2E Test with Real Async Worker ===")
    
    today = datetime.now()
    two_days_ago = today - timedelta(days=2)
    
    # 리포트 생성 요청
    request_body = {
        "location": "E2E테스트시",
        "start_date": two_days_ago.strftime('%Y-%m-%d'), # 최근 이틀치 데이터를 포함하는 기간
        "end_date": today.strftime('%Y-%m-%d'),
        "report_type": "e2e_test"
    }
    generate_url = app.url_path_for('request_manual_report_generation')
    response = client.post(generate_url, json=request_body)
    
    assert response.status_code == 202
    initial_result = response.json()
    assert initial_result["status"] == "WORKFLOW_STARTED"
    workflow_task_id = initial_result.get("workflow_task_id")
    assert workflow_task_id is not None, "Workflow Task ID가 반환되어야 합니다."
    print(f"Workflow Task ID: {workflow_task_id}")
    
    # 비동기 작업 완료 대기
    final_result = None
    for i in range(TASK_STATUS_CHECK_MAX_ATTEMPTS):
        status_url = app.url_path_for('get_report_status', task_id=workflow_task_id)
        response = client.get(status_url)
        res_json = response.json()
        
        print(f"    Workflow Status: {res_json['status']}")
        
        if res_json["status"] == "COMPLETED":
            final_result = res_json["result"]
            print("✅ Full workflow completed!")
            break
        elif res_json["status"] == "FAILED":
            pytest.fail(f"Task failed: {res_json}")
        
        time.sleep(TASK_STATUS_CHECK_INTERVAL_SECONDS)
    
    # 결과 검증
    assert final_result is not None, "워크플로우가 제한 시간 내에 완료되지 않았습니다."
    assert final_result["status"] == "SUCCESS"
    report = final_result.get("report")
    assert report is not None
    assert report["location"] == "E2E테스트시"
    assert "executive_summary" in report
    assert len(report["categorical_analysis"]) > 0

    print("\n=== E2E Test (Full Workflow) successful! ===")