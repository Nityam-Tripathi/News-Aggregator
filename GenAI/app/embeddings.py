from sentence_transformers import SentenceTransformer

# Load once globally
model = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embedding(text: str):
    return model.encode(text).tolist()