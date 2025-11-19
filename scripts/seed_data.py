import requests
import json

# --- 설정 ---
API_BASE_URL = "http://localhost:8001/api/v1/dev"
HEADERS = {"Content-Type": "application/json"}

# --- 테스트용 Mock 데이터 정의 ---
MOCK_NEWS_DATA = [
    # 춘천 (총 7개)
    # 춘천 - 경제
    {"news_id": "CK001", "press": "강원일보", "title": "춘천 데이터센터 착공, 지역 경제 활성화 기대", "content": "춘천시의 새로운 데이터센터가 오늘 착공에 들어갔다. IT 일자리 창출과 함께 지역 경제에 큰 활력을 불어넣을 것으로 기대된다.", "location": "춘천", "category": "경제", "pubDate": "Mon, 27 Oct 2025 10:00:00 +0900"},
    {"news_id": "CK002", "press": "강원도민일보", "title": "레고랜드, 방문객 100만명 돌파하며 춘천 대표 관광지로", "content": "춘천 레고랜드가 개장 1년 만에 누적 방문객 100만 명을 돌파했다. 이는 지역 관광 수입 증대에 직접적으로 기여하고 있다.", "location": "춘천", "category": "경제", "pubDate": "Tue, 28 Oct 2025 11:00:00 +0900"},
    {"news_id": "CK003", "press": "G1방송", "title": "춘천시, '감자빵'과 협력하여 농가 소득 증대", "content": "춘천시가 지역 명물인 감자빵 제조업체와 협력하여, 지역 감자 농가의 소득을 증대시키는 상생 모델을 발표했다.", "location": "춘천", "category": "경제", "pubDate": "Wed, 29 Oct 2025 09:30:00 +0900"},
    # 춘천 - 사회
    {"news_id": "CS001", "press": "춘천MBC", "title": "춘천시, 청년 주거 안정 대책 발표", "content": "춘천시가 청년들의 주거 안정을 돕기 위한 새로운 정책을 발표했다. 저렴한 임대주택 공급을 확대할 계획이다.", "location": "춘천", "category": "사회", "pubDate": "Tue, 28 Oct 2025 14:00:00 +0900"},
    {"news_id": "CS002", "press": "KBS춘천", "title": "소양강 스카이워크 야간 개장, 관광객 발길 이어져", "content": "소양강 스카이워크가 야간 조명과 함께 개장하며, 춘천을 찾는 관광객들에게 새로운 볼거리를 제공하고 있다.", "location": "춘천", "category": "사회", "pubDate": "Thu, 30 Oct 2025 19:00:00 +0900"},
    # 춘천 - 문화
    {"news_id": "CC001", "press": "강원일보", "title": "춘천 마임 축제, 3년 만에 거리 공연 재개", "content": "춘천의 대표 축제인 마임 축제가 3년 만에 야외 거리 공연으로 돌아와 시민들과 관광객들에게 큰 즐거움을 선사했다.", "location": "춘천", "category": "문화", "pubDate": "Mon, 27 Oct 2025 18:00:00 +0900"},
    # 춘천 - IT/과학
    {"news_id": "CI001", "press": "전자신문", "title": "춘천시, K-클라우드 파크 조성으로 '데이터 수도' 도약", "content": "춘천시가 수열 에너지 기반의 K-클라우드 파크 조성을 본격화하며, 국내 데이터 산업의 중심지로 거듭나고 있다.", "location": "춘천", "category": "IT/과학", "pubDate": "Wed, 29 Oct 2025 16:00:00 +0900"},
    # 춘천 - 생활 
    {"news_id": "CL001", "press": "춘천사람들", "title": "춘천 공공자전거 '쿠키' 도입, 시민 만족도 높아", "content": "춘천시가 도입한 공공자전거 '쿠키'가 편리한 이용 방식으로 시민들에게 큰 호응을 얻고 있다.", "location": "춘천", "category": "생활", "pubDate": "Fri, 31 Oct 2025 11:00:00 +0900"},

    # 원주 (총 7개)
    # 원주 - 경제
    {"news_id": "WK001", "press": "G1방송", "title": "원주 반도체 클러스터, 정부 예비타당성 조사 통과", "content": "원주시의 숙원 사업이었던 반도체 클러스터 조성이 정부의 예비타당성 조사를 통과하며 사업 추진에 청신호가 켜졌다.", "location": "원주", "category": "경제", "pubDate": "Mon, 27 Oct 2025 09:00:00 +0900"},
    {"news_id": "WK002", "press": "원주투데이", "title": "원주 의료기기 테크노밸리, 수출 1억 달러 달성", "content": "원주 의료기기 테크노밸리가 올해 수출 1억 달러를 달성하며, K-의료기기의 전초기지로 자리매김하고 있다.", "location": "원주", "category": "경제", "pubDate": "Wed, 29 Oct 2025 15:00:00 +0900"},
    # 원주 - 사회
    {"news_id": "WS001", "press": "KBS원주", "title": "원주시, '걷기 좋은 도시' 10대 명소 선정", "content": "원주시가 시민 건강 증진을 위해 '걷기 좋은 도시' 10대 명소를 선정하고 관련 인프라를 확충한다고 밝혔다.", "location": "원주", "category": "사회", "pubDate": "Fri, 31 Oct 2025 10:00:00 +0900"},
    {"news_id": "WS002", "press": "강원일보", "title": "원주 기업도시, 인구 3만 돌파... 정주 여건 개선 시급", "content": "원주 기업도시의 인구가 3만 명을 넘어섰으나, 학교 및 교통 인프라 부족 문제가 여전히 해결 과제로 남아있다.", "location": "원주", "category": "사회", "pubDate": "Tue, 28 Oct 2025 13:00:00 +0900"},
    # 원주 - 문화 
    {"news_id": "WC001", "press": "원주MBC", "title": "박경리 문학공원, 가을 문학 축제 성황리 개최", "content": "원주 박경리 문학공원에서 열린 가을 문학 축제에 수많은 관광객이 방문하며 문학의 도시 원주를 알렸다.", "location": "원주", "category": "문화", "pubDate": "Mon, 27 Oct 2025 17:00:00 +0900"},
    # 원주 - IT/과학 
    {"news_id": "WI001", "press": "디지털투데이", "title": "원주시, '스마트시티' 솔루션으로 교통 문제 해결 나서", "content": "원주시가 AI 기반의 스마트 교통 시스템을 도입하여, 출퇴근 시간 상습 정체 구간 해소에 나선다.", "location": "원주", "category": "IT/과학", "pubDate": "Thu, 30 Oct 2025 11:30:00 +0900"},
    # 원주 - 생활 
    {"news_id": "WL001", "press": "원주투데이", "title": "원주천 둘레길, 야간 조명 설치로 '밤 산책 명소'로", "content": "원주천 둘레길에 최근 야간 경관 조명이 설치되어, 시민들이 밤에도 안전하게 산책을 즐길 수 있게 되었다.", "location": "원주", "category": "생활", "pubDate": "Wed, 29 Oct 2025 20:00:00 +0900"},

    # 강릉 (총 6개)
    # 강릉 - 경제
    {"news_id": "GK001", "press": "강릉일보", "title": "강릉항, 해양 관광 거점으로 재개발... 1000억 투입", "content": "강릉항 일대가 해양 관광 및 레저의 중심지로 거듭나기 위해 대규모 재개발 사업에 착수한다.", "location": "강릉", "category": "경제", "pubDate": "Mon, 27 Oct 2025 14:00:00 +0900"},
    # 강릉 - 사회
    {"news_id": "GS001", "press": "강원도민일보", "title": "KTX 강릉선, 주말 좌석 매진 행렬... '관광 특수'", "content": "가을 단풍철을 맞아 KTX 강릉선이 주말마다 매진되며 지역 관광 경기에 활기를 불어넣고 있다.", "location": "강릉", "category": "사회", "pubDate": "Tue, 28 Oct 2025 10:30:00 +0900"},
    # 강릉 - 문화
    {"news_id": "GC001", "press": "강릉MBC", "title": "강릉 커피 축제, 50만명 방문하며 역대 최대 성과", "content": "이번 강릉 커피 축제가 50만 명의 방문객을 유치하며, 명실상부한 대한민국 대표 커피 축제로 자리매김했다.", "location": "강릉", "category": "문화", "pubDate": "Mon, 27 Oct 2025 11:00:00 +0900"},
    {"news_id": "GC002", "press": "KBS강릉", "title": "강릉단오제전수교육관, 유네스코 인류무형문화유산 홍보", "content": "강릉단오제전수교육관이 유네스코 인류무형문화유산인 강릉단오제를 알리기 위한 다채로운 체험 프로그램을 운영한다.", "location": "강릉", "category": "문화", "pubDate": "Wed, 29 Oct 2025 18:00:00 +0900"},
    # 강릉 - IT/과학
    {"news_id": "GI001", "press": "전자신문", "title": "강릉시, '해양 바이오' 산업 육성... R&D 센터 개소", "content": "강릉시가 풍부한 해양 자원을 활용한 바이오 산업 육성을 위해 전문 R&D 센터를 개소하고 기업 유치에 나섰다.", "location": "강릉", "category": "IT/과학", "pubDate": "Thu, 30 Oct 2025 15:30:00 +0900"},
    # 강릉 - 생활
    {"news_id": "GL001", "press": "강릉일보", "title": "안목해변, '쓰레기 없는 해변' 캠페인으로 깨끗함 되찾아", "content": "강릉시와 지역 상인, 자원봉사자들이 함께한 '쓰레기 없는 해변' 캠페인 덕분에 안목해변이 깨끗한 모습을 되찾았다.", "location": "강릉", "category": "생활", "pubDate": "Fri, 31 Oct 2025 14:00:00 +0900"}
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