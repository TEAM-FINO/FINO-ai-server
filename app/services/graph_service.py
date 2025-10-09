from app.core.config import settings
from neo4j import GraphDatabase, Driver
from typing import List, Optional, TypedDict

class NewsInfo(TypedDict):
    news_id: str
    title: str
    category: str

class Neo4jService:
    _driver: Driver = None

    def connect(self):
        """애플리케이션 시작 시 호출될 드라이버 초기화 메서드"""
        if self._driver is None:
            print("Initializing Neo4j Driver...")
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
            )

    def close(self):
        """애플리케이션 종료 시 호출될 드라이버 종료 메서드"""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            print("Neo4j Driver closed.")

    def get_session(self):
        """세션 컨텍스트 매니저를 반환합니다."""
        if self._driver is None:
            raise Exception("Neo4j Driver not initialized. Call connect() first.")
        return self._driver.session()

    def get_filtered_news_ids(
        self,
        location: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[str]:
        with self.get_session() as session:
            base_query = "MATCH (n:News)"
            params = {}

            if location:
                base_query += " MATCH (n)-[:IS_IN_LOCATION]->(l:Location {name: $location})"
                params['location'] = location
            if category:
                base_query += " MATCH (n)-[:HAS_CATEGORY]->(c:Category {name: $category})"
                params['category'] = category

            final_query = base_query + " RETURN n.news_id as news_id LIMIT 100"
            result = session.run(final_query, params)
            return [record['news_id'] for record in result]

    def get_all_news_by_location(self, location: str) -> List[NewsInfo]:
        """특정 지역의 모든 뉴스 ID, 제목, 카테고리를 가져옵니다."""
        with self.get_session() as session:
            query = """
                MATCH (l:Location {name: $location})<-[:IS_IN_LOCATION]-(n:News)-[:HAS_CATEGORY]->(c:Category)
                RETURN n.news_id AS news_id, n.title AS title, c.name AS category
            """
            result = session.run(query, location=location)
            # TypedDict 형태로 변환하여 반환
            return [{"news_id": record["news_id"], "title": record["title"], "category": record["category"]} for record in result]

    def create_news_graph_data(self, doc):
        with self.get_session() as session:
            session.run("""
                MERGE (l:Location {name: $location})
                MERGE (c:Category {name: $category})
                MERGE (n:News {news_id: $news_id, title: $title})
                MERGE (n)-[:IS_IN_LOCATION]->(l)
                MERGE (n)-[:HAS_CATEGORY]->(c)
            """, location=doc.location, category=doc.category, news_id=doc.news_id, title=doc.title)

    def delete_test_data(self, news_id: str):
        with self.get_session() as session:
            session.run("MATCH (n:News {news_id: $id}) DETACH DELETE n", id=news_id)

graph_service = Neo4jService()