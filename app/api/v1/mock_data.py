from fastapi import APIRouter
from app.services.vectorstore_service import collection, embedding_model, delete_test_data
from app.services.graph_service import graph_service
from app.schemas.report_schemas import NewsDocument

router = APIRouter()
    
# 테스트용 Mock 데이터 주입 API
@router.post("/news/mock_chroma", tags=["Mock Data"])
def add_mock_news_to_chroma(doc: NewsDocument):
    """(테스트용) ChromaDB에 문서를 임베딩하여 저장합니다."""
    embedding = embedding_model.encode(doc.content).tolist()
    collection.add(
        ids=[doc.news_id],
        embeddings=[embedding],
        documents=[doc.content],
        metadatas=[{ 
            "news_id": doc.news_id,
            "title": doc.title,
            "press": doc.press
        }]
    )
    return {"status": "success", "news_id": doc.news_id}

@router.post("/news/mock_graph", tags=["Mock Data"])
def add_mock_news_to_neo4j(doc: NewsDocument):
    """(테스트용) Neo4j에 뉴스 노드와 관계를 생성합니다."""
    graph_service.create_news_graph_data(doc)
    return {"status": "success", "news_id": doc.news_id}

@router.delete("/news/cleanup/{news_id}", tags=["Mock Data"])
def cleanup_test_news(news_id: str):
    """(테스트용) ID에 해당하는 테스트 데이터를 모든 DB에서 정리합니다."""
    try:
        graph_service.delete_test_data(news_id)
        delete_test_data([news_id])
        return {"status": "success", "message": f"Deleted {news_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
