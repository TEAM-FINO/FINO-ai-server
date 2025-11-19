"""
Neo4j 인덱스 생성 스크립트

성능 최적화를 위해 필수 인덱스를 생성합니다.
배포 전 한 번 실행하세요.
"""
from neo4j import GraphDatabase
import sys
import os

# 환경변수에서 Neo4j 연결 정보 가져오기
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_PASSWORD:
    print("❌ Error: NEO4J_PASSWORD environment variable not set")
    sys.exit(1)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

def create_indexes():
    """필수 인덱스를 생성합니다."""
    
    indexes = [
        # News 노드 인덱스
        "CREATE INDEX news_id_index IF NOT EXISTS FOR (n:News) ON (n.news_id)",
        "CREATE INDEX news_pub_date_index IF NOT EXISTS FOR (n:News) ON (n.pubDate)",
        
        # Location 노드 인덱스
        "CREATE INDEX location_name_index IF NOT EXISTS FOR (l:Location) ON (l.name)",
        
        # Category 노드 인덱스
        "CREATE INDEX category_name_index IF NOT EXISTS FOR (c:Category) ON (c.name)",
    ]
    
    with driver.session() as session:
        for index_query in indexes:
            try:
                session.run(index_query)
                print(f"✓ Created index: {index_query.split('FOR')[0].strip()}")
            except Exception as e:
                print(f"✗ Failed to create index: {e}")
    
    print("\n✅ Index creation completed!")

def verify_indexes():
    """생성된 인덱스를 확인합니다."""
    
    with driver.session() as session:
        result = session.run("SHOW INDEXES")
        
        print("\n📊 Current indexes:")
        for record in result:
            print(f"  • {record['name']}: {record['labelsOrTypes']} ({record['properties']})")

if __name__ == "__main__":
    print("🔧 Creating Neo4j indexes...\n")
    
    try:
        create_indexes()
        verify_indexes()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        driver.close()