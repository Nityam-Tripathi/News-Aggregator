import os
import requests

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

def generate_embedding(text: str):
    try:
        response = requests.post(
            API_URL, 
            headers=headers, 
            json={"inputs": text, "options": {"wait_for_model": True}},
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], float):
                    return result
                elif isinstance(result[0], list):
                    return result[0]
    except Exception as e:
        print(f"Error generating embedding via HF: {e}")
        
    return [0.0] * 384