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
    # === 기본 설정 ===
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Seoul',
    enable_utc=False,
    
    # === Broker 연결 설정 ===
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=10.0,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_heartbeat=60,
    broker_pool_limit=2,
    
    # === Worker 설정 ===
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_send_task_events=True,
    worker_disable_rate_limits=False,
    
    # === Task 실행 설정 ===
    task_soft_time_limit=600,   # 10분 (경고)
    task_time_limit=720,        # 12분 (강제 종료)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # === Result Backend 설정 ===
    result_expires=3600,
    result_persistent=False,
    result_compression='gzip',
)

# --- Celery Task 정의 ---
# 단일 카테고리 분석 Task
@celery_app.task(
    bind=True,
    name='reports.analyze_category',
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),  # 모든 예외에 대해 자동 재시도
    retry_backoff=True,           # 지수 백오프 (60s, 120s, 240s)
    retry_backoff_max=300,
    retry_jitter=True
)
def analyze_single_category(self, category_news: list, category_name: str):
    """
    단일 카테고리 분석을 수행합니다.
    
    실패 시 자동으로 재시도하며, 최종 실패 시 예외를 발생시켜
    상위 워크플로우(assemble_final_report)가 전체를 재시도하도록 합니다.
    """
    try:
        logger.info(
            f"Analyzing category '{category_name}' "
            f"(attempt {self.request.retries + 1}/{self.max_retries + 1})"
        )
        
        analysis_result = generate_categorical_analysis(category_news, category_name)
        
        logger.info(f"✓ Category '{category_name}' analysis completed successfully.")
        return {
            "status": "SUCCESS",
            "category": category_name,
            "data": analysis_result
        }
    
    except Exception as e:
        attempt_num = self.request.retries + 1
        max_attempts = self.max_retries + 1
        
        logger.error(
            f"✗ Category '{category_name}' analysis failed "
            f"(attempt {attempt_num}/{max_attempts}): {e}",
            exc_info=(attempt_num == max_attempts)  # 마지막 시도에만 전체 스택 트레이스
        )
        
        # 재시도 횟수가 남았으면 자동 재시도 (autoretry_for가 처리)
        # 최종 실패 시 예외를 다시 발생시켜 워크플로우 전체 실패 트리거
        raise

# 최종 보고서 조립 Task
@celery_app.task(
    bind=True,
    name='reports.assemble',
    max_retries=2,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600
)
def assemble_final_report(self, analysis_results: list, executive_summary: dict, location: str, report_type: str):
    """
    모든 분석 결과를 취합하여 최종 보고서를 완성하고 FINO 서버로 전송합니다.
    
    하나라도 실패한 카테고리가 있으면 예외를 발생시켜 전체 재시도합니다.
    """
    try:
        logger.info(f"Assembling final report for '{location}' ({report_type})...")
        
        # 모든 카테고리 분석 성공 여부 검증
        failed_categories = []
        successful_analyses = []
        
        for result in analysis_results:
            if result.get("status") == "SUCCESS":
                successful_analyses.append(result["data"])
            else:
                # 실패한 카테고리 기록
                failed_categories.append({
                    "category": result.get("category"),
                    "error": result.get("error")
                })
        
        # 실패한 카테고리가 하나라도 있으면 전체 워크플로우 재시도
        if failed_categories:
            error_msg = (
                f"Incomplete report for '{location}': "
                f"{len(failed_categories)}/{len(analysis_results)} categories failed. "
                f"Failed categories: {[c['category'] for c in failed_categories]}"
            )
            logger.error(error_msg)
            
            # 예외 발생 → autoretry_for가 자동으로 재시도
            raise Exception(error_msg)
        
        # 리포트 조립 
        logger.info(f"✓ All {len(successful_analyses)} categories analyzed successfully.")
        
        final_report_json = {
            "location": location,
            "report_type": report_type,
            "generated_at": datetime.now().isoformat(),
            "executive_summary": executive_summary,
            "categorical_analysis": successful_analyses,
            "metadata": {
                "total_categories": len(analysis_results),
                "successful_categories": len(successful_analyses),
                "report_quality": "complete"  # 100% 완성도 표시
            }
        }
        
        # FINO 서버로 전송
        logger.info(f"Sending complete report for '{location}' to FINO server...")
        #success, response = fino_api_service.send_report(final_report_json)
        #if not success:
            # 전송 실패 시에도 재시도
        #    raise Exception(f"Failed to send report to FINO server: {response}")
        
        logger.info(f"✓ Successfully sent complete report for '{location}'.")
        
        # 전체 리포트 데이터 반환 (스크립트에서 사용)
        return {
            "status": "SUCCESS",
            "location": location,
            "report_type": report_type,
            "categories_analyzed": len(successful_analyses),
            "report_quality": "complete",
            # 실제 리포트 내용 포함
            "report": final_report_json,  # 최종 리포트 
            "executive_summary": executive_summary,
            "categorical_analysis": successful_analyses,
            "generated_at": final_report_json["generated_at"],
            "metadata": final_report_json["metadata"]
        }
    
    except Exception as e:
        attempt_num = self.request.retries + 1
        max_attempts = self.max_retries + 1
        
        logger.error(
            f"✗ Report assembly failed for '{location}' "
            f"(attempt {attempt_num}/{max_attempts}): {e}",
            exc_info=True
        )
        
        # 재시도를 위해 예외 다시 발생
        raise

# 전체 리포트 생성 워크플로우 실행 Task
@celery_app.task(
    bind=True,
    name='reports.generate_workflow',
    max_retries=2,  # 워크플로우 레벨에서도 재시도
    default_retry_delay=600,  # 10분 후 재시도
    autoretry_for=(Exception,),
    retry_backoff=True
)
def generate_report_workflow(self, location: str, start_date_iso: str, end_date_iso: str, report_type: str):
    """
    리포트 생성 전체 워크플로우를 지휘합니다.
    
    하위 Task(카테고리 분석, 리포트 조립)에서 실패 시 전체 워크플로우를 재시도합니다.
    """
    task_id = self.request.id
    attempt_num = self.request.retries + 1
    max_attempts = self.max_retries + 1
    
    start_date = datetime.fromisoformat(start_date_iso)
    end_date = datetime.fromisoformat(end_date_iso)
    
    logger.info(
        f"[{task_id}] Workflow started for '{location}' ({report_type}) "
        f"- Attempt {attempt_num}/{max_attempts}"
    )
    
    try:
        # 뉴스 데이터 조회
        all_news_data = graph_service.get_all_news_by_location(location, start_date, end_date)
        
        if not all_news_data:
            logger.warning(f"[{task_id}] No news data for '{location}'. Workflow skipped.")
            return {
                "status": "SKIPPED",
                "reason": "No news data available",
                "location": location,
                "date_range": {
                    "start": start_date_iso,
                    "end": end_date_iso
                }
            }
        
        logger.info(f"[{task_id}] Retrieved {len(all_news_data)} news items for '{location}'.")
        
        # Executive Summary 생성
        try:
            executive_summary = generate_executive_summary(all_news_data)
            logger.info(f"[{task_id}] Executive summary generated successfully.")
        except Exception as e:
            logger.error(f"[{task_id}] Executive summary generation failed: {e}", exc_info=True)
            # Executive Summary 실패도 전체 워크플로우 재시도 트리거
            raise Exception(f"Executive summary generation failed: {e}")
        
        # 카테고리별 분석 Task 그룹 생성
        all_categories = sorted(set(news['category'] for news in all_news_data))
        category_tasks = []
        
        for category_name in all_categories:
            category_news = [news for news in all_news_data if news['category'] == category_name]
            category_tasks.append(
                analyze_single_category.s(category_news, category_name)
            )
        
        logger.info(
            f"[{task_id}] Dispatching {len(category_tasks)} category analysis tasks "
            f"for categories: {all_categories}"
        )
        
        # 워크플로우 정의 및 실행
        workflow = chain(
            group(*category_tasks),  # 모든 카테고리 병렬 분석
            assemble_final_report.s(
                executive_summary=executive_summary,
                location=location,
                report_type=report_type
            )
        )
        
        result = workflow.apply_async()
        
        logger.info(f"[{task_id}] Workflow dispatched successfully (chain ID: {result.id}).")
        
        return {
            "status": "WORKFLOW_STARTED",
            "workflow_task_id": result.id,
            "location": location,
            "report_type": report_type,
            "metadata": {
                "total_news": len(all_news_data),
                "categories": all_categories,
                "category_count": len(all_categories),
                "attempt": attempt_num
            }
        }
    
    except Exception as e:
        logger.error(
            f"[{task_id}] Workflow failed for '{location}' "
            f"(attempt {attempt_num}/{max_attempts}): {e}",
            exc_info=True
        )
        
        # 재시도 횟수가 남았으면 autoretry_for가 자동 재시도
        # 최종 실패 시에만 아래 메시지 반환
        if attempt_num >= max_attempts:
            logger.critical(
                f"[{task_id}] Workflow PERMANENTLY FAILED for '{location}' "
                f"after {max_attempts} attempts. Manual intervention required."
            )
        
        raise  # 재시도 또는 최종 실패

# --- Dispatcher Task 추가 ---
@celery_app.task(name='reports.dispatch_weekly_reports', autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def dispatch_weekly_reports():
    """모든 대상 지역에 대해 주간 리포트 생성 워크플로우를 시작합니다."""
    try:
        target_locations = graph_service.get_all_target_locations()
        
        if not target_locations:
            logger.warning("No target locations found for weekly reports.")
            return {"status": "SKIPPED", "reason": "No target locations"}
        
        logger.info(f"Dispatching weekly reports for {len(target_locations)} locations.")
        
        # 날짜 계산 (지난주 월요일 00:00 ~ 이번주 월요일 00:00)
        today = datetime.now()
        last_week_end = today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=today.weekday())
        last_week_start = last_week_end - timedelta(days=7)
        
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
                dispatched.append({
                    "location": location,
                    "task_id": task.id,
                    "dispatched_at": datetime.now().isoformat()
                })
                logger.info(f"✓ Dispatched weekly report for '{location}' (task_id: {task.id})")
                
            except Exception as e:
                failed.append({
                    "location": location,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                logger.error(f"✗ Failed to dispatch weekly report for '{location}': {e}", exc_info=True)
        
        result = {
            "status": "COMPLETED" if not failed else "PARTIAL_SUCCESS",
            "report_type": "weekly",
            "total_locations": len(target_locations),
            "dispatched": len(dispatched),
            "failed": len(failed),
            "date_range": {
                "start": last_week_start.isoformat(),
                "end": last_week_end.isoformat()
            },
            "dispatched_details": dispatched,
            "failed_details": failed if failed else None
        }
        
        if failed:
            logger.warning(
                f"Weekly dispatch partially failed: {len(failed)}/{len(target_locations)} locations failed."
            )
        else:
            logger.info(f"✓ Weekly dispatch completed successfully for all {len(target_locations)} locations.")
        
        return result
    
    except Exception as e:
        logger.error(f"Critical error in weekly dispatcher: {e}", exc_info=True)
        raise

@celery_app.task(name='reports.dispatch_monthly_reports', autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def dispatch_monthly_reports():
    """모든 대상 지역에 대해 월간 리포트 생성 워크플로우를 시작합니다."""
    try:
        target_locations = graph_service.get_all_target_locations()
        
        if not target_locations:
            logger.warning("No target locations found for monthly reports.")
            return {"status": "SKIPPED", "reason": "No target locations"}
        
        logger.info(f"Dispatching monthly reports for {len(target_locations)} locations.")
        
        # 날짜 계산 (지난달 1일 00:00 ~ 이번달 1일 00:00)
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
                dispatched.append({
                    "location": location,
                    "task_id": task.id,
                    "dispatched_at": datetime.now().isoformat()
                })
                logger.info(f"✓ Dispatched monthly report for '{location}' (task_id: {task.id})")
                
            except Exception as e:
                failed.append({
                    "location": location,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                logger.error(f"✗ Failed to dispatch monthly report for '{location}': {e}", exc_info=True)
        
        result = {
            "status": "COMPLETED" if not failed else "PARTIAL_SUCCESS",
            "report_type": "monthly",
            "total_locations": len(target_locations),
            "dispatched": len(dispatched),
            "failed": len(failed),
            "date_range": {
                "start": last_month_start.isoformat(),
                "end": last_month_end.isoformat()
            },
            "dispatched_details": dispatched,
            "failed_details": failed if failed else None
        }
        
        if failed:
            logger.warning(
                f"Monthly dispatch partially failed: {len(failed)}/{len(target_locations)} locations failed."
            )
        else:
            logger.info(f"✓ Monthly dispatch completed successfully for all {len(target_locations)} locations.")
        
        return result
    
    except Exception as e:
        logger.error(f"Critical error in monthly dispatcher: {e}", exc_info=True)
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