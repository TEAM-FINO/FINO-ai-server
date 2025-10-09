import logging
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from celery.utils.log import get_task_logger
from app.core.config import settings
from app.services.graph_service import graph_service
from app.chains.report_chain import generate_executive_summary, generate_categorical_analysis

logger = get_task_logger(__name__)

# --- Celery Signal Handlers ---
@worker_process_init.connect
def init_services(**kwargs):
    print("Celery worker starting... Initializing services.")
    graph_service.connect()

@worker_process_shutdown.connect
def shutdown_services(**kwargs):
    print("Celery worker shutting down... Closing service connections.")
    graph_service.close()

# --- Celery App 설정 ---
celery_app = Celery('tasks', broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json']
)

# --- Celery Task 정의 ---
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_report_task(self, request_data: dict):
    try:
        task_id = self.request.id
        location = request_data.get('location')
        categories = request_data.get('categories', []) # categories는 리스트 형태
        
        logger.info(f"[{task_id}] Report generation task started for Location: {location}, Categories: {categories}")

        # 전체 뉴스 데이터 확보 
        logger.info(f"[{task_id}] Fetching all news data from Neo4j for '{location}'.")
        all_news_data = graph_service.get_all_news_by_location(location)
        if not all_news_data:
            logger.warning(f"[{task_id}] No news data found for '{location}'. Task aborted.")
            return {"status": "SUCCESS", "report": "해당 지역의 뉴스 데이터가 없어 리포트를 생성할 수 없습니다."}

        # 최종 보고서의 각 파트를 담을 리스트
        report_parts = []

        # '지역 전체 핵심 이슈 분석' 생성 
        logger.info(f"[{task_id}] Generating executive summary.")
        executive_summary = generate_executive_summary(all_news_data)
        report_parts.append(executive_summary)

        # '분야별 상세 분석' 생성
        if categories: # 사용자가 카테고리를 선택한 경우에만 실행
            logger.info(f"[{task_id}] Generating categorical analysis for {categories}.")
            for category_name in categories:
                # 메모리에 있는 전체 데이터에서 해당 카테고리 뉴스만 필터링
                category_news = [news for news in all_news_data if news['category'] == category_name]
                
                if category_news:
                    analysis = generate_categorical_analysis(category_news, category_name)
                    report_parts.append(analysis)
                else:
                    logger.warning(f"[{task_id}] No news found for category '{category_name}'. Skipping.")

        # 최종 보고서 취합
        logger.info(f"[{task_id}] Combining all parts into the final report.")
        final_report = "\n\n".join(report_parts)
        
        logger.info(f"[{task_id}] Task completed successfully.")
        return {"status": "SUCCESS", "report": final_report}

    except Exception as e:
        logger.error(f"!!! Task {self.request.id} failed. Retrying...", exc_info=True)
        self.retry(exc=e)