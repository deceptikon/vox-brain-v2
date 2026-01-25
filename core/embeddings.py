import ollama
from typing import List

class EmbeddingEngine:
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for i, text in enumerate(texts):
            if i > 0 and i % 100 == 0:
                print(f"  Processed {i}/{len(texts)} embeddings...")
            
            if not text.strip():
                text = "empty"
            
            # Limit length to ~8k chars to prevent status 500 in Ollama
            safe_text = text[:8000]
            
            try:
                response = ollama.embeddings(model=self.model, prompt=safe_text)
                embeddings.append(response["embedding"])
            except Exception as e:
                print(f"⚠️ Embedding failed at index {i}: {e}")
                embeddings.append([0.0] * 768) 
        return embeddings
