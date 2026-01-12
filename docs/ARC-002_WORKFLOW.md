# 워크플로우 상세

> **문서 번호**: ARC-002
> **버전**: 1.0
> **최종 수정일**: 2025-01-13
> **작성자**: FINO AI Team
> **검토자**: -

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-01-13 | FINO AI Team | 최초 작성 |

---

## 1. 개요

이 문서는 FINO AI Server의 리포트 생성 워크플로우를 상세하게 설명합니다. Celery 기반의 비동기 작업 처리, LangChain 분석 파이프라인, RAG 컨텍스트 확장 등 핵심 프로세스를 다룹니다.

---

## 2. 전체 워크플로우

### 2.1 워크플로우 개요

```
┌────────────────────────────────────────────────────────────────────────┐
│                        API 요청 (POST /generate/manual)                 │
│                              location, date_range                       │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│               generate_report_workflow (Main Task)                      │
│                       celery_worker.py:217                              │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
   ┌─────────────┐     ┌─────────────────┐    ┌─────────────────┐
   │ Neo4j 조회  │     │ Executive       │    │  병렬 카테고리   │
   │ 뉴스 데이터 │ →   │ Summary 생성    │ →  │     분석        │
   └─────────────┘     └─────────────────┘    └────────┬────────┘
                                                       │
          ┌────────────┬────────────┬────────────┬─────┴─────┐
          ▼            ▼            ▼            ▼           ▼
     ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐  ┌────────┐
     │ 경제   │   │ 사회   │   │ 문화   │   │ 정치   │  │ 환경   │
     │ 분석   │   │ 분석   │   │ 분석   │   │ 분석   │  │ 분석   │
     └────┬───┘   └────┬───┘   └────┬───┘   └────┬───┘  └────┬───┘
          │            │            │            │           │
          └────────────┴────────────┴────────────┴─────┬─────┘
                                                       ▼
                              ┌─────────────────────────────────────┐
                              │     assemble_final_report           │
                              │     최종 리포트 조립 + FINO 전송     │
                              └─────────────────────────────────────┘
```

### 2.2 Celery 워크플로우 패턴

```python
# Chain + Group 조합
workflow = chain(
    group(*category_tasks),      # 병렬 실행 (Group)
    assemble_final_report.s(...) # 순차 실행 (Chain)
)
```

---

## 3. Celery Task 상세

### 3.1 Task 목록

| Task 이름 | 파일 위치 | 역할 | 재시도 | 타임아웃 |
|-----------|-----------|------|--------|----------|
| `generate_report_workflow` | celery_worker.py:217 | 전체 워크플로우 지휘 | 2회 (10분 간격) | soft 600s / hard 720s |
| `analyze_single_category` | celery_worker.py:64 | 단일 카테고리 분석 | 3회 (지수 백오프) | soft 600s / hard 720s |
| `assemble_final_report` | celery_worker.py:111 | 결과 조립 및 전송 | 2회 (5분 간격) | soft 600s / hard 720s |
| `dispatch_weekly_reports` | celery_worker.py:322 | 주간 리포트 배치 | 3회 | - |
| `dispatch_monthly_reports` | celery_worker.py:392 | 월간 리포트 배치 | 3회 | - |

### 3.2 Task 설정 상세

```python
@celery_app.task(
    bind=True,                    # self 접근 가능
    name='reports.analyze_category',
    max_retries=3,                # 최대 재시도 횟수
    default_retry_delay=60,       # 기본 재시도 간격 (초)
    autoretry_for=(Exception,),   # 자동 재시도 예외
    retry_backoff=True,           # 지수 백오프 활성화
    retry_backoff_max=300,        # 최대 재시도 간격 (5분)
    retry_jitter=True             # 랜덤 지연 추가
)
```

---

## 4. 단계별 상세

### 4.1 STEP 1: 뉴스 데이터 조회

**파일 위치**: `celery_worker.py:237`

```python
all_news_data = graph_service.get_all_news_by_location(location, start_date, end_date)
```

**Neo4j Cypher 쿼리**:

```cypher
MATCH (l:Location {name: $location})<-[:IS_IN_LOCATION]-(n:News)-[:HAS_CATEGORY]->(c:Category)
WHERE n.published_at >= $start_date AND n.published_at < $end_date
RETURN n.news_id, n.title, n.content, n.published_at, c.name as category
ORDER BY n.published_at DESC
```

**결과 처리**:
- 데이터 없음 → `SKIPPED` 상태 반환
- 데이터 있음 → 다음 단계 진행

---

### 4.2 STEP 2: Executive Summary 생성

**파일 위치**: `report_chain.py:219`

```
뉴스 데이터
    │
    ▼ _rank_news_by_trending()
    │   └─ Google API로 화제성 점수 측정 (병렬 10스레드)
    │   └─ 점수 높은 순 정렬
    ▼
Top 5 뉴스 선정 (TOP_N_EXECUTIVE = 5)
    │
    ▼ _expand_context_with_chroma()
    │   └─ ChromaDB에서 각 뉴스별 유사 문서 3개 검색
    │   └─ 벡터 임베딩 기반 의미론적 검색
    ▼
확장된 컨텍스트
    │
    ▼ LangChain + vLLM
    │   └─ 프롬프트: 헤드라인 브리핑 + 주요 동향
    │   └─ JSON 파싱 (최대 3회 재시도)
    ▼
ExecutiveSummary (Dict)
```

**출력 구조**:

```json
{
  "headline_briefing": "2-3문장 (100-150자) - 핵심 이슈 요약",
  "key_trends": "3-5문단 (300-500자) - 상황/배경/전망"
}
```

---

### 4.3 STEP 3: 병렬 카테고리 분석

**파일 위치**: `celery_worker.py:262-285`

```python
# Celery group으로 병렬 실행
for category_name in all_categories:
    category_news = [news for news in all_news_data if news['category'] == category_name]
    category_tasks.append(
        analyze_single_category.s(category_news, category_name)
    )

workflow = chain(
    group(*category_tasks),      # 모든 카테고리 동시 분석
    assemble_final_report.s(...) # 결과 조립
)
```

**각 카테고리 분석 (`report_chain.py:342`)**:

```
카테고리별 뉴스
    │
    ▼ _rank_news_by_trending()
    │   └─ 화제성 순 정렬
    ▼
Top 3 뉴스 선정 (TOP_N_CATEGORY = 3)
    │
    ▼ _expand_context_with_chroma()
    │   └─ 관련 문서 검색
    ▼
확장된 컨텍스트
    │
    ▼ LangChain + vLLM
    │   └─ 분야별 특화 프롬프트
    │   └─ 현황 → 심층 분석 → 전망 구조
    ▼
CategoricalAnalysis (Dict)
```

**출력 구조**:

```json
{
  "category": "경제",
  "analysis_text": "4-6문단 (500-800자) - 분야별 심층 분석"
}
```

---

### 4.4 STEP 4: 최종 조립

**파일 위치**: `celery_worker.py:120`

```python
final_report_json = {
    "location": location,
    "report_type": report_type,
    "generated_at": datetime.now().isoformat(),
    "executive_summary": executive_summary,
    "categorical_analysis": successful_analyses,
    "metadata": {
        "total_categories": len(analysis_results),
        "successful_categories": len(successful_analyses),
        "report_quality": "complete"
    }
}
```

**실패 처리**:
- 하나라도 실패한 카테고리 → 전체 워크플로우 재시도
- 모두 성공 → FINO 서버로 전송

---

## 5. 화제성 랭킹 시스템

**파일 위치**: `report_chain.py:22`

### 5.1 동작 흐름

```
┌─────────────────────────────────────────────────────────┐
│               _rank_news_by_trending()                  │
└─────────────────────────┬───────────────────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    ▼                     ▼                     ▼
┌────────┐          ┌────────┐           ┌────────┐
│ 뉴스1  │          │ 뉴스2  │           │ 뉴스N  │
│ 제목   │          │ 제목   │           │ 제목   │
└───┬────┘          └───┬────┘           └───┬────┘
    │ ThreadPool        │                    │
    │ (10 workers)      │                    │
    ▼                   ▼                    ▼
┌────────────────────────────────────────────────────┐
│           Google Custom Search API                  │
│    검색 결과 수 = 화제성 점수                       │
└────────────────────────────────────────────────────┘
    │
    ▼ 점수 내림차순 정렬
┌────────────────────────────────────────────────────┐
│  [뉴스3: 1200점] [뉴스1: 800점] [뉴스2: 450점] ... │
└────────────────────────────────────────────────────┘
```

### 5.2 설정 값

```python
MAX_API_WORKERS = 10  # 병렬 API 호출 스레드 수
```

### 5.3 에러 처리

- Rate Limit 도달 시 → 0점 반환 및 경고 로그
- 전체 성공률 50% 미만 시 → 경고 로그 출력

---

## 6. RAG 컨텍스트 확장

**파일 위치**: `report_chain.py:75`

### 6.1 동작 흐름

```
┌─────────────────────────────────────────────────────────┐
│            _expand_context_with_chroma()                │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Top N 뉴스 제목들                                       │
│   ["데이터센터 유치...", "관광객 증가...", ...]         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼ SentenceTransformers 임베딩
┌─────────────────────────────────────────────────────────┐
│ Query Vectors: [[0.12, 0.34, ...], [0.56, 0.78, ...]]  │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼ ChromaDB 유사도 검색
┌─────────────────────────────────────────────────────────┐
│ 각 뉴스별 관련 문서 3개씩 검색                          │
│   - 원본 뉴스 자체는 제외 (self_excluded)               │
│   - 거리 기준 정렬                                      │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 확장된 컨텍스트 (예시)                                  │
│                                                         │
│ ### 주요 뉴스 #1: 데이터센터 유치 성공                  │
│   - 관련 뉴스: IT 기업 유치 현황 (내용: ...)            │
│   - 관련 뉴스: 일자리 창출 효과 (내용: ...)             │
│                                                         │
│ ### 주요 뉴스 #2: 관광객 증가 추세                      │
│   - 관련 뉴스: 숙박업 매출 상승 (내용: ...)             │
└─────────────────────────────────────────────────────────┘
```

### 6.2 설정 값

```python
VECTOR_SEARCH_CANDIDATES = 3  # 뉴스당 검색할 관련 문서 수
```

---

## 7. 재시도 전략

### 7.1 재시도 흐름

```
실패 발생
    │
    ▼ 1차 재시도 (60초 후)
    │
    ▼ 2차 재시도 (120초 후) ← 지수 백오프
    │
    ▼ 3차 재시도 (240초 후)
    │
    ▼ 최대 300초까지
    │
    └─ 최종 실패 시 상위 Task로 예외 전파
```

### 7.2 설정 코드

```python
@celery_app.task(
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,        # 지수 백오프 활성화
    retry_backoff_max=300,     # 최대 5분
    retry_jitter=True          # 랜덤 지연 추가 (Thundering Herd 방지)
)
```

---

## 8. 스케줄링 (Celery Beat)

### 8.1 스케줄 설정

```python
celery_app.conf.beat_schedule = {
    'run-weekly-dispatcher': {
        'task': 'reports.dispatch_weekly_reports',
        'schedule': crontab(hour=4, minute=0, day_of_week='monday'),
    },
    'run-monthly-dispatcher': {
        'task': 'reports.dispatch_monthly_reports',
        'schedule': crontab(hour=5, minute=0, day_of_month='1'),
    },
}
```

### 8.2 스케줄 상세

| 스케줄 | Task | 실행 시점 | 날짜 범위 |
|--------|------|----------|----------|
| 주간 리포트 | `dispatch_weekly_reports` | 매주 월요일 04:00 | 지난주 월~일 |
| 월간 리포트 | `dispatch_monthly_reports` | 매월 1일 05:00 | 지난달 전체 |

### 8.3 날짜 계산 로직

```python
# 주간 (지난주 월요일 00:00 ~ 이번주 월요일 00:00)
today = datetime.now()
last_week_end = today.replace(hour=0, minute=0) - timedelta(days=today.weekday())
last_week_start = last_week_end - timedelta(days=7)

# 월간 (지난달 1일 00:00 ~ 이번달 1일 00:00)
last_month_end = today.replace(day=1, hour=0, minute=0)
last_month_start = (last_month_end - timedelta(days=1)).replace(day=1)
```

---

## 9. 최종 리포트 구조

```json
{
  "location": "춘천",
  "report_type": "weekly",
  "generated_at": "2025-01-12T04:30:00",
  "executive_summary": {
    "headline_briefing": "핵심 이슈 2-3문장...",
    "key_trends": "주요 동향 3-5문단..."
  },
  "categorical_analysis": [
    {
      "category": "경제",
      "analysis_text": "경제 분야 심층 분석..."
    },
    {
      "category": "사회",
      "analysis_text": "사회 분야 심층 분석..."
    }
  ],
  "metadata": {
    "total_categories": 5,
    "successful_categories": 5,
    "report_quality": "complete"
  }
}
```

---

## 관련 문서

- [ARC-001 시스템 아키텍처](./ARC-001_SYSTEM_ARCHITECTURE.md)
- [DEV-001 코딩 컨벤션](./DEV-001_CODING_CONVENTION.md)
- [DEV-002 로그 규칙](./DEV-002_LOGGING_RULES.md)
