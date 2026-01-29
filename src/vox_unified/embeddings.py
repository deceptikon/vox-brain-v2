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
        err_msg = f"❌ HTTP Error {e.response.status_code}: {e.response.text} (Text Length: {len(text)})"
        print(err_msg, file=sys.stderr)
        raise RuntimeError(err_msg)
    except requests.exceptions.ConnectionError:
        err_msg = "❌ Error: Cannot connect to Ollama server at http://localhost:11434"
        print(err_msg, file=sys.stderr)
        raise RuntimeError(err_msg)
    except Exception as e:
        err_msg = f"❌ Error getting Ollama embedding: {e}"
        print(err_msg, file=sys.stderr)
        raise RuntimeError(err_msg)


