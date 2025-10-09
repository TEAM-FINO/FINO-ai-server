import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

MOCK_ALL_NEWS_DATA = [
    {"news_id": "EXEC01", "title": "춘천 전체에서 가장 중요한 뉴스", "category": "경제"},
    {"news_id": "EXEC02", "title": "두번째로 중요한 뉴스", "category": "사회"},
    {"news_id": "CAT01", "title": "경제 분야의 핵심 뉴스", "category": "경제"},
]

def test_generate_executive_summary(mocker):
    """'거시적 요약' 생성 파이프라인 단위 테스트"""
    # 외부 의존성 Mocking
    # 헬퍼 함수들을 Mocking하여 generate_executive_summary 로직만 테스트
    mocker.patch("app.chains.report_chain._rank_news_by_trending", return_value=MOCK_ALL_NEWS_DATA)
    mocker.patch("app.chains.report_chain._expand_context_with_chroma", return_value="[Mocked] 확장된 컨텍스트입니다.")
    
    # LangChain LLM을 가짜 모델로 교체
    mocker.patch("app.chains.report_chain.llm", FakeListChatModel(responses=["[Mocked] 거시적 요약 리포트"]))
    
    from app.chains.report_chain import generate_executive_summary
    result = generate_executive_summary(all_news=MOCK_ALL_NEWS_DATA)
    
    # [THEN] 결과 검증
    assert result == "[Mocked] 거시적 요약 리포트"


def test_generate_categorical_analysis(mocker):
    """'분야별 상세 분석' 생성 파이프라인 단위 테스트"""
    # 외부 의존성 Mocking
    mocker.patch("app.chains.report_chain._rank_news_by_trending", return_value=[MOCK_ALL_NEWS_DATA[2]])
    mocker.patch("app.chains.report_chain._expand_context_with_chroma", return_value="[Mocked] 경제 분야 컨텍스트입니다.")
    mocker.patch("app.chains.report_chain.llm", FakeListChatModel(responses=["[Mocked] 경제 분야 분석 리포트"]))
    
    from app.chains.report_chain import generate_categorical_analysis
    
    # '경제' 카테고리 뉴스만 필터링해서 함수에 전달하는 상황을 가정
    economy_news = [news for news in MOCK_ALL_NEWS_DATA if news['category'] == '경제']
    result = generate_categorical_analysis(category_news=economy_news, category_name="경제")

    # 결과 검증
    assert result == "[Mocked] 경제 분야 분석 리포트"
