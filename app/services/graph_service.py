import logging
from app.core.config import settings
from neo4j import GraphDatabase, Driver, Session
from typing import List, Optional, TypedDict
from datetime import datetime
from email.utils import parsedate_to_datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class NewsInfo(TypedDict):
    news_id: str
    title: str
    category: str

class Neo4jConnectionError(Exception):
    """Neo4j 연결 관련 에러"""
    pass

class Neo4jService:
    _driver: Optional[Driver] = None

    def connect(self):
        """애플리케이션 시작 시 호출될 드라이버 초기화 메서드"""
        if self._driver is None:
            try:
                logger.info("Initializing Neo4j Driver...")
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
                    # 연결 풀 설정
                    max_connection_pool_size=50,
                    connection_acquisition_timeout=60.0
                )
                # 연결 테스트
                self._driver.verify_connectivity()
                logger.info("✓ Neo4j Driver initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j Driver: {e}", exc_info=True)
                raise Neo4jConnectionError(f"Could not connect to Neo4j: {e}")

    def close(self):
        """애플리케이션 종료 시 호출될 드라이버 종료 메서드"""
        if self._driver is not None:
            try:
                self._driver.close()
                self._driver = None
                logger.info("Neo4j Driver closed.")
            except Exception as e:
                logger.error(f"Error closing Neo4j Driver: {e}", exc_info=True)

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager로 세션을 안전하게 반환합니다.
        사용 예: with graph_service.get_session() as session: ...
        """
        if self._driver is None:
            raise Neo4jConnectionError("Neo4j Driver not initialized. Call connect() first.")
        
        session = None
        try:
            session = self._driver.session()
            yield session
        except Exception as e:
            logger.error(f"Neo4j session error: {e}", exc_info=True)
            raise
        finally:
            if session is not None:
                session.close()

    def get_all_target_locations(self) -> List[str]:
        """DB에 저장된 모든 Location 노드의 이름을 가져옵니다."""
        try:
            with self.get_session() as session:
                query = "MATCH (l:Location) RETURN DISTINCT l.name AS location ORDER BY l.name"
                result = session.run(query)
                locations = [record["location"] for record in result]
                logger.info(f"Found {len(locations)} target locations.")
                return locations
        except Exception as e:
            logger.error(f"Failed to get target locations: {e}", exc_info=True)
            return []  # 실패 시 빈 리스트 반환 (Beat 스케줄러가 멈추지 않도록)

    def get_all_news_by_location(self, location: str, start_date: datetime, end_date: datetime) -> List[NewsInfo]:
        """특정 지역의 지정된 기간 내 모든 뉴스 ID, 제목, 카테고리를 가져옵니다."""
        try:
            with self.get_session() as session:
                query = """
                    MATCH (l:Location {name: $location})<-[:IS_IN_LOCATION]-(n:News)-[:HAS_CATEGORY]->(c:Category)
                    WHERE datetime($start_date) <= n.pubDate < datetime($end_date)
                    RETURN n.news_id AS news_id, n.title AS title, c.name AS category
                    ORDER BY n.pubDate DESC
                """
                result = session.run(
                    query,
                    location=location,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat()
                )
                news_list = [
                    {"news_id": record["news_id"], "title": record["title"], "category": record["category"]} 
                    for record in result
                ]
                logger.info(f"Retrieved {len(news_list)} news items for '{location}' between {start_date.date()} and {end_date.date()}.")
                return news_list
        except Exception as e:
            logger.error(f"Failed to get news for location '{location}': {e}", exc_info=True)
            return []
    
    def get_filtered_news_ids(
        self,
        location: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100  # 기본값 명시
    ) -> List[str]:
        """필터링된 뉴스 ID 목록을 가져옵니다."""
        try:
            with self.get_session() as session:
                match_patterns = ["(n:News)"]
                params = {"limit": limit}
                
                if location:
                    match_patterns.append("(n)-[:IS_IN_LOCATION]->(l:Location {name: $location})")
                    params['location'] = location
                
                if category:
                    match_patterns.append("(n)-[:HAS_CATEGORY]->(c:Category {name: $category})")
                    params['category'] = category
                
                match_clause = ", ".join(match_patterns)
                
                query = f"""
                    MATCH {match_clause}
                    RETURN n.news_id AS news_id
                    ORDER BY n.pubDate DESC
                    LIMIT $limit
                """
                
                result = session.run(query, params)
                news_ids = [record['news_id'] for record in result]
                logger.info(f"Filtered {len(news_ids)} news IDs (location={location}, category={category}).")
                return news_ids
        except Exception as e:
            logger.error(f"Failed to get filtered news IDs: {e}", exc_info=True)
            return []

    def create_news_graph_data(self, doc):
        """뉴스 그래프 데이터를 생성합니다."""
        try:
            with self.get_session() as session:
                # pubDate 파싱 예외 처리
                try:
                    pub_date_dt = parsedate_to_datetime(doc.pubDate)
                except Exception as e:
                    logger.warning(f"Failed to parse pubDate '{doc.pubDate}' for news {doc.news_id}: {e}")
                    pub_date_dt = datetime.now()  # Fallback to current time
                
                session.run("""
                    MERGE (l:Location {name: $location})
                    MERGE (c:Category {name: $category})
                    MERGE (n:News {news_id: $news_id})
                    ON CREATE SET n.title = $title, n.pubDate = $pubDate
                    ON MATCH SET n.title = $title, n.pubDate = $pubDate
                    MERGE (n)-[:IS_IN_LOCATION]->(l)
                    MERGE (n)-[:HAS_CATEGORY]->(c)
                """, 
                    location=doc.location, 
                    category=doc.category, 
                    news_id=doc.news_id, 
                    title=doc.title, 
                    pubDate=pub_date_dt
                )
                logger.info(f"Created/updated graph data for news {doc.news_id}.")
        except Exception as e:
            logger.error(f"Failed to create graph data for news {doc.news_id}: {e}", exc_info=True)

    def delete_test_data(self, news_id: str):
        """테스트 데이터를 삭제합니다."""
        try:
            with self.get_session() as session:
                result = session.run(
                    "MATCH (n:News {news_id: $id}) DETACH DELETE n RETURN count(n) AS deleted", 
                    id=news_id
                )
                deleted_count = result.single()["deleted"]
                if deleted_count > 0:
                    logger.info(f"Deleted test news {news_id}.")
                else:
                    logger.warning(f"Test news {news_id} not found for deletion.")
        except Exception as e:
            logger.error(f"Failed to delete test data {news_id}: {e}", exc_info=True)

    def health_check(self) -> bool:
        """Neo4j 연결 상태를 확인합니다."""
        try:
            if self._driver is None:
                return False
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False
    
    def get_database_stats(self) -> dict:
        """데이터베이스 통계를 반환합니다."""
        try:
            with self.get_session() as session:
                stats = {}
                
                # 뉴스 개수
                result = session.run("MATCH (n:News) RETURN count(n) AS count")
                stats["total_news"] = result.single()["count"]
                
                # 지역 개수
                result = session.run("MATCH (l:Location) RETURN count(l) AS count")
                stats["total_locations"] = result.single()["count"]
                
                # 카테고리 개수
                result = session.run("MATCH (c:Category) RETURN count(c) AS count")
                stats["total_categories"] = result.single()["count"]
                
                # 지역별 뉴스 개수
                result = session.run("""
                    MATCH (l:Location)<-[:IS_IN_LOCATION]-(n:News)
                    RETURN l.name AS location, count(n) AS count
                    ORDER BY count DESC
                """)
                stats["news_by_location"] = [
                    {"location": record["location"], "count": record["count"]} 
                    for record in result
                ]
                
                return stats
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}", exc_info=True)
            return {"error": str(e)}

graph_service = Neo4jService()