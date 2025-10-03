import logging
import concurrent.futures
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from app.services.llm_service import llm as default_llm
from app.services.vectorstore_service import collection, embedding_model
from app.services.graph_service import graph_service 
from app.services.google_api_service import google_api_service

logger = logging.getLogger(__name__)

VECTOR_SEARCH_CANDIDATES = 5
TOP_DOCS_LIMIT = 3
MAX_API_WORKERS = 5 # 병렬 API 호출 스레드 수

# Neo4j 필터링 
def _filter_news_ids_from_neo4j(input_dict: dict) -> list[str]:
    """입력 딕셔너리에서 location과 category를 사용하여 뉴스 ID를 필터링합니다."""
    try:
        location = input_dict.get('location')
        category = input_dict.get('category')
        logger.info(f"Filtering news from Neo4j (Location: {location}, Category: {category})")
        return graph_service.get_filtered_news_ids(location, category)
    except Exception as e:
        logger.error(f"Error in Neo4j filtering step: {e}", exc_info=True)
        return []

# ChromaDB 검색 
def _retrieve_documents_from_chroma(input_dict: dict) -> list[dict]:
    """필터링된 ID를 바탕으로 의미 기반 검색을 수행하고, 문서 객체 리스트를 반환합니다."""
    try:
        # 이전 단계(Neo4j)의 결과를 입력으로 받음
        query, filtered_ids = input_dict['query'], input_dict['filtered_ids']
        logger.info(f"Retrieving documents from ChromaDB for query: '{query}'.")
        query_vector = embedding_model.encode(query).tolist()
        
        where_filter = {"news_id": {"$in": filtered_ids}} if filtered_ids else None
        
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=VECTOR_SEARCH_CANDIDATES,
            where=where_filter
        )
        
        documents_with_metadata = []
        if results and results.get('documents') and results['documents'][0]:
            for content, metadata in zip(results['documents'][0], results['metadatas'][0]):
                documents_with_metadata.append({"content": content, "metadata": metadata})
                
        logger.debug(f"ChromaDB found {len(documents_with_metadata)} documents.")
        return documents_with_metadata
    except Exception as e:
        logger.error(f"Error in ChromaDB retrieval step: {e}", exc_info=True)
        return []
    
# Google API 랭킹 
def _rank_documents_by_trending(docs: list[dict]) -> list[dict]:
    """검색된 문서들의 화제성을 측정하고 점수가 높은 순으로 정렬합니다."""
    # 이전 단계(ChromaDB)의 결과를 입력으로 받음
    if not docs:
        return []

    logger.info(f"Ranking {len(docs)} documents using Google API in parallel.")
    
    # 각 문서의 화제성 점수 계산
    def get_score_for_doc(doc):
        try:
            title = doc['metadata'].get('title', '').strip()
            if not title:
                logger.debug("Empty title found, assigning score 0.")
                return 0
            return google_api_service.get_search_trend_score(title)
        except Exception as e:
            logger.warning(f"Failed to get trend score for '{title}': {e}")
            return 0  # 개별 API 실패 시 기본값 반환
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_API_WORKERS) as executor:
            scores = list(executor.map(get_score_for_doc, docs))
        # 점수가 높은 순으로 정렬
        scored_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs]
    except Exception as e:
        logger.error(f"Error during trending rank: {e}", exc_info=True)
        return docs

# 최종 컨텍스트 포맷팅 
def _format_context(docs: list[dict]) -> str:
    """랭킹된 문서들 중 상위 몇 개만 선택하여 LLM에게 전달할 최종 컨텍스트 문자열을 만듭니다."""
    try:
        logger.info(f"Formatting context with top {TOP_DOCS_LIMIT} documents.")
        # 이전 단계(랭킹)의 결과를 입력으로 받음
        if not docs:
            return "관련된 뉴스 기사를 찾을 수 없습니다."
        
        # 화제성 높은 상위 'TOP_DOCS_LIMIT'개의 뉴스만 선택
        top_docs = docs[:TOP_DOCS_LIMIT]
        
        # 각 뉴스의 제목과 내용을 명확하게 구분하여 컨텍스트 구성
        context_parts = []
        for i, doc in enumerate(top_docs, 1):
            title = doc['metadata'].get('title', '제목 없음')
            content = doc.get('content', '내용 없음')  
            context_parts.append(f"뉴스 #{i}\n- 제목: {title}\n- 내용: {content}")
            
        return "\n\n".join(context_parts)
    except Exception as e:
        logger.error(f"Error in context formatting: {e}", exc_info=True)
        return "뉴스 기사 처리 중 오류가 발생했습니다."

# LCEL 체인 구성
def get_report_chain(llm_override=None) -> Runnable:
    """
    모든 단계를 포함하는 LangChain RAG 파이프라인을 생성하여 반환합니다.
    """
    llm = llm_override or default_llm
    
    prompt_template = ChatPromptTemplate.from_template(
        """
        당신은 대한민국 지역 뉴스를 분석하는 전문 애널리스트입니다.
        주어진 [관련 뉴스 기사]를 완벽하게 이해하고, 사용자의 [질문]에 대해 **반드시 한국어로** 상세하고 깊이 있는 리포트를 작성해주세요.
        
        **분석 가이드라인:**
        1. 주어진 [관련 뉴스 기사]의 정보만을 사용하여 답변해야 합니다.
        2. 여러 기사의 정보를 종합하여, 사실 기반의 균형 잡힌 관점을 제시해야 합니다.
        3. 추측이나 확인되지 않은 정보는 절대 포함해서는 안 됩니다.

        [관련 뉴스 기사]
        {context}

        [질문]
        {query}

        [생성 리포트]
        """
    )
    
    return (
        {
            "filtered_ids": _filter_news_ids_from_neo4j,
            "query": lambda x: x["query"]
        }
        | RunnablePassthrough.assign(retrieved_docs=_retrieve_documents_from_chroma)
        | RunnablePassthrough.assign(ranked_docs=lambda x: _rank_documents_by_trending(x["retrieved_docs"]))
        | {
            "context": lambda x: _format_context(x["ranked_docs"]),
            "query": lambda x: x["query"],
          }
        | prompt_template
        | llm
        | StrOutputParser()
    )