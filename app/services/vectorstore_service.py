from app.core.config import settings
import chromadb
from sentence_transformers import SentenceTransformer

chroma_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=8000)
embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
collection = chroma_client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)

def delete_test_data(ids: list[str]):
    collection.delete(ids=ids)