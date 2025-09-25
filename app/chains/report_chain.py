from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from app.services.llm_service import llm
from app.services.vectorstore_service import collection, embedding_model
from app.services.graph_service import graph_service

# Neo4j 필터링 
def _filter_news_from_neo4j(input_dict: dict) -> dict:
    ids = graph_service.get_filtered_news_ids(input_dict['location'], input_dict['category'])
    input_dict['filtered_ids'] = ids
    return input_dict

# ChromaDB 검색 
def _retrieve_documents(input_dict: dict) -> dict:
    query_vector = embedding_model.encode(input_dict['query']).tolist()

    # Neo4j에서 필터링된 ID 목록이 있으면 where 조건으로 사용
    where_filter = {}
    if input_dict.get('filtered_ids'):
        # ChromaDB의 메타데이터 필터링 방식
        where_filter = {"news_id": {"$in": input_dict['filtered_ids']}}

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=3,
        where=where_filter if where_filter else None # 필터가 있을 때만 적용
    )
    if not results or not results.get('documents') or not results['documents'][0]:
        input_dict['context'] = "관련된 뉴스 기사를 찾을 수 없습니다."
    else:
        input_dict['context'] = "\n\n".join(results['documents'][0])

    return input_dict

# 프롬프트 템플릿
prompt_template = ChatPromptTemplate.from_template(
    """
    당신은 대한민국 지역 뉴스를 분석하는 전문 애널리스트입니다.
    주어진 [관련 뉴스 기사]를 완벽하게 이해하고, 사용자의 [질문]에 대해 **반드시 한국어로** 상세하고 깊이 있는 리포트를 작성해주세요.

    [관련 뉴스 기사]
    {context}

    [질문]
    {query}

    [생성 리포트]
    """
)

# LCEL 체인 구성
report_chain = (
    RunnablePassthrough.assign(neo4j_results=_filter_news_from_neo4j)
    | RunnablePassthrough.assign(retrieved_results=_retrieve_documents)
    | {
        "context": lambda x: x['retrieved_results']['context'],
        "query": lambda x: x['query']
      }
    | prompt_template
    | llm
    | StrOutputParser()
)