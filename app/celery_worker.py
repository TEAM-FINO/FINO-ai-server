import traceback
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from app.core.config import settings
from app.services.graph_service import graph_service
from app.chains.report_chain import report_chain

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
        query = request_data.get('query')
        location = request_data.get('location')
        category = request_data.get('category')
        
        input_data = {"query": query, "location": location, "category": category}
        report = report_chain.invoke(input_data)
        return {"status": "SUCCESS", "report": report}
    except Exception as e:
        print(f"!!! Task failed, will retry. Error: {e}")
        self.retry(exc=e)