import logging
from datetime import datetime, timedelta
from celery import Celery, group, chain
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
from celery.utils.log import get_task_logger
from app.core.config import settings
from app.services.graph_service import graph_service
from app.services.fino_api_service import fino_api_service
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
    accept_content=['json'],
    timezone='Asia/Seoul',
    enable_utc=False,
)

# --- Celery Task 정의 ---
# 단일 카테고리 분석 Task
@celery_app.task(bind=True, name='reports.analyze_category', max_retries=3, default_retry_delay=60)
def analyze_single_category(self, category_news: list, category_name: str):
    """단일 카테고리 분석을 수행하고, 실패 시 자동으로 일정 횟수 재시도합니다."""
    try:
        analysis_result = generate_categorical_analysis(category_news, category_name)
        return {"status": "SUCCESS", "category": category_name, "data": analysis_result}
    except Exception as e:
        logger.error(f"Final failure for category '{category_name}' after retries.", exc_info=True)
        # 재시도에 최종 실패하면, 에러를 일으키는 대신 실패 상태를 반환합니다.
        return {"status": "FAILURE", "category": category_name, "error": str(e)}

# 최종 보고서 조립 Task
@celery_app.task(bind=True, name='reports.assemble', max_retries=2, default_retry_delay=300)
def assemble_final_report(self, analysis_results: list, executive_summary: dict, location: str, report_type: str):
    """모든 분석 결과를 취합하여 최종 보고서 JSON을 완성하고 FINO 서버로 전송합니다."""
    try:
        logger.info(f"Assembling final report for {location} ({report_type}).")
        
        final_report_json = {
            "location": location,
            "report_type": report_type,
            "generated_at": datetime.now().isoformat(),
            "executive_summary": executive_summary,
            "categorical_analysis": analysis_results
        }
        
        # 전송 로직
        logger.info(f"Sending final report for {location} to FINO main server...")
        success, response = fino_api_service.send_report(final_report_json)

        if not success:
            # 전송에 실패하면 Celery Task를 재시도하도록 에러를 발생시킵니다.
            raise Exception(f"Failed to send report to FINO Server: {response}")

        logger.info(f"Successfully assembled and sent report for {location}.")
        return { "status": "SUCCESS", "location": location, "report_type": report_type, "report": final_report_json }

    except Exception as e:
        logger.error(f"Error in assemble_final_report for {location}: {e}", exc_info=True)
        # 재시도 로직
        raise self.retry(exc=e)

# 전체 리포트 생성 워크플로우 실행 Task
@celery_app.task(bind=True, name='reports.generate_workflow')
def generate_report_workflow(self, location: str, start_date_iso: str, end_date_iso: str, report_type: str):
    """리포트 생성 전체 워크플로우를 지휘합니다."""
    task_id = self.request.id
    start_date = datetime.fromisoformat(start_date_iso)
    end_date = datetime.fromisoformat(end_date_iso)
    logger.info(f"[{task_id}] Workflow started for '{location}' ({report_type}).")

    all_news_data = graph_service.get_all_news_by_location(location, start_date, end_date)
    if not all_news_data:
        logger.warning(f"[{task_id}] No news data. Workflow skipped.")
        return {"status": "SKIPPED", "reason": "No news data", "location": location}

    # 지역 전체 핵심 이슈 분석 생성
    try:
        executive_summary = generate_executive_summary(all_news_data)
    except Exception as e:
        logger.error(f"[{task_id}] Failed to generate executive summary: {e}", exc_info=True)
        return {"status": "FAILED", "reason": "Executive summary generation failed", "error": str(e)}

    # 모든 카테고리에 대한 '하위 분석 Task' 그룹 및 분야별 심층 분석 생성 
    all_categories = sorted(list(set(news['category'] for news in all_news_data)))
    category_tasks = []
    for category_name in all_categories:
        category_news = [news for news in all_news_data if news['category'] == category_name]
        category_tasks.append(analyze_single_category.s(category_news, category_name)) # signature를 사용하여 Task와 인자를 미리 정의

    # 워크플로우 정의
    workflow = chain(
        group(category_tasks),
        assemble_final_report.s(executive_summary=executive_summary, location=location, report_type=report_type)
    )
    
    # 워크플로우 실행
    result = workflow.apply_async()
    
    logger.info(f"[{task_id}] Dispatched workflow with chain ID: {result.id}")
    
    return {
        "status": "WORKFLOW_STARTED",
        "workflow_task_id": result.id, # 하위 워크플로우 추적 ID 반환
        "location": location,
        "report_type": report_type,
    }

# --- Dispatcher Task 추가 ---
@celery_app.task(name='reports.dispatch_weekly_reports')
def dispatch_weekly_reports():
    """모든 대상 지역에 대해 주간 리포트 생성 워크플로우를 시작합니다."""
    try:
        target_locations = graph_service.get_all_target_locations()
        logger.info(f"Dispatching weekly reports for {len(target_locations)} locations: {target_locations}")
        
        if not target_locations:
            logger.warning("No target locations found for weekly reports.")
            return {"status": "SKIPPED", "reason": "No target locations"}
        
        today = datetime.now()
        last_week_end = today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=today.weekday())
        last_week_start = last_week_end - timedelta(days=7)
        
        # 부분 실패 추적
        dispatched = []
        failed = []
        
        for location in target_locations:
            try:
                task = generate_report_workflow.delay(
                    location, 
                    last_week_start.isoformat(), 
                    last_week_end.isoformat(), 
                    'weekly'
                )
                dispatched.append({"location": location, "task_id": task.id})
                logger.info(f"✓ Dispatched weekly report for '{location}' (task_id: {task.id})")
            except Exception as e:
                failed.append({"location": location, "error": str(e)})
                logger.error(f"✗ Failed to dispatch weekly report for '{location}': {e}", exc_info=True)
        
        result = {
            "status": "COMPLETED" if not failed else "PARTIAL_SUCCESS",
            "total": len(target_locations),
            "dispatched": len(dispatched),
            "failed": len(failed),
            "dispatched_locations": [d["location"] for d in dispatched],
            "failed_locations": [f["location"] for f in failed]
        }
        
        if failed:
            logger.warning(f"Weekly dispatch partially failed: {len(failed)}/{len(target_locations)} locations failed.")
        
        return result
        
    except Exception as e:
        logger.error(f"Critical error in dispatch_weekly_reports: {e}", exc_info=True)
        raise

@celery_app.task(name='reports.dispatch_monthly_reports')
def dispatch_monthly_reports():
    """모든 대상 지역에 대해 월간 리포트 생성 워크플로우를 시작합니다."""
    try:
        target_locations = graph_service.get_all_target_locations()
        logger.info(f"Dispatching monthly reports for {len(target_locations)} locations: {target_locations}")
        
        if not target_locations:
            logger.warning("No target locations found for monthly reports.")
            return {"status": "SKIPPED", "reason": "No target locations"}
        
        today = datetime.now()
        last_month_end = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (last_month_end - timedelta(days=1)).replace(day=1)
        
        dispatched = []
        failed = []
        
        for location in target_locations:
            try:
                task = generate_report_workflow.delay(
                    location, 
                    last_month_start.isoformat(), 
                    last_month_end.isoformat(), 
                    'monthly'
                )
                dispatched.append({"location": location, "task_id": task.id})
                logger.info(f"✓ Dispatched monthly report for '{location}' (task_id: {task.id})")
            except Exception as e:
                failed.append({"location": location, "error": str(e)})
                logger.error(f"✗ Failed to dispatch monthly report for '{location}': {e}", exc_info=True)
        
        result = {
            "status": "COMPLETED" if not failed else "PARTIAL_SUCCESS",
            "total": len(target_locations),
            "dispatched": len(dispatched),
            "failed": len(failed),
            "dispatched_locations": [d["location"] for d in dispatched],
            "failed_locations": [f["location"] for f in failed]
        }
        
        if failed:
            logger.warning(f"Monthly dispatch partially failed: {len(failed)}/{len(target_locations)} locations failed.")
        
        return result
        
    except Exception as e:
        logger.error(f"Critical error in dispatch_monthly_reports: {e}", exc_info=True)
        raise

# --- Celery Beat 스케줄 설정 ---
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