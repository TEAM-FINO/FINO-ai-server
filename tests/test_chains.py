import pytest
import numpy as np
from app.chains.report_chain import _filter_news_from_neo4j, _retrieve_documents
from unittest.mock import MagicMock

def test_filter_news_from_neo4j(mocker):
    """Neo4j 서비스를 Mocking하여 필터링 함수를 테스트합니다."""
    # graph_service.get_filtered_news_ids 함수가 항상 ["id1", "id2"]를 반환하도록 속입니다.
    mocker.patch(
        "app.chains.report_chain.graph_service.get_filtered_news_ids",
        return_value=["id1", "id2"]
    )

    input_data = {"location": "테스트시", "category": "IT", "query": "test"}
    result = _filter_news_from_neo4j(input_data)

    assert result["filtered_ids"] == ["id1", "id2"]

def test_retrieve_documents(mocker):
    """ChromaDB와 임베딩 모델을 Mocking하여 검색 함수를 테스트합니다."""
    # 가짜 ChromaDB 검색 결과 정의
    mock_results = {
        'documents': [['테스트 문서입니다.']],
        'metadatas': [[{'news_id': 'id1', 'title': '테스트 제목'}]]
    }
    # collection.query 함수를 가짜 결과를 반환하도록 속입니다.
    mocker.patch("app.chains.report_chain.collection.query", return_value=mock_results)
    # 임베딩 모델도 간단한 가짜 함수로 대체합니다.
    mocker.patch(
        "app.chains.report_chain.embedding_model.encode",
        return_value=np.array([0.1]*768)
    )

    input_data = {"query": "테스트", "filtered_ids": ["id1", "id2"]}
    result = _retrieve_documents(input_data)

    assert result['context'] == "테스트 문서입니다."