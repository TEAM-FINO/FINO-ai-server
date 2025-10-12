import logging
import concurrent.futures
from pydantic import BaseModel, Field
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import JsonOutputParser
from app.services.graph_service import NewsInfo
from app.services.google_api_service import google_api_service
from app.services.vectorstore_service import collection, embedding_model
from app.services.llm_service import llm
import time

logger = logging.getLogger(__name__)

TOP_N_EXECUTIVE = 5
TOP_N_CATEGORY = 3
VECTOR_SEARCH_CANDIDATES = 5
MAX_API_WORKERS = 5 # 병렬 API 호출 스레드 수

def _rank_news_by_trending(news_list: List[NewsInfo]) -> List[NewsInfo]:
    """입력된 뉴스 리스트의 화제성을 측정하고 점수가 높은 순으로 정렬합니다."""
    if not news_list:
        return []

    logger.info(f"Ranking {len(news_list)} news items using Google API.")

    def get_score_for_news(news: NewsInfo) -> tuple[NewsInfo, int]:
        """뉴스와 점수를 튜플로 반환 (예외 시 0점 반환)"""
        try:
            title = news.get('title', '').strip()
            if not title:
                return (news, 0)
            score = google_api_service.get_search_trend_score(title)
            return (news, score)
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate limit' in error_msg or '429' in error_msg or 'quota' in error_msg:
                logger.error(f"Google API rate limit hit for '{news.get('title')}': {e}")
            else:
                logger.warning(f"Failed to get trend score for '{news.get('title')}': {e}")
            return (news, 0)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_API_WORKERS) as executor:
            # 각 뉴스에 대해 (news, score) 튜플 리스트를 생성
            scored_news_tuples = list(executor.map(get_score_for_news, news_list))
        
        # 점수(튜플의 두 번째 요소)를 기준으로 내림차순 정렬
        scored_news_tuples.sort(key=lambda x: x[1], reverse=True)
        
        # 통계 로깅
        successful_scores = sum(1 for _, score in scored_news_tuples if score > 0)
        logger.info(f"Successfully scored {successful_scores}/{len(news_list)} news items.")
        
        # 점수가 너무 적으면 경고
        if successful_scores < len(news_list) * 0.5:
            logger.warning(
                f"Only {successful_scores}/{len(news_list)} news got scores. "
                "Possible API rate limit or connectivity issue."
            )
        
        # 정렬된 튜플에서 뉴스 객체만 추출하여 최종 리스트 반환
        return [news for news, score in scored_news_tuples]
    
    except Exception as e:
        # ThreadPoolExecutor 자체에 심각한 문제가 생긴 경우
        logger.error(f"Critical error in ThreadPoolExecutor during ranking: {e}", exc_info=True)
        # 최소한 순서라도 유지하기 위해 원본 반환 (하지만 경고 로그 남김)
        logger.warning("Returning original news list without ranking due to executor failure.")
        return news_list


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
        n_results=5,
        include=["metadatas", "documents", "distances"]
    )
    
    # 검색된 문서들을 종합하여 컨텍스트를 구성
    context_parts = []
    distances_list = results.get('distances', [[] for _ in range(len(top_news_list))])
    
    # 통계 수집
    total_retrieved = sum(len(docs) for docs in results['documents'])
    total_added = 0
    self_excluded = 0
    
    for i, (news, documents, metadatas, distances) in enumerate(
        zip(top_news_list, results['documents'], results['metadatas'], distances_list), 1
    ):
        # 원본 Top 뉴스 정보
        context_parts.append(f"\n### 주요 뉴스 #{i}: {news['title']}")
        
        # 빈 결과 처리
        if not documents:
            context_parts.append("  (ChromaDB에서 관련 뉴스를 찾을 수 없습니다)")
            logger.warning(f"No related documents found for news: {news['title']}")
            continue
        
        sorted_related = sorted(
            zip(documents, metadatas, distances), 
            key=lambda x: x[2]
        )
        
        added_count = 0
        for doc_content, metadata, distance in sorted_related:
            news_id = metadata.get('news_id')
            
            if news_id == news.get('news_id'):
                self_excluded += 1
                continue
            
            if news_id:
                title = metadata.get('title', '제목 없음')
                content_preview = doc_content[:150].strip() + "..."
                context_parts.append(f"  - 관련 뉴스: {title}\n    (내용: {content_preview})")
                
                added_count += 1
                total_added += 1
                
                if added_count >= 3:
                    break
    
        # 관련 뉴스가 하나도 추가되지 않은 경우
        if added_count == 0:
            context_parts.append("  (유사한 관련 뉴스가 없습니다)")
    
    final_context = "\n".join(context_parts)
    
    # 상세 로그
    logger.info(
        f"Context stats: retrieved={total_retrieved}, added={total_added}, "
        f"self_excluded={self_excluded}, final_length={len(final_context)} chars"
    )
    
    if len(final_context) > 8000:
        logger.warning(f"Context length {len(final_context)} exceeds recommended limit.")
    
    return final_context

class ExecutiveSummary(BaseModel):
    headline_briefing: str = Field(description="가장 중요한 핵심 이슈들을 요약한 헤드라인 브리핑")
    key_trends: str = Field(description="주요 동향 및 이슈에 대한 1~2문단 분량의 상세 분석")

class CategoricalAnalysis(BaseModel):
    category: str = Field(description="분석 대상 카테고리 이름")
    analysis_text: str = Field(description="해당 카테고리에 대한 심층 분석 기사")

# 지역 전체 핵심 이슈 분석
def generate_executive_summary(all_news: List[NewsInfo]) -> Dict:
    """지역 전체 뉴스를 바탕으로 '지역 전체 핵심 이슈 분석'을 생성하여 JSON(Dict)으로 반환합니다."""
    logger.info("Executive Summary Generation.")
    
    parser = JsonOutputParser(pydantic_object=ExecutiveSummary) # JSON 파서 초기화
    
    # 지역 전체 뉴스 랭킹
    ranked_news = _rank_news_by_trending(all_news)
    top_executive_news = ranked_news[:TOP_N_EXECUTIVE]
    
    # 컨텍스트 확장
    context = _expand_context_with_chroma(top_executive_news)
    
    # LLM 프롬프트 및 생성
    prompt = ChatPromptTemplate.from_template(
        """
        당신은 대한민국 지역 동향을 분석하는 전문 애널리스트입니다.
        주어진 [핵심 뉴스 데이터]를 바탕으로, 해당 지역의 전반적인 상황을 조망하는 '헤드라인 브리핑'과 '주요 동향 및 이슈'를 분석해주세요.
        독자가 상황을 한눈에 파악할 수 있도록, 가장 중요한 사건과 그 의미를 중심으로 명확하고 간결하게 작성해야 합니다.
        **반드시 한국어로** 상세하고 깊이 있는 리포트를 작성해주세요.

        **분석 가이드라인:**
        1. 당신은 반드시 다음 JSON 형식에 맞춰서만 응답해야 합니다. 절대로 JSON 외부에는 어떤 텍스트, 설명, 마크다운도 추가해서는 안 됩니다.
        {format_instructions}
        2. 여러 기사의 정보를 종합하여, 사실 기반의 균형 잡힌 관점을 제시해야 합니다.
        3. 추측이나 확인되지 않은 정보는 절대 포함해서는 안 됩니다.

        [핵심 뉴스 데이터]
        {context}
        """,
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    chain = prompt | llm | parser

    # 파싱 실패 시 재시도 및 폴백
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            result = chain.invoke({"context": context})
            # 결과 필드 검증
            if "headline_briefing" not in result or "key_trends" not in result:
                raise ValueError("Missing required fields in LLM output.")
            return result
        except Exception as e:
            logger.warning(f"JSON parsing/validation failed (Attempt {attempt}/{max_attempts}): {e}")
            if attempt == max_attempts:
                logger.error("All parsing attempts failed for executive summary.")
                return {
                    "headline_briefing": "리포트 요약 생성 중 오류가 발생했습니다.",
                    "key_trends": "분석 과정에서 일시적인 문제가 발생하여 주요 동향을 요약할 수 없습니다."
                }
            time.sleep(attempt * 2) 

# 분야별 상세 분석
def generate_categorical_analysis(category_news: List[NewsInfo], category_name: str) -> Dict:
    """특정 카테고리 뉴스들을 바탕으로 '분야별 상세 분석' 파트를 생성합니다."""
    logger.info(f"Analysis for '{category_name}' category.")
    
    parser = JsonOutputParser(pydantic_object=CategoricalAnalysis) # JSON 파서 초기화
    
    ranked_news = _rank_news_by_trending(category_news)
    top_category_news = ranked_news[:TOP_N_CATEGORY]

    context = _expand_context_with_chroma(top_category_news)

    prompt = ChatPromptTemplate.from_template(
        """
        당신은 '{category_name}' 분야의 전문 애널리스트입니다. 다음 [분석 가이드라인]을 반드시 준수하여, 주어진 [분야별 뉴스 데이터]를 바탕으로 심층 분석 기사를 생성해주세요.
        **반드시 한국어로** 상세하고 깊이 있는 리포트를 작성해주세요.

        **분석 가이드라인:**
        1. **응답 형식**: 당신은 반드시 다음 JSON 형식에 맞춰서만 응답해야 합니다. 절대로 JSON 외부에는 어떤 텍스트, 설명, 마크다운도 추가해서는 안 됩니다.
        {format_instructions}
        2. **언어 및 형식**: 오직 완벽한 한국어 문법만을 사용하세요. 절대 다른 언어, 오타, 신조어를 섞어 쓰지 마세요. 
        3. **내용**: [분야별 뉴스 데이터]에 있는 사실만을 근거로 분석해야 합니다. 당신의 추측이나 외부 지식을 추가하지 마세요.
        4. **독창성**: 다른 파트에서 이미 언급된 내용이 있더라도, 이 분야만의 새로운 관점과 깊이 있는 해석을 제공해야 합니다.
        5. **구조**: 서론, 본론, 결론의 논리적인 구조를 갖춰 문단을 작성하세요.

        [분야별 뉴스 데이터]
        {context}
        """,
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    chain = prompt | llm | parser
    
    # 파싱 실패 시 재시도 및 폴백 
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            result = chain.invoke({"context": context, "category_name": category_name})
            if "category" not in result or "analysis_text" not in result:
                raise ValueError("Missing required fields in LLM output.")
            return result
        except Exception as e:
            logger.warning(f"JSON parsing/validation failed for '{category_name}' (Attempt {attempt}/{max_attempts}): {e}")
            if attempt == max_attempts:
                logger.error(f"All parsing attempts failed for '{category_name}'.")
                return {
                    "category": category_name,
                    "analysis_text": "해당 분야의 분석 리포트를 생성하는 중 일시적인 오류가 발생했습니다."
                }
            time.sleep(attempt * 2)