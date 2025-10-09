import logging
import concurrent.futures
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import StrOutputParser
from app.services.graph_service import NewsInfo
from app.services.google_api_service import google_api_service
from app.services.vectorstore_service import collection, embedding_model
from app.services.llm_service import llm

logger = logging.getLogger(__name__)

TOP_N_EXECUTIVE = 5
TOP_N_CATEGORY = 3
VECTOR_SEARCH_CANDIDATES = 10
MAX_API_WORKERS = 5 # 병렬 API 호출 스레드 수

def _rank_news_by_trending(news_list: List[NewsInfo]) -> List[NewsInfo]:
    """입력된 뉴스 리스트의 화제성을 측정하고 점수가 높은 순으로 정렬합니다."""
    if not news_list:
        return []

    logger.info(f"Ranking {len(news_list)} news items using Google API.")

    def get_score_for_news(news: NewsInfo):
        try:
            title = news.get('title', '').strip()
            if not title: return 0
            return google_api_service.get_search_trend_score(title)
        except Exception as e:
            logger.warning(f"Failed to get trend score for '{title}': {e}")
            return 0

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_API_WORKERS) as executor:
            scores = list(executor.map(get_score_for_news, news_list))
        
        scored_news = sorted(zip(news_list, scores), key=lambda x: x[1], reverse=True)
        return [news for news, score in scored_news]
    except Exception as e:
        logger.error(f"Error during trending rank: {e}", exc_info=True)
        return news_list # 에러 발생 시 원본 리스트 반환

def _expand_context_with_chroma(top_news_list: List[NewsInfo]) -> str:
    """선정된 Top N 뉴스 각각에 대해 ChromaDB에서 관련 문서를 검색하여 하나의 컨텍스트 문자열로 합칩니다."""
    if not top_news_list:
        return "관련된 주요 뉴스 기사를 찾을 수 없습니다."

    logger.info(f"Expanding context for {len(top_news_list)} top news items from ChromaDB.")
    
    # 각 뉴스의 제목으로 벡터 검색을 수행하고 결과를 종합
    queries = [news['title'] for news in top_news_list]
    query_vectors = embedding_model.encode(queries).tolist()

    results = collection.query(
        query_embeddings=query_vectors,
        n_results=VECTOR_SEARCH_CANDIDATES,
    )

    # 검색된 문서들을 종합하여 컨텍스트를 구성
    context_parts = []
    seen_ids = set() # 중복 문서 방지
    
    for i, (news, documents, metadatas) in enumerate(zip(top_news_list, results['documents'], results['metadatas']), 1):
        # 원본 Top 뉴스 정보 추가
        context_parts.append(f"주요 뉴스 #{i}: {news['title']}\n---")
        
        # ChromaDB에서 찾은 관련 뉴스 정보 추가
        for doc_content, metadata in zip(documents, metadatas):
            news_id = metadata.get('news_id')
            if news_id and news_id not in seen_ids:
                context_parts.append(f"- 제목: {metadata.get('title', '제목 없음')}\n- 내용: {doc_content[:200]}...") # 내용은 일부만 포함
                seen_ids.add(news_id)
        context_parts.append("\n")

    return "\n".join(context_parts)


def generate_executive_summary(all_news: List[NewsInfo]) -> str:
    """지역 전체 뉴스를 바탕으로 '지역 전체 핵심 이슈 분석'을 생성합니다."""
    logger.info("Starting Part 1: Executive Summary Generation.")
    
    # 1. 지역 전체 뉴스 랭킹
    ranked_news = _rank_news_by_trending(all_news)
    top_executive_news = ranked_news[:TOP_N_EXECUTIVE]
    
    # 2. 컨텍스트 확장
    context = _expand_context_with_chroma(top_executive_news)
    
    # 3. LLM 프롬프트 및 생성
    prompt = ChatPromptTemplate.from_template(
        """
        당신은 대한민국 지역 동향을 분석하는 전문 애널리스트입니다.
        주어진 [핵심 뉴스 데이터]를 바탕으로, 해당 지역의 전반적인 상황을 조망하는 '헤드라인 브리핑'과 '주요 동향 및 이슈'를 분석해주세요.
        독자가 상황을 한눈에 파악할 수 있도록, 가장 중요한 사건과 그 의미를 중심으로 명확하고 간결하게 작성해야 합니다.
        **반드시 한국어로** 상세하고 깊이 있는 리포트를 작성해주세요.

        **분석 가이드라인:**
        1. 여러 기사의 정보를 종합하여, 사실 기반의 균형 잡힌 관점을 제시해야 합니다.
        2. 추측이나 확인되지 않은 정보는 절대 포함해서는 안 됩니다.

        [핵심 뉴스 데이터]
        {context}

        [생성할 리포트]
        ## 헤드라인 브리핑
        (여기에 핵심 내용을 요약)

        ## 주요 동향 및 이슈
        (여기에 주요 이슈를 1~2문단으로 분석)
        """
    )
    
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": context})


def generate_categorical_analysis(category_news: List[NewsInfo], category_name: str) -> str:
    """특정 카테고리 뉴스들을 바탕으로 '분야별 상세 분석' 파트를 생성합니다."""
    logger.info(f"Starting Part 2: Analysis for '{category_name}' category.")
    
    ranked_news = _rank_news_by_trending(category_news)
    top_category_news = ranked_news[:TOP_N_CATEGORY]

    context = _expand_context_with_chroma(top_category_news)

    prompt = ChatPromptTemplate.from_template(
        """
        당신은 '{category_name}' 분야의 전문 애널리스트입니다. 다음 [분석 가이드라인]을 반드시 준수하여, 주어진 [분야별 뉴스 데이터]를 바탕으로 심층 분석 기사를 생성해주세요.
        **반드시 한국어로** 상세하고 깊이 있는 리포트를 작성해주세요.

        [분석 가이드라인]
        1. **언어 및 형식**: 오직 완벽한 한국어 문법만을 사용하세요. 절대 다른 언어, 오타, 신조어를 섞어 쓰지 마세요. 
        2. **내용**: [분야별 뉴스 데이터]에 있는 사실만을 근거로 분석해야 합니다. 당신의 추측이나 외부 지식을 추가하지 마세요.
        3. **독창성**: 다른 파트에서 이미 언급된 내용이 있더라도, 이 분야만의 새로운 관점과 깊이 있는 해석을 제공해야 합니다.
        4. **구조**: 서론, 본론, 결론의 논리적인 구조를 갖춰 문단을 작성하세요.

        [분야별 뉴스 데이터]
        {context}

        [생성할 분석 기사]
        ### {category_name} 분야 심층 분석
        (여기에 분석 가이드라인을 준수한 기사를 작성)
        """
    )

    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": context, "category_name": category_name})