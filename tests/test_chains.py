import pytest
import numpy as np
from langchain_core.language_models.fake_chat_models import FakeListChatModel

def test_filter_news_ids_from_neo4j(mocker):
    """Neo4j 서비스를 Mocking하여 필터링 함수를 테스트합니다."""
    # graph_service.get_filtered_news_ids 함수가 항상 ["id1", "id2"]를 반환하도록 속입니다.
    mocker.patch("app.chains.report_chain.graph_service.get_filtered_news_ids", return_value=["id1", "id2"])

    from app.chains.report_chain import _filter_news_ids_from_neo4j

    input_data = {"location": "테스트시", "category": "IT"}
    result = _filter_news_ids_from_neo4j(input_data)

    assert result == ["id1", "id2"]


def test_retrieve_documents_from_chroma(mocker):
    """ChromaDB와 임베딩 모델을 Mocking하여 검색 함수를 테스트합니다."""
    # 가짜 ChromaDB 검색 결과 정의
    mock_results = {
        'ids': [['id1']], 
        'documents': [['테스트 문서입니다.']],
        'metadatas': [[{'news_id': 'id1', 'title': '테스트 제목'}]]
    }
    # collection.query 함수를 가짜 결과를 반환하도록 속입니다.
    mocker.patch("app.chains.report_chain.collection.query", return_value=mock_results)
    # 임베딩 모델도 간단한 가짜 함수로 대체합니다.
    mocker.patch("app.chains.report_chain.embedding_model.encode", return_value=np.array([0.1]*768))

    from app.chains.report_chain import _retrieve_documents_from_chroma

    input_data = {"query": "테스트", "filtered_ids": ["id1"]}
    result = _retrieve_documents_from_chroma(input_data)

    assert len(result) == 1
    assert result[0]["content"] == "테스트 문서입니다."
    
    
def test_rank_documents_by_trending(mocker):
    """Google API 서비스를 Mocking하여 랭킹 및 정렬 기능을 테스트합니다."""
    # "모의고사" 전략: get_search_trend_score 함수를 가짜 함수로 대체
    def mock_get_score(keyword):
        if "레고랜드" in keyword: return 1000
        if "데이터센터" in keyword: return 100
        return 10
        
    mocker.patch("app.chains.report_chain.google_api_service.get_search_trend_score", side_effect=mock_get_score)

    from app.chains.report_chain import _rank_documents_by_trending

    docs_to_rank = [
        {"content": "데이터센터 내용", "metadata": {"title": "춘천 데이터센터 착공"}},
        {"content": "레고랜드 내용", "metadata": {"title": "춘천 레고랜드 인기"}}
    ]
    result = _rank_documents_by_trending(docs_to_rank)
    assert "레고랜드" in result[0]['metadata']['title']
    
       
# RAG 체인 전체를 검증하는 단위 테스트
def test_report_chain_invocation(mocker):
    """
    RAG 체인 전체의 흐름을 테스트합니다.
    모든 외부 서비스는 Mocking하고, 테스트 전용 체인을 생성하여 검증합니다.
    """
    # 모든 외부 의존성을 먼저 Mock
    mocker.patch("app.chains.report_chain.graph_service.get_filtered_news_ids", return_value=["news1"])
    mocker.patch("app.chains.report_chain.collection.query", return_value={
        'ids': [['id1']], 
        'documents': [['뉴스 내용']], 
        'metadatas': [[{'title': '뉴스 제목', 'news_id': 'news1'}]]
    })
    mocker.patch("app.chains.report_chain.google_api_service.get_search_trend_score", return_value=100)
    mocker.patch("app.chains.report_chain.embedding_model.encode", return_value=np.array([0.1]*768))
    
    # 의존성 Mock 후 체인 생성 함수를 import
    from app.chains.report_chain import get_report_chain
    
    # LangChain이 제공하는 테스트용 가짜 LLM 모델 생성
    fake_llm = FakeListChatModel(responses=["최종 AI 생성 리포트입니다."])

    # 가짜 llm을 '주입'하여 테스트 전용 체인 생성
    report_chain_for_test = get_report_chain(llm_override=fake_llm)
    
    # 테스트 실행 및 검증
    input_data = {"query": "테스트 쿼리", "location": "테스트시", "category": "IT"}
    final_report = report_chain_for_test.invoke(input_data)
    
    assert final_report == "최종 AI 생성 리포트입니다."