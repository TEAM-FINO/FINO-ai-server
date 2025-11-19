import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.graph_service import graph_service
from unittest.mock import patch
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
    
@pytest.fixture(scope="module", autouse=True)
def mock_fino_api():
    """FINO 서버 API 호출을 Mock 처리합니다 (unittest.mock 사용)."""
    print("\n--- Mocking FINO API ---")
    with patch("app.services.fino_api_service.fino_api_service.send_report") as mock_send:
        # Mock 응답 설정
        mock_send.return_value = (True, {"status": "ok", "message": "Report received"})
        yield mock_send
        print(f"\n--- FINO API called {mock_send.call_count} times ---")

# 테스트 데이터 생성 Fixture 
@pytest.fixture(scope="module")
def setup_test_data():
    """실제 테스트용 데이터를 DB에 생성"""
    print("\n--- Setting up E2E test data in DB ---")
    
    # 테스트 실행 시점을 기준으로 상대 날짜 생성
    now = datetime.now()
    today = now.replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    
    # 테스트용 뉴스 데이터 생성
    from types import SimpleNamespace
    test_news = [
        SimpleNamespace(
            news_id="E2E_01_TWO_DAYS_AGO",
            title="E2E 경제 뉴스 (이틀 전)",
            location="E2E테스트시",
            category="경제",
            pubDate=two_days_ago.strftime('%a, %d %b %Y %H:%M:%S +0900'),
            content="이틀 전 발생한 경제 관련 뉴스 내용입니다."
        ),
        SimpleNamespace(
            news_id="E2E_02_YESTERDAY",
            title="E2E 사회 뉴스 (어제)",
            location="E2E테스트시",
            category="사회",
            pubDate=yesterday.strftime('%a, %d %b %Y %H:%M:%S +0900'),
            content="어제 발생한 사회 관련 뉴스 내용입니다."
        ),
        SimpleNamespace(
            news_id="E2E_03_TODAY",
            title="E2E 문화 뉴스 (오늘)",
            location="E2E테스트시",
            category="문화",
            pubDate=today.strftime('%a, %d %b %Y %H:%M:%S +0900'),
            content="오늘 발생한 문화 관련 뉴스 내용입니다."
        ),
    ]
    
    for news in test_news:
        try:
            graph_service.create_news_graph_data(news)
            print(f"✓ Created test news: {news.news_id}")
        except Exception as e:
            print(f"✗ Failed to create news {news.news_id}: {e}")
    
    yield
    
    # 테스트 데이터 정리
    print("\n--- Cleaning up E2E test data ---")
    for news in test_news:
        try:
            graph_service.delete_test_data(news.news_id)
            print(f"✓ Deleted test news: {news.news_id}")
        except Exception as e:
            print(f"✗ Failed to delete news {news.news_id}: {e}")


DISPATCH_CHECK_MAX_ATTEMPTS = 30  # 최대 1분 대기
WORKFLOW_CHECK_MAX_ATTEMPTS = 90  # 최대 3분 대기
CHECK_INTERVAL_SECONDS = 2

# E2E 테스트 함수
def test_async_report_generation_e2e(client: TestClient, setup_test_data):
    """실제 비동기 Worker를 사용하여, 지정된 기간의 리포트가 생성되는지 검증합니다."""
    print("\n=== Starting E2E Test with Real Async Worker ===")
    
    today = datetime.now()
    yesterday = (today - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    four_days_ago = yesterday - timedelta(days=3)
    
    request_body = {
        "location": "E2E테스트시",
        "start_date": four_days_ago.strftime('%Y-%m-%d'),
        "end_date": yesterday.strftime('%Y-%m-%d'),
        "report_type": "e2e_test"
    }
    print(f"Request body: {request_body}")
    
    # 리포트 생성 요청
    generate_url = app.url_path_for('request_manual_report_generation')
    response = client.post(generate_url, json=request_body)
    
    # 디버깅 정보 
    if response.status_code != 202:
        print(f"❌ Unexpected status code: {response.status_code}")
        print(f"Response: {response.json()}")
        pytest.fail(f"Request failed with {response.status_code}: {response.json()}")
    
    assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
    
    initial_result = response.json()
    print(f"Initial response: {initial_result}")
    
    # 워크플로우 Dispatch Task ID 확인
    dispatch_task_id = initial_result["task_id"]
    assert dispatch_task_id is not None, "Task ID가 반환되어야 합니다."
    print(f"Dispatch Task ID: {dispatch_task_id}")
    
    # 비동기 모드에서는 status가 "WORKFLOW_DISPATCHED"
    assert initial_result["status"] in ["WORKFLOW_DISPATCHED", "WORKFLOW_STARTED"]

    # Dispatch Task 완료 대기 (WORKFLOW_STARTED 상태 확인)
    workflow_task_id = None
    for i in range(DISPATCH_CHECK_MAX_ATTEMPTS):
        status_url = app.url_path_for('get_report_status', task_id=dispatch_task_id)
        response = client.get(status_url)
        res_json = response.json()
        
        status = res_json.get("status")
        result = res_json.get("result")
        
        print(f"    [Dispatch Check {i+1}/{DISPATCH_CHECK_MAX_ATTEMPTS}] Status: {status}")
        
        # 상세 디버깅
        if result:
            print(f"        Result keys: {list(result.keys())}")
            if "workflow_task_id" in result:
                print(f"        Workflow Task ID: {result.get('workflow_task_id')}")
        
        # COMPLETED 상태이고 WORKFLOW_STARTED인 경우
        if status == "COMPLETED" and result:
            if result.get("status") == "WORKFLOW_STARTED":
                workflow_task_id = result.get("workflow_task_id")
                if workflow_task_id:
                    print(f"✓ Workflow dispatched successfully. Chain ID: {workflow_task_id}")
                    break
        
        # PROCESSING 상태인 경우에도 workflow_task_id가 있는지 확인
        elif status == "PROCESSING" and result:
            workflow_task_id = result.get("workflow_task_id")
            if workflow_task_id:
                print(f"✓ Found workflow_task_id in PROCESSING state: {workflow_task_id}")
                break
        
        # FAILED 상태
        elif status == "FAILED":
            print(f"❌ Dispatch task failed: {res_json}")
            pytest.fail(f"Dispatch task failed: {res_json}")
        
        # SKIPPED 상태 (뉴스 데이터 없음)
        elif status == "SKIPPED":
            print(f"⚠️  Workflow skipped: {result.get('reason', 'Unknown reason')}")
            pytest.skip(f"Workflow skipped: {result.get('reason')}")
        
        time.sleep(CHECK_INTERVAL_SECONDS)
    
    # workflow_task_id 확인
    if workflow_task_id is None:
        print("\n❌ Failed to get workflow_task_id within timeout")
        print(f"Last status response: {res_json}")
        pytest.fail(
            f"Workflow task ID was not returned within "
            f"{DISPATCH_CHECK_MAX_ATTEMPTS * CHECK_INTERVAL_SECONDS} seconds"
        )
    
    # 실제 워크플로우 완료 대기
    print(f"\n=== Waiting for workflow completion (Task ID: {workflow_task_id}) ===")
    final_result = None
    
    for i in range(WORKFLOW_CHECK_MAX_ATTEMPTS):
        status_url = app.url_path_for('get_report_status', task_id=workflow_task_id)
        response = client.get(status_url)
        res_json = response.json()
        
        status = res_json.get("status")
        print(f"    [Workflow Check {i+1}/{WORKFLOW_CHECK_MAX_ATTEMPTS}] Status: {status}")
        
        if status == "COMPLETED":
            final_result = res_json.get("result")
            print("✅ Full workflow completed!")
            break
        
        elif status == "FAILED":
            print(f"❌ Workflow failed: {res_json}")
            error_result = res_json.get("result", {})
            print(f"    Error: {error_result.get('error', 'Unknown error')}")
            pytest.fail(f"Workflow failed: {res_json}")
        
        elif status in ["PROCESSING", "STARTED", "PENDING", "RETRY"]:
            # 계속 대기
            pass
        
        else:
            print(f"⚠️  Unexpected status: {status}")
        
        time.sleep(CHECK_INTERVAL_SECONDS)
    
    # 결과 검증 
    if final_result is None:
        print(f"\n❌ Workflow did not complete within timeout")
        print(f"Last status response: {res_json}")
        pytest.fail(
            f"워크플로우가 {WORKFLOW_CHECK_MAX_ATTEMPTS * CHECK_INTERVAL_SECONDS}초 "
            "내에 완료되지 않았습니다."
        )
    
    # 최종 결과 상태 확인
    print(f"\n=== Validating Results ===")
    print(f"Final result keys: {list(final_result.keys())}")
    
    assert final_result.get("status") == "SUCCESS", (
        f"Expected SUCCESS, got {final_result.get('status')}"
    )
    assert final_result.get("location") == "E2E테스트시"
    
    # 리포트 내용 검증
    assert "categories_analyzed" in final_result, "categories_analyzed field missing"
    assert final_result["categories_analyzed"] > 0, "No categories were analyzed"
    
    # FINO API 호출 검증
    assert mock_fino_api.call_count == 1, f"Expected 1 FINO API call, got {mock_fino_api.call_count}"
    
    # 전송된 리포트 데이터 검증
    sent_report = mock_fino_api.call_args[0][0]
    assert sent_report["location"] == "E2E테스트시"
    assert sent_report["report_type"] == "e2e_test"
    assert "executive_summary" in sent_report
    assert "categorical_analysis" in sent_report
    assert len(sent_report["categorical_analysis"]) == 3  # 경제, 사회, 문화
    
    print(f"\n✅ E2E Test successful!")
    print(f"   - Location: {final_result['location']}")
    print(f"   - Report Type: {final_result['report_type']}")
    print(f"   - Categories Analyzed: {final_result['categories_analyzed']}")
    print(f"   - Report Quality: {final_result.get('report_quality', 'N/A')}")
    print(f"   - FINO API called: {mock_fino_api.call_count} time(s)")