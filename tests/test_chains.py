import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
import json

MOCK_ALL_NEWS_DATA = [
    {
        "news_id": "EXEC01", 
        "title": "춘천 경제 활성화 정책 발표", 
        "category": "경제",
        "content": "춘천시가 지역 경제 활성화를 위한 새로운 정책을 발표했다...",
        "pubDate": "Mon, 06 Oct 2025 10:00:00 +0900"
    },
    {
        "news_id": "EXEC02", 
        "title": "강원도 관광객 증가세", 
        "category": "사회",
        "content": "최근 강원도를 찾는 관광객이 전년 대비 20% 증가했다...",
        "pubDate": "Mon, 06 Oct 2025 11:30:00 +0900"
    },
    {
        "news_id": "CAT01", 
        "title": "중소기업 지원 프로그램 시작", 
        "category": "경제",
        "content": "지역 중소기업을 위한 맞춤형 지원 프로그램이 시작됐다...",
        "pubDate": "Mon, 06 Oct 2025 09:00:00 +0900"
    },
]

@pytest.fixture
def mock_chain_helpers(mocker):
    """Chain 테스트에서 공통으로 사용하는 헬퍼 함수 Mock"""
    mocker.patch("app.chains.report_chain._rank_news_by_trending", 
                 return_value=MOCK_ALL_NEWS_DATA)
    mocker.patch("app.chains.report_chain._expand_context_with_chroma", 
                 return_value="### 주요 뉴스 #1: 춘천 경제 활성화 정책 발표\n  - 관련 뉴스: 중소기업 지원...")
    yield
    
def test_generate_executive_summary(mocker, mock_chain_helpers):
    """'거시적 요약' 생성 함수가 올바른 JSON(dict)을 반환하는지 테스트"""
    # Mocking 설정
    mock_response_dict = {
        "headline_briefing": "춘천시의 경제 활성화 정책과 관광 증가세가 주목받고 있습니다.", 
        "key_trends": "지역 경제 성장을 위한 다각적인 노력이 진행 중입니다..."
    }
    # 가짜 LLM이 JSON "문자열"을 반환하도록 설정
    fake_llm = FakeListChatModel(responses=[json.dumps(mock_response_dict)])
    mocker.patch("app.chains.report_chain.llm", fake_llm)

    # 테스트 실행
    from app.chains.report_chain import generate_executive_summary
    result = generate_executive_summary(all_news=MOCK_ALL_NEWS_DATA)
    
    # 결과 검증
    assert result == mock_response_dict
    assert "headline_briefing" in result
    assert "key_trends" in result

# LLM 파싱 실패 시나리오 테스트
def test_generate_executive_summary_parsing_failure(mocker, mock_chain_helpers):
    """LLM이 잘못된 형식을 반환할 때 fallback이 작동하는지 테스트"""
    # 잘못된 응답 (JSON이 아님)
    fake_llm = FakeListChatModel(responses=[
        "이것은 JSON이 아닙니다.",  # 1번째 시도
        "여전히 JSON이 아닙니다.",  # 2번째 시도
        "마지막도 실패"  # 3번째 시도
    ])
    mocker.patch("app.chains.report_chain.llm", fake_llm)
    
    from app.chains.report_chain import generate_executive_summary
    result = generate_executive_summary(all_news=MOCK_ALL_NEWS_DATA)
    
    # Fallback 응답 확인
    assert "오류가 발생했습니다" in result["headline_briefing"]
    assert "일시적인 문제" in result["key_trends"]


def test_generate_categorical_analysis(mocker, mock_chain_helpers):
    """'분야별 상세 분석' 생성 함수가 올바른 JSON(dict)을 반환하는지 테스트"""
    # Mocking 설정
    mock_response_dict = {
        "category": "경제", 
        "analysis_text": "지역 중소기업 지원 프로그램이 시작되면서 경제 활성화에 대한 기대가 높아지고 있습니다..."
    }
    # 가짜 LLM이 JSON "문자열"을 반환하도록 설정
    fake_llm = FakeListChatModel(responses=[json.dumps(mock_response_dict)])
    mocker.patch("app.chains.report_chain.llm", fake_llm)

    from app.chains.report_chain import generate_categorical_analysis
    
    # '경제' 카테고리 뉴스만 필터링해서 함수에 전달하는 상황을 가정
    economy_news = [news for news in MOCK_ALL_NEWS_DATA if news['category'] == '경제']
    
    # 테스트 실행
    result = generate_categorical_analysis(category_news=economy_news, category_name="경제")

    # 결과 검증
    assert result == mock_response_dict
    assert result["category"] == "경제"
    assert "analysis_text" in result

# 카테고리 분석 파싱 실패 테스트
def test_generate_categorical_analysis_parsing_failure(mocker, mock_chain_helpers):
    """카테고리 분석 생성 시 LLM 파싱 실패 fallback 테스트"""
    fake_llm = FakeListChatModel(responses=[
        "잘못된 형식 1",
        "잘못된 형식 2", 
        "잘못된 형식 3"
    ])
    mocker.patch("app.chains.report_chain.llm", fake_llm)
    
    from app.chains.report_chain import generate_categorical_analysis
    
    economy_news = [news for news in MOCK_ALL_NEWS_DATA if news['category'] == '경제']
    result = generate_categorical_analysis(category_news=economy_news, category_name="경제")
    
    # Fallback 검증
    assert result["category"] == "경제"
    assert "일시적인 오류" in result["analysis_text"]


def test_assemble_final_report_sends_data(mocker):
    """'최종 조립' Task가 fino_api_service를 올바르게 호출하는지 테스트"""
    # FINO API 호출 Mock
    mock_send_report = mocker.patch(
        "app.celery_worker.fino_api_service.send_report", 
        return_value=(True, {"status": "ok"})
    )
    
    # Celery Task를 동기 모드로 실행하기 위한 설정
    from app.celery_worker import celery_app, assemble_final_report
    celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)
    
    # 테스트 데이터 준비
    analysis_results = [
        {"status": "SUCCESS", "category": "경제", "data": {"category": "경제", "analysis_text": "경제 분석..."}},
        {"status": "SUCCESS", "category": "사회", "data": {"category": "사회", "analysis_text": "사회 분석..."}}
    ]
    executive_summary = {
        "headline_briefing": "주요 이슈 브리핑입니다.",
        "key_trends": "주요 동향 분석입니다."
    }
    
    # Task 실행 (.delay() 대신 .apply_async() 사용하거나, 그냥 직접 호출)
    # eager 모드에서는 .delay()도 동기적으로 실행됨
    result = assemble_final_report.delay(
        analysis_results=analysis_results,
        executive_summary=executive_summary,
        location="테스트시",
        report_type="weekly"
    )
    
    # 결과 검증
    # eager 모드에서는 result.get()으로 실제 반환값을 가져올 수 있음
    task_result = result.get()
    assert task_result["status"] == "SUCCESS"
    assert task_result["location"] == "테스트시"
    assert task_result["report_type"] == "weekly"
    
    # FINO API 호출 검증
    mock_send_report.assert_called_once()
    
    # 전송된 데이터 내용 검증
    sent_data = mock_send_report.call_args[0][0]
    assert sent_data["location"] == "테스트시"
    assert sent_data["report_type"] == "weekly"
    assert "executive_summary" in sent_data
    assert "categorical_analysis" in sent_data
    assert sent_data["executive_summary"] == executive_summary
    assert len(sent_data["categorical_analysis"]) == 2
    assert "generated_at" in sent_data
    
# assemble_final_report 실패 시나리오 테스트
def test_assemble_final_report_retry_on_send_failure(mocker):
    """FINO 서버 전송 실패 시 재시도 로직 테스트"""
    # FINO API가 실패를 반환하도록 Mock
    mock_send_report = mocker.patch(
        "app.celery_worker.fino_api_service.send_report",
        return_value=(False, {"error": "Connection timeout"})
    )
    
    from app.celery_worker import celery_app, assemble_final_report
    celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)
    
    analysis_results = [{"status": "SUCCESS", "category": "경제", "data": {}}]
    executive_summary = {"headline_briefing": "...", "key_trends": "..."}
    
    # 실패 시 예외가 발생해야 함 (재시도 로직 때문)
    with pytest.raises(Exception) as exc_info:
        assemble_final_report.apply(args=(
            analysis_results,
            executive_summary,
            "테스트시",
            "weekly"
        ))
    
    # 예외 메시지 검증
    assert "Failed to send report to FINO Server" in str(exc_info.value)
    mock_send_report.assert_called_once()