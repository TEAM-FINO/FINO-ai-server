import requests
from app.core.config import settings

class FinoApiService:
    def __init__(self):
        # FINO 서버의 기본 URL과 헤더 설정
        self.base_url = settings.FINO_SERVER_URL
        self.headers = {"Content-Type": "application/json"}

    def send_report(self, report_data: dict):
        """
        생성된 리포트를 FINO 서버의 API 엔드포인트로 전송합니다.
        """
        # 임의 API 엔드포인트 경로
        endpoint = f"{self.base_url}/api/v1/reports" 
        
        try:
            print(f"Sending report to FINO Server at {endpoint}...")
            response = requests.post(endpoint, json=report_data, headers=self.headers, timeout=10)
            response.raise_for_status()  # 2xx 응답이 아니면 에러 발생
            print("Successfully sent report to FINO Server.")
            return True, response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send report to FINO Server: {e}")
            return False, str(e)

fino_api_service = FinoApiService()