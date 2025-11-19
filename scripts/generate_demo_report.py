"""
Demo 리포트 생성 스크립트

실제 뉴스 데이터를 바탕으로 완전한 리포트를 생성합니다.
"""

import requests
import json
import time
from datetime import datetime

# 설정
API_BASE_URL = "http://localhost:8001/api/v1/reports"
HEADERS = {"Content-Type": "application/json"}

# 대상 지역 및 기간 설정
DEMO_CONFIGS = [
    {
        "location": "춘천",
        "start_date": "2025-10-27",
        "end_date": "2025-11-03",
        "report_type": "demo_weekly",
        "description": "춘천시 주간 리포트"
    },
    {
        "location": "원주",
        "start_date": "2025-10-27",
        "end_date": "2025-11-03",
        "report_type": "demo_weekly",
        "description": "원주시 주간 리포트"
    },
    {
        "location": "강릉",
        "start_date": "2025-10-27",
        "end_date": "2025-11-03",
        "report_type": "demo_weekly",
        "description": "강릉시 주간 리포트"
    }
]


def generate_report(config):
    """리포트 생성을 요청하고 Dispatcher Task ID를 반환합니다."""
    print(f"\n{'='*80}")
    print(f"📝 {config['description']}")
    print(f"{'='*80}")
    
    url = f"{API_BASE_URL}/generate/manual"
    payload = {
        "location": config["location"],
        "start_date": config["start_date"],
        "end_date": config["end_date"],
        "report_type": config["report_type"]
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        dispatcher_task_id = result.get("task_id")  # Dispatcher Task ID
        
        print(f"✅ 리포트 생성 요청 성공")
        print(f"  Dispatcher Task ID: {dispatcher_task_id}")
        
        return dispatcher_task_id  # Dispatcher ID 반환 (이것이 핵심!)
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 리포트 생성 요청 실패: {e}")
        return None


def wait_for_workflow_start(dispatcher_task_id, max_attempts=30, interval=2):
    """
    Dispatcher Task가 완료되어 Workflow Task ID를 반환할 때까지 대기합니다.
    """
    url = f"{API_BASE_URL}/status/{dispatcher_task_id}"
    
    print(f"\n⏳ Workflow 시작 대기 중... (최대 {max_attempts * interval}초)")
    
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            status = result.get("status")
            
            if attempt % 5 == 1:  # 10초마다 출력
                print(f"   [{attempt}/{max_attempts}] Dispatcher 상태: {status}")
            
            # COMPLETED 또는 PROCESSING 상태 확인 (둘 다 workflow_task_id 포함 가능)
            if status in ["COMPLETED", "PROCESSING"]:
                result_data = result.get("result", {})
                workflow_status = result_data.get("status")
                
                if workflow_status == "WORKFLOW_STARTED":
                    workflow_task_id = result_data.get("workflow_task_id")
                    if workflow_task_id:
                        print(f"✅ Workflow 시작됨! Chain ID: {workflow_task_id}")
                        return workflow_task_id
                
                elif workflow_status == "SKIPPED":
                    print(f"⚠️  워크플로우 스킵됨: {result_data.get('reason')}")
                    return None
            
            elif status == "FAILED":
                print(f"❌ Dispatcher 실패: {result}")
                return None
            
            time.sleep(interval)
        
        except requests.exceptions.RequestException as e:
            print(f"❌ 상태 확인 실패: {e}")
            return None
    
    print(f"⏰ 타임아웃: Workflow가 시작되지 않음")
    return None


def check_workflow_status(workflow_task_id, max_attempts=180, interval=5):
    """Workflow 완료를 대기하고 최종 결과를 반환합니다."""
    url = f"{API_BASE_URL}/status/{workflow_task_id}"
    
    print(f"\n⏳ 리포트 생성 진행 중... (최대 {max_attempts * interval}초)")
    
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            status = result.get("status")
            
            # 30초마다 출력
            if attempt % 6 == 1:
                print(f"   [{attempt}/{max_attempts}] Workflow 상태: {status}")
            
            if status == "COMPLETED":
                print(f"\n✅ 리포트 생성 완료!")
                return result.get("result")
            
            elif status == "FAILED":
                print(f"\n❌ 리포트 생성 실패")
                error_info = result.get("result", {})
                print(f"   오류: {error_info.get('error', 'Unknown error')}")
                return None
            
            elif status in ["PENDING", "STARTED", "PROCESSING", "RETRY"]:
                time.sleep(interval)
            
            else:
                print(f"\n⚠️  예상치 못한 상태: {status}")
                time.sleep(interval)
        
        except requests.exceptions.RequestException as e:
            print(f"\n❌ 상태 확인 실패: {e}")
            return None
    
    print(f"\n⏰ 타임아웃: {max_attempts * interval}초 내에 완료되지 않음")
    return None


def save_report(report_data, location):
    """생성된 리포트를 파일로 저장합니다."""
    if not report_data:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = "/var/log/fino-ai"
    filename = f"{log_dir}/demo_report_{location}_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 리포트 저장 완료: {filename}")
        
        # 간단한 요약 출력
        print(f"\n📊 리포트 요약:")
        print(f"   - 지역: {report_data.get('location')}")
        print(f"   - 유형: {report_data.get('report_type')}")
        print(f"   - 분석된 카테고리: {report_data.get('categories_analyzed')}")
        print(f"   - 품질: {report_data.get('report_quality', 'N/A')}")
        
    except Exception as e:
        print(f"\n❌ 파일 저장 실패: {e}")


def print_report_preview(report_data):
    """리포트의 미리보기를 출력합니다."""
    if not report_data:
        return
    
    print(f"\n{'='*80}")
    print(f"📄 리포트 미리보기")
    print(f"{'='*80}")
    
    # Executive Summary
    exec_summary = report_data.get("executive_summary", {})
    if exec_summary:
        print(f"\n## 헤드라인 브리핑")
        print(exec_summary.get("headline_briefing", ""))
        print(f"\n## 주요 동향")
        key_trends = exec_summary.get("key_trends", "")
        # key_trends가 리스트인 경우 처리
        if isinstance(key_trends, list):
            key_trends = "\n".join(key_trends)
        print(key_trends[:300] + "...")
    
    # Categorical Analysis
    categorical = report_data.get("categorical_analysis", [])
    if categorical:
        print(f"\n## 분야별 분석 ({len(categorical)}개 카테고리)")
        for i, analysis in enumerate(categorical, 1):
            category = analysis.get("category", "")
            text = analysis.get("analysis_text", "")
            print(f"\n{i}. {category}")
            print(f"   {str(text)[:150]}...")


def main():
    """메인 실행 함수"""
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "FINO AI 데모 리포트 생성기" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    
    # 사용자 선택
    print("\n생성할 리포트를 선택하세요:")
    for i, config in enumerate(DEMO_CONFIGS, 1):
        print(f"  {i}. {config['description']}")
    print(f"  0. 전체 생성 (모든 지역)")
    
    try:
        choice = input("\n선택 (0-3): ").strip()
        choice = int(choice)
    except (ValueError, KeyboardInterrupt):
        print("\n프로그램 종료")
        return
    
    # 선택에 따라 실행
    if choice == 0:
        selected_configs = DEMO_CONFIGS
    elif 1 <= choice <= len(DEMO_CONFIGS):
        selected_configs = [DEMO_CONFIGS[choice - 1]]
    else:
        print("❌ 잘못된 선택")
        return
    
    # 리포트 생성
    for config in selected_configs:
        # 1. 리포트 생성 요청 (Dispatcher Task ID 반환)
        dispatcher_task_id = generate_report(config)
        if not dispatcher_task_id:
            continue
        
        # 2. Workflow 시작 대기 (Workflow Task ID 획득)
        workflow_task_id = wait_for_workflow_start(dispatcher_task_id)
        if not workflow_task_id:
            continue
        
        # 3. Workflow 완료 대기
        report_data = check_workflow_status(workflow_task_id, max_attempts=180, interval=5)
        if not report_data:
            continue
        
        # 4. 실제 리포트 내용 추출
        final_report = report_data.get("report")
        if not final_report:
            print("❌ 최종 리포트 데이터가 없습니다.")
            continue
        
        # 5. 결과 저장
        save_report(final_report, config["location"])
        
        # 6. 미리보기 출력
        print_report_preview(final_report)
        
        # 다음 리포트 생성 전 대기
        if len(selected_configs) > 1:
            print(f"\n⏸️  5초 후 다음 리포트 생성...")
            time.sleep(5)
    
    print(f"\n{'='*80}")
    print("✅ 모든 리포트 생성 완료!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()