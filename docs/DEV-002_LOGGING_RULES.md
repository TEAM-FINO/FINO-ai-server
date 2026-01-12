# 로그 규칙

> **문서 번호**: DEV-002
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

이 문서는 FINO AI Server 프로젝트의 로깅 규칙을 정의합니다. 일관된 로그 포맷과 적절한 로그 레벨을 사용하여 운영 및 디버깅 효율성을 높이는 것이 목표입니다.

---

## 2. 로그 레벨

### 2.1 레벨별 사용 기준

| 레벨 | 사용 상황 | 예시 |
|------|----------|------|
| `CRITICAL` | 시스템 전체에 영향을 미치는 치명적 오류 | DB 연결 완전 실패, 필수 서비스 불능 |
| `ERROR` | 즉시 대응 필요, 작업 실패 | Task 최종 실패, API 호출 실패 |
| `WARNING` | 잠재적 문제, 재시도 발생 | Rate Limit, 파싱 재시도 |
| `INFO` | 주요 이벤트, 작업 진행 상황 | 워크플로우 시작/완료, Task 디스패치 |
| `DEBUG` | 디버깅 정보, 상세 데이터 | 쿼리 파라미터, 중간 결과값 |

### 2.2 환경별 기본 레벨

| 환경 | 기본 레벨 | 설정 |
|------|----------|------|
| Development | DEBUG | `LOG_LEVEL=DEBUG` |
| Staging | INFO | `LOG_LEVEL=INFO` |
| Production | INFO | `LOG_LEVEL=INFO` |

---

## 3. 로그 포맷

### 3.1 Development 포맷

```
[시간] [레벨] [파일명:라인번호] 메시지
```

**예시**:
```
[2025-01-13 10:30:45] [INFO] [celery_worker.py:231] Workflow started for '춘천' (weekly)
[2025-01-13 10:30:46] [DEBUG] [report_chain.py:27] Ranking 15 news items using Google API
[2025-01-13 10:30:50] [ERROR] [report_chain.py:40] Google API rate limit hit for '데이터센터 유치'
```

### 3.2 Production 포맷 (JSON)

```json
{
  "timestamp": "2025-01-13T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.celery_worker",
  "message": "Workflow started for '춘천' (weekly)",
  "task_id": "abc123",
  "location": "춘천",
  "report_type": "weekly"
}
```

---

## 4. 로그 작성 규칙

### 4.1 기본 규칙

```python
import logging

logger = logging.getLogger(__name__)

# Good - 구조화된 로그
logger.info(f"[{task_id}] Workflow started for '{location}' ({report_type})")

# Good - 키-값 형식
logger.info(f"Context stats: retrieved={total}, added={added}, length={len(ctx)}")

# Bad - 불명확한 로그
logger.info("Starting...")
logger.info("Done")
```

### 4.2 성공/실패 표시

```python
# 성공 시
logger.info(f"✓ Category '{category_name}' analysis completed successfully.")
logger.info(f"✓ Weekly dispatch completed for all {count} locations.")

# 실패 시
logger.error(f"✗ Category '{category_name}' analysis failed: {e}")
logger.error(f"✗ Failed to dispatch weekly report for '{location}': {e}")
```

### 4.3 Task 로그 패턴

```python
@celery_app.task(bind=True, name='reports.analyze_category')
def analyze_single_category(self, category_news: list, category_name: str):
    task_id = self.request.id
    attempt = self.request.retries + 1
    max_attempts = self.max_retries + 1

    # 시작 로그
    logger.info(
        f"[{task_id}] Analyzing category '{category_name}' "
        f"(attempt {attempt}/{max_attempts})"
    )

    try:
        result = process(category_news)

        # 성공 로그
        logger.info(f"[{task_id}] ✓ Category '{category_name}' completed")
        return result

    except Exception as e:
        # 실패 로그
        logger.error(
            f"[{task_id}] ✗ Category '{category_name}' failed "
            f"(attempt {attempt}/{max_attempts}): {e}",
            exc_info=(attempt == max_attempts)  # 마지막 시도에만 스택 트레이스
        )
        raise
```

---

## 5. 필수 로그 항목

### 5.1 워크플로우 로그

| 시점 | 레벨 | 필수 정보 |
|------|------|----------|
| 시작 | INFO | task_id, location, report_type, attempt |
| 뉴스 조회 | INFO | 조회된 뉴스 수, location |
| Executive Summary | INFO | 생성 성공/실패 |
| 카테고리 분석 | INFO | 카테고리 수, 카테고리 목록 |
| 완료 | INFO | 성공 카테고리 수, 실패 카테고리 수 |
| 실패 | ERROR | 에러 메시지, 스택 트레이스 |

### 5.2 API 로그

| 시점 | 레벨 | 필수 정보 |
|------|------|----------|
| 요청 수신 | INFO | endpoint, method, 주요 파라미터 |
| 처리 완료 | INFO | 응답 상태, 처리 시간 |
| 에러 발생 | ERROR | 에러 타입, 메시지 |

### 5.3 외부 API 로그

| 시점 | 레벨 | 필수 정보 |
|------|------|----------|
| 호출 | DEBUG | API 이름, 요청 파라미터 |
| 성공 | DEBUG | 응답 요약 |
| 실패 | WARNING/ERROR | 에러 코드, 메시지 |
| Rate Limit | WARNING | API 이름, 남은 쿼터 |

---

## 6. 로그 예시

### 6.1 워크플로우 전체 로그

```
[INFO] [celery_worker.py:231] [abc123] Workflow started for '춘천' (weekly) - Attempt 1/3
[INFO] [celery_worker.py:251] [abc123] Retrieved 45 news items for '춘천'
[INFO] [report_chain.py:221] Executive Summary Generation.
[INFO] [report_chain.py:27] Ranking 45 news items using Google API.
[INFO] [report_chain.py:55] Successfully scored 43/45 news items.
[INFO] [report_chain.py:80] Expanding context for 5 top news items from ChromaDB.
[INFO] [report_chain.py:144] Context stats: retrieved=15, added=12, self_excluded=3, final_length=2450 chars
[INFO] [report_chain.py:323] ✓ Executive summary parsed successfully.
[INFO] [celery_worker.py:274] [abc123] Dispatching 5 category analysis tasks for categories: ['경제', '사회', '문화', '정치', '환경']
[INFO] [celery_worker.py:89] ✓ Category '경제' analysis completed successfully.
[INFO] [celery_worker.py:89] ✓ Category '사회' analysis completed successfully.
[INFO] [celery_worker.py:89] ✓ Category '문화' analysis completed successfully.
[INFO] [celery_worker.py:89] ✓ Category '정치' analysis completed successfully.
[INFO] [celery_worker.py:89] ✓ Category '환경' analysis completed successfully.
[INFO] [celery_worker.py:156] ✓ All 5 categories analyzed successfully.
[INFO] [celery_worker.py:178] ✓ Successfully sent complete report for '춘천'.
```

### 6.2 에러 로그

```
[WARNING] [report_chain.py:328] Parsing failed (Attempt 1/3): Invalid JSON format
[WARNING] [report_chain.py:328] Parsing failed (Attempt 2/3): Missing required fields
[ERROR] [report_chain.py:333] All parsing attempts failed for executive summary.
[ERROR] [celery_worker.py:102] ✗ Category '경제' analysis failed (attempt 3/4): LLM timeout
Traceback (most recent call last):
  File "/app/app/celery_worker.py", line 87, in analyze_single_category
    analysis_result = generate_categorical_analysis(category_news, category_name)
  File "/app/app/chains/report_chain.py", line 453, in generate_categorical_analysis
    raw_output = chain.invoke({"context": context, "category_name": category_name})
TimeoutError: LLM request timed out after 60 seconds
```

---

## 7. 금지 사항

### 7.1 절대 금지

```python
# [X] 민감 정보 로깅
logger.info(f"API Key: {settings.GOOGLE_API_KEY}")  # 금지
logger.info(f"Password: {password}")                 # 금지
logger.debug(f"Token: {auth_token}")                 # 금지

# [X] print() 문 사용
print("Debug message")  # 금지

# [X] 의미 없는 로그
logger.info("Here")     # 금지
logger.info("Done")     # 금지
logger.info("OK")       # 금지

# [X] 과도한 로그 (루프 내 반복 로그)
for news in news_list:
    logger.debug(f"Processing: {news}")  # 금지 (수백 건 로그 발생)
```

### 7.2 주의 사항

```python
# [!] 대용량 데이터 로깅 주의
logger.debug(f"Full response: {large_response}")  # 주의 - 필요시 축약

# 권장
logger.debug(f"Response preview: {str(large_response)[:200]}...")

# [!] 스택 트레이스는 마지막 시도에만
logger.error(f"Failed: {e}", exc_info=(attempt == max_attempts))
```

---

## 8. 로깅 설정

### 8.1 logging_config.py

```python
import logging
from app.core.config import settings

def setup_logging():
    """애플리케이션 로깅을 설정합니다."""

    log_level = getattr(logging, settings.LOG_LEVEL.upper())

    if settings.ENV_MODE == "development":
        # 개발 환경: 상세 포맷
        log_format = "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
    else:
        # 프로덕션 환경: JSON 포맷
        # python-json-logger 사용
        log_format = "%(timestamp)s %(level)s %(name)s %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format
    )
```

### 8.2 환경 변수

```bash
# .env
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
ENV_MODE=development    # development, production
ENABLE_FILE_LOGGING=false
```

---

## 9. 모니터링 연동

### 9.1 Flower (Celery 모니터링)

```
URL: http://localhost:5555
기능: Task 상태, Worker 상태, 실패 Task 확인
```

### 9.2 로그 파일

```bash
# 파일 로깅 활성화 시
/var/log/fino-ai/app.log
/var/log/fino-ai/celery-worker.log
/var/log/fino-ai/celery-beat.log
```

---

## 관련 문서

- [DEV-001 코딩 컨벤션](./DEV-001_CODING_CONVENTION.md)
- [OPS-003 모니터링](./OPS-003_MONITORING.md)
- [ARC-001 시스템 아키텍처](./ARC-001_SYSTEM_ARCHITECTURE.md)
