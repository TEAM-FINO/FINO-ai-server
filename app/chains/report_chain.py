import logging
import concurrent.futures
import re
import json
from pydantic import BaseModel, Field
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.services.graph_service import NewsInfo
from app.services.google_api_service import google_api_service
from app.services.vectorstore_service import collection, embedding_model
from app.services.llm_service import llm
import time

logger = logging.getLogger(__name__)

TOP_N_EXECUTIVE = 5
TOP_N_CATEGORY = 3
VECTOR_SEARCH_CANDIDATES = 3
MAX_API_WORKERS = 10 # 병렬 API 호출 스레드 수

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
        n_results=VECTOR_SEARCH_CANDIDATES,
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
                
                if added_count >= VECTOR_SEARCH_CANDIDATES:
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

def extract_json_from_text(text: str) -> str:
    """LLM 응답에서 JSON 객체만 추출하고, 개행 문자를 이스케이프 처리합니다."""
    # 마크다운 코드 블록 제거
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # JSON 객체 패턴 찾기 (중첩된 중괄호 지원)
    brace_count = 0
    start_idx = -1
    end_idx = -1
    
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                end_idx = i + 1
                break
    
    if start_idx == -1 or end_idx == -1:
        # JSON 패턴을 찾지 못한 경우 원본 반환
        return text.strip()
    
    json_str = text[start_idx:end_idx].strip()
    
    # JSON 문자열 값 내부의 이스케이프되지 않은 개행 문자 처리
    # "analysis_text": "... 내용 \n 내용 ..." 형태를 안전하게 처리
    def escape_newlines_in_strings(match):
        """JSON 문자열 값 내부의 개행을 \\n으로 변환"""
        string_content = match.group(1)
        # 이미 이스케이프된 \n은 그대로 두고, 실제 개행만 변환
        escaped = string_content.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'"{escaped}"'
    
    # 정규식: "..." 형태의 문자열 찾기 (따옴표 내부에 있는 내용만)
    json_str = re.sub(r'"((?:[^"\\]|\\.)*?)"', escape_newlines_in_strings, json_str)
    
    return json_str


def validate_korean_only(text: str) -> bool:
    """텍스트가 한국어 위주인지 검증 (영어 비율 20% 미만)"""
    if not text:
        return False
    # 알파벳 개수 세기 (공백 제외)
    alpha_count = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    total_chars = len(text.replace(' ', '').replace('\n', ''))
    if total_chars == 0:
        return False
    english_ratio = alpha_count / total_chars
    return english_ratio < 0.2  # 영어 비율 20% 미만만 허용

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
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """
            당신은 대한민국 지역 경제 및 사회 동향을 분석하는 **수석 애널리스트**입니다.
    
            # 역할 및 목표
            - 해당 지역의 의사결정권자(지자체, 기업, 투자자)가 **1분 안에 핵심을 파악**할 수 있도록 작성
            - 단순 요약이 아닌, **트렌드와 의미 해석**에 집중
            - **객관적 사실**에 기반하되, **인사이트**를 제공

            # 중요: 출력 형식
            반드시 다음 JSON 형식으로만 응답하세요. **어떠한 추가 설명, 마크다운, 코드 블록도 포함하지 마세요.**
            {format_instructions}

            # 작성 가이드라인

            ## 1. headline_briefing (헤드라인 브리핑)
            **목적**: 5초 안에 "무슨 일이 있었나"를 파악할 수 있게 작성
            **길이**: 2-3문장 (100-150자)
            **구조**: 
            - 1문장: 가장 중요한 이슈 1개 (What)
            - 2문장: 영향력/파급효과 (Why it matters)
            
            **예시**:
            "춘천시가 데이터센터 유치에 성공하며 IT 산업 클러스터로 도약하고 있다. 이는 1,000명 이상의 신규 일자리 창출과 연간 3,000억 원의 경제효과가 예상된다."

            ## 2. key_trends (주요 동향 및 이슈)
            **목적**: 지역의 **현재 상황**과 **향후 전망**을 제시
            **길이**: 3-5문단 (300-500자)
            **구조**:
            - 1문단: 현재 상황 (What is happening now)
            - 2문단: 배경 및 원인 (Why is this happening)
            - 3문단: 예상 영향 및 전망 (What's next)
            - [선택] 4문단: 리스크 요인 또는 기회 요소

            **작성 원칙**:
            1. **구체적 수치** 사용 (%, 금액, 인원 등)
            2. **비교 표현** 활용 ("전년 대비", "전국 평균 대비")
            3. **시간 축** 명시 ("향후 6개월", "2025년 상반기")
            4. **주체 명확화** (정부, 기업, 시민단체 등)

            **피해야 할 표현**:
            ❌ "...로 보인다", "...할 것으로 예상된다" (추측)
            ❌ "중요하다", "의미 있다" (빈약한 형용사)
            ❌ "...등이 있다" (나열식 종결)

            **권장 표현**:
            ✅ "데이터에 따르면", "관계자에 따르면"
            ✅ "이는 ~를 의미한다", "~로 이어질 전망이다"
            ✅ "주목해야 할 점은", "특히"
        """),
        ("user", """
            # 입력 데이터
            다음은 해당 지역의 최근 주요 뉴스입니다:

            [핵심 뉴스 데이터]
            {context}

            # 중요 제약사항
            - 반드시 **한국어**로만 작성
            - JSON 형식 외에 **어떠한 추가 텍스트도 포함 금지**
            - [핵심 뉴스 데이터]에 **없는 정보는 작성 금지**
            - 불확실한 내용은 언급하지 말고, **확인된 사실만** 기술
        """)
    ])
    prompt = prompt_template.partial(format_instructions=parser.get_format_instructions())
    chain = prompt | llm

    # 파싱 실패 시 재시도
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            # LLM 호출
            raw_output = chain.invoke({"context": context})
            
            # AIMessage 객체인 경우 content 추출
            raw_text = raw_output.content if hasattr(raw_output, 'content') else str(raw_output)
            
            # JSON 추출 및 파싱
            json_text = extract_json_from_text(raw_text)
            result = json.loads(json_text)
            
            # 필드 검증
            if "headline_briefing" not in result or "key_trends" not in result:
                raise ValueError("Missing required fields in LLM output.")
            
            # 한국어 검증
            combined_text = result["headline_briefing"] + result["key_trends"]
            if not validate_korean_only(combined_text):
                raise ValueError(f"English content detected (attempt {attempt}). Retrying...")
            
            logger.info("✓ Executive summary parsed successfully.")
            return result
        
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"Parsing failed (Attempt {attempt}/{max_attempts}): {e}\n"
                f"Raw output preview: {raw_text[:200] if 'raw_text' in locals() else 'N/A'}"
            )
            
            if attempt == max_attempts:
                logger.error("All parsing attempts failed for executive summary.")
                return {
                    "headline_briefing": "리포트 요약 생성 중 오류가 발생했습니다.",
                    "key_trends": "분석 과정에서 일시적인 문제가 발생하여 주요 동향을 요약할 수 없습니다."
                }
            
            time.sleep(attempt * 2)

# 분야별 상세 분석
def generate_categorical_analysis(category_news: List[NewsInfo], category_name: str) -> Dict:
    """특정 카테고리 뉴스를 바탕으로 분야별 분석을 생성합니다."""
    logger.info(f"Analysis for '{category_name}' category.")
    
    parser = JsonOutputParser(pydantic_object=CategoricalAnalysis) # JSON 파서 초기화
    
    ranked_news = _rank_news_by_trending(category_news)
    top_category_news = ranked_news[:TOP_N_CATEGORY]

    context = _expand_context_with_chroma(top_category_news)
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", f"""
            당신은 '{{category_name}}' 분야를 전문으로 하는 **시니어 산업 애널리스트**입니다.
    
            # 역할 및 목표
            - 해당 분야의 **전문가**가 읽어도 만족할 수준의 심층 분석 제공
            - 단순 사실 나열이 아닌, **트렌드 분석 + 시사점 도출**
            - 지역 특화 관점에서 **전국 대비 위상** 및 **경쟁력** 평가

            # 출력 형식
            반드시 다음 JSON 형식으로만 응답하세요:
            {{format_instructions}}

            # 작성 가이드라인

            ## category 필드
            - 반드시 한국어로 작성 (예: "경제", "사회", "문화")
            - 입력받은 category_name을 그대로 사용

            ## analysis_text 필드
            **목적**: 해당 분야의 **현황 -> 분석 -> 전망**을 3단계로 제시
            **길이**: 4-6문단 (500-800자)
            
            **필수 구조**:
            
            ### 1단계: 현황 파악 (1-2문단)
            - **무슨 일이 일어났는가?** (주요 이슈 2-3개)
            - **누가 주도하는가?** (주체: 정부, 기업, 시민 등)
            - **규모는 어느 정도인가?** (구체적 수치)
            
            예시:
            "'{category_name}' 분야에서는 최근 [주요 이슈 1], [주요 이슈 2]가 동시에 진행되고 있다. 
            특히 [주체]의 [구체적 행동]은 [금액/인원/규모]에 달하며, 이는 전년 대비 [증감률]에 해당한다."

            ### 2단계: 심층 분석 (2-3문단)
            - **왜 이런 일이 일어났는가?** (배경, 원인)
            - **다른 지역/분야와 비교하면?** (상대적 위치)
            - **주목해야 할 변화는?** (새로운 트렌드, 전환점)
            
            분석 프레임워크:
            - SWOT 관점: 강점, 약점, 기회, 위협 중 1-2개 선택
            - 이해관계자 분석: 누가 이득/손해를 보는가?
            - 시간 축: 단기 vs 중장기 영향

            ### 3단계: 전망 및 시사점 (1-2문단)
            - **앞으로 어떻게 전개될 것인가?** (향후 3-6개월)
            - **주의 깊게 봐야 할 포인트는?** (핵심 지표, 이벤트)
            - **지역에 주는 의미는?** (긍정적/부정적 영향)

            예시:
            "향후 6개월간 [예상 시나리오]가 전개될 것으로 보인다. 
            특히 [핵심 지표]의 변화 추이가 중요한 판단 기준이 될 것이다. 
            이는 지역 경제에 [긍정적/부정적] 영향을 미칠 것으로 예상된다."

            ## 작성 원칙
            
            **DO**:
            ✅ 구체적 수치와 데이터 활용
            ✅ 비교 분석 (전년 대비, 타지역 대비)
            ✅ 전문 용어는 필요시 짧게 설명
            ✅ 인과관계 명확히 ("A로 인해 B가 발생")
            ✅ 시간 표현 구체화 ("2025년 상반기", "향후 3개월")

            **DON'T**:
            ❌ 추측성 표현 ("~것으로 보인다", "~할 가능성")
            ❌ 일반론적 서술 ("중요하다", "의미 있다")
            ❌ 근거 없는 전망 (데이터에 없는 미래 예측)
            ❌ 다른 분야 중복 내용 (Executive Summary와 차별화)
            ❌ 영어 단어 남발 (필요시 한글 병기)
        """),
        ("user", """
            ## 분야별 특화 가이드
    
            **경제**: 투자액, 고용효과, GDP 기여도, 산업 클러스터 효과
            **사회**: 인구 변화, 복지 수혜자 수, 안전 지표, 시민 만족도
            **문화**: 관람객 수, 문화시설 증감, 지역 정체성, 관광 연계효과
            **정치**: 정책 수혜자, 예산 규모, 이해관계자 반응, 법제화 일정
            **환경**: 오염도 수치, 친환경 투자액, 규제 영향, 시민 인식 변화

            # 입력 데이터
            다음은 '{{category_name}}' 분야의 최근 주요 뉴스입니다:

            [분야별 뉴스 데이터]
            {context}

            # 중요 제약사항
            - 반드시 **한국어**로만 작성 (완벽한 문법)
            - JSON 형식 외에 **어떠한 추가 텍스트도 포함 금지**
            - [분야별 뉴스 데이터]에 **없는 정보는 작성 금지**
            - **사실과 분석을 명확히 구분** (사실: "~이다", 분석: "이는 ~를 의미한다")
            - 다른 파트(Executive Summary)와 **내용 중복 최소화**
        """)
    ])
    prompt = prompt_template.partial(format_instructions=parser.get_format_instructions())
    chain = prompt | llm
    
    # 파싱 실패 시 재시도
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            raw_output = chain.invoke({"context": context, "category_name": category_name})
            
            raw_text = raw_output.content if hasattr(raw_output, 'content') else str(raw_output)
            
            json_text = extract_json_from_text(raw_text)
            result = json.loads(json_text)
            
            if "category" not in result or "analysis_text" not in result:
                raise ValueError("Missing required fields in LLM output.")
            
            if not validate_korean_only(result["analysis_text"]):
                raise ValueError(f"English detected in '{category_name}' (attempt {attempt})")
            
            logger.info(f"✓ Category '{category_name}' analysis parsed successfully.")
            return result
        
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"Parsing failed for '{category_name}' (Attempt {attempt}/{max_attempts}): {e}\n"
                f"Raw output preview: {raw_text[:200] if 'raw_text' in locals() else 'N/A'}"
            )
            
            if attempt == max_attempts:
                logger.error(f"All parsing attempts failed for '{category_name}'.")
                return {
                    "category": category_name,
                    "analysis_text": "해당 분야의 분석 리포트를 생성하는 중 일시적인 오류가 발생했습니다."
                }
            
            time.sleep(attempt * 2)