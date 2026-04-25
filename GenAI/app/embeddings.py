import os
from huggingface_hub import InferenceClient

HF_TOKEN = os.getenv("HF_TOKEN")
client = InferenceClient(token=HF_TOKEN)

def generate_embedding(text: str):
    try:
        result = client.feature_extraction(
            text,
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        # result is a numpy array, convert to list
        return result.tolist()
    except Exception as e:
        print(f"Error generating embedding via HF: {e}")
        return [0.0] * 384