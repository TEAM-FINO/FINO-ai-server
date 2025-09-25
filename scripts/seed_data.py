import requests
import json

# --- 설정 ---
API_BASE_URL = "http://localhost:8001/api/v1/dev"
HEADERS = {"Content-Type": "application/json"}

# --- 테스트용 Mock 데이터 정의 ---
MOCK_NEWS_DATA = [
    # 춘천 경제
    {"news_id": "CK001", "press": "강원일보", "title": "춘천 데이터센터 착공, 지역 경제 활성화 기대", "content": "춘천시의 새로운 데이터센터가 오늘 착공에 들어갔다. IT 일자리 창출과 함께 지역 경제에 큰 활력을 불어넣을 것으로 기대된다.", "location": "춘천", "category": "경제"},
    {"news_id": "CK002", "press": "강원일보", "title": "레고랜드, 방문객 100만명 돌파하며 춘천 대표 관광지로", "content": "춘천 레고랜드가 개장 1년 만에 누적 방문객 100만 명을 돌파했다. 이는 지역 관광 수입 증대에 직접적으로 기여하고 있다.", "location": "춘천", "category": "경제"},
    # 춘천 사회
    {"news_id": "CS001", "press": "춘천MBC", "title": "춘천시, 청년 주거 안정 대책 발표", "content": "춘천시가 청년들의 주거 안정을 돕기 위한 새로운 정책을 발표했다. 저렴한 임대주택 공급을 확대할 계획이다.", "location": "춘천", "category": "사회"},
    # 원주 경제
    {"news_id": "WK001", "press": "G1방송", "title": "원주 반도체 클러스터, 정부 예비타당성 조사 통과", "content": "원주시의 숙원 사업이었던 반도체 클러스터 조성이 정부의 예비타당성 조사를 통과하며 사업 추진에 청신호가 켜졌다.", "location": "원주", "category": "경제"},
]

def seed_chromadb():
    """ChromaDB에 뉴스 문서와 벡터를 저장합니다."""
    print("--- Seeding ChromaDB ---")
    url = f"{API_BASE_URL}/news/mock_chroma" # ChromaDB용 Mock API
    for news in MOCK_NEWS_DATA:
        try:
            response = requests.post(url, headers=HEADERS, data=json.dumps(news))
            response.raise_for_status()
            print(f"  [SUCCESS] ChromaDB: Added '{news['title']}'")
        except requests.exceptions.RequestException as e:
            print(f"  [FAILURE] ChromaDB: Failed to add '{news['title']}'. Error: {e}")

def seed_neo4j():
    """Neo4j에 뉴스 노드와 관계를 생성합니다."""
    print("\n--- Seeding Neo4j ---")
    url = f"{API_BASE_URL}/news/mock_graph" # Neo4j용 Mock API
    for news in MOCK_NEWS_DATA:
        try:
            response = requests.post(url, headers=HEADERS, data=json.dumps(news))
            response.raise_for_status()
            print(f"  [SUCCESS] Neo4j: Added '{news['title']}'")
        except requests.exceptions.RequestException as e:
            print(f"  [FAILURE] Neo4j: Failed to add '{news['title']}'. Error: {e}")

if __name__ == "__main__":
    print("Starting database seeding process...")
    seed_chromadb()
    seed_neo4j()
    print("\nDatabase seeding finished!")