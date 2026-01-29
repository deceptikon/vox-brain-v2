import json
import requests
import sys

def get_ollama_embedding(text: str, model: str = "nomic-embed-text") -> list[float]:
    """
    Gets an embedding from the Ollama API.
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            data=json.dumps({
                "model": model,
                "prompt": text
            })
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error {e.response.status_code}: {e.response.text}")
        # Only print snippet if verbose logging is needed, or keep it for safety
        print(f"   Text Length: {len(text)} chars")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Cannot connect to Ollama server at http://localhost:11434")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error getting Ollama embedding: {e}")
        sys.exit(1)
