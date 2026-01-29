import json
import requests
import sys

def get_ollama_embedding(text: str, model: str = "nomic-embed-text", is_query: bool = False) -> list[float]:
    """
    Gets an embedding from the Ollama API.
    Adds nomic-embed-text specific prefixes if applicable.
    """
    # Nomic v1.5 prefers prefixes
    if model == "nomic-embed-text":
        prefix = "search_query: " if is_query else "search_document: "
        if not text.startswith(prefix):
            text = f"{prefix}{text}"

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
