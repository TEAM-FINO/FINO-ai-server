import requests
import json

# --- 설정 ---
API_BASE_URL = "http://localhost:8001/api/v1/dev"
HEADERS = {"Content-Type": "application/json"}

# --- 테스트용 Mock 데이터 정의 ---
MOCK_NEWS_DATA = [
    # 춘천 경제 (지난 주 데이터)
    {"news_id": "CK001", "press": "강원일보", "title": "춘천 데이터센터 착공...", "content": "...", "location": "춘천", "category": "경제", "pubDate": "Mon, 06 Oct 2025 10:00:00 +0900"},
    {"news_id": "CK002", "press": "강원일보", "title": "레고랜드, 방문객 100만명 돌파...", "content": "...", "location": "춘천", "category": "경제", "pubDate": "Tue, 07 Oct 2025 11:00:00 +0900"},
    # 춘천 사회 (지난 주 데이터)
    {"news_id": "CS001", "press": "춘천MBC", "title": "춘천시, 청년 주거 안정 대책 발표", "content": "...", "location": "춘천", "category": "사회", "pubDate": "Wed, 08 Oct 2025 14:00:00 +0900"},
    # 원주 경제 (지난 달 데이터)
    {"news_id": "WK001", "press": "G1방송", "title": "원주 반도체 클러스터, 정부 예타 통과", "content": "...", "location": "원주", "category": "경제", "pubDate": "Wed, 10 Sep 2025 09:00:00 +0900"},
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