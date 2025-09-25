from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = 'distiluse-base-multilingual-cased-v1'

print(f"Downloading embedding model ('{EMBEDDING_MODEL_NAME}') to cache...")
SentenceTransformer(EMBEDDING_MODEL_NAME)
print("Model download complete.")