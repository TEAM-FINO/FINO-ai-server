import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.graph_service import graph_service
from app.services.vectorstore_service import delete_test_data as delete_vector_data
import time

# 파일의 모든 테스트에 integration 마커 적용
pytestmark = pytest.mark.integration

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
def setup_and_teardown_db(client: TestClient): # client fixture를 인자로 받습니다.
    """
    각 테스트 함수 실행 전 Mock 데이터를 주입하고,
    실행 후에는 주입한 데이터를 삭제하는 Fixture.
    """
    print("\n--- [Setup] Creating test data ---")
    test_news_id = "test_fixture_001"
    mock_news = {
        "news_id": test_news_id, "press": "픽스처일보", "title": "픽스처 도시, 테스트 허브로 도약",
        "content": "픽스처 도시는 최근 테스트 자동화에 성공하며 미래 성장 동력을 확보했다.",
        "location": "픽스처시", "category": "TEST"
    }

    # URL 동적 생성
    url_chroma = client.app.url_path_for('add_mock_news_to_chroma') 
    url_graph = client.app.url_path_for('add_mock_news_to_neo4j') 

    # 데이터 주입
    response_chroma = client.post(url_chroma, json=mock_news) # client.post("/api/v1/dev/news/mock_chroma", json=mock_news)
    assert response_chroma.status_code == 200

    response_graph = client.post(url_graph, json=mock_news) # client.post("/api/v1/dev/news/mock_graph", json=mock_news)
    assert response_graph.status_code == 200

    yield mock_news

    print(f"\n--- [Teardown] Cleaning up test data: {test_news_id} ---")
    graph_service.delete_test_data(test_news_id)
    delete_vector_data([test_news_id])

def test_health_check(client: TestClient): # client fixture를 인자로 받습니다.
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_full_rag_pipeline(client: TestClient, setup_and_teardown_db): # 두 fixture를 모두 받습니다.
    mock_news = setup_and_teardown_db

    # 1. 리포트 생성 요청
    query = {
        "query": f"{mock_news['location']}의 {mock_news['category']} 산업에 대한 소식",
        "location": mock_news['location'],
        "category": mock_news['category']
    }
    response = client.post("/api/v1/generate", json=query)
    assert response.status_code == 202, f"API Error: {response.text}"
    task_id = response.json()["task_id"]
    assert task_id is not None

    # 2. 결과 확인 (폴링)
    final_result = None
    for _ in range(20):
        response = client.get(f"/api/v1/status/{task_id}")
        assert response.status_code == 200
        if response.json()["status"] == "COMPLETED":
            final_result = response.json()
            break
        time.sleep(1)

    # 3. 최종 결과 검증 (개선된 방식)
    assert final_result is not None, "Task did not complete in time"
    assert final_result["status"] == "COMPLETED"
    
    report_text = final_result["result"]["report"]
    # '성공', '도약', '확보' 등 핵심 의미를 담는 키워드 중 하나라도 포함되는지 확인
    expected_keywords = ["성공", "도약", "확보", "자동화"]
    assert any(keyword in report_text for keyword in expected_keywords), \
        f"Expected one of {expected_keywords} in report, but got: {report_text}"