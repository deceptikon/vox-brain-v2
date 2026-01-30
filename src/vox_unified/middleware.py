import json
import sqlite3
from typing import Optional, Any
from pathlib import Path

# Load storage config if needed (omitted for brevity)

class CacheLayer:
    """
    Handles 'Just-in-Time' caching for expensive operations like File Tree.
    """
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_cache_table()

    def _get_conn(self):
        return sqlite3.connect(str(self.db_path))

    def _init_cache_table(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    project_id TEXT,
                    key TEXT,
                    value TEXT, -- JSON payload
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, key)
                )
            """)

    def get(self, project_id: str, key: str) -> Optional[Any]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM cache WHERE project_id = ? AND key = ?", 
                (project_id, key)
            ).fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except:
                    return row[0]
        return None

    def set(self, project_id: str, key: str, value: Any):
        json_val = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (project_id, key, value, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (project_id, key, json_val)
            )

    def invalidate(self, project_id: str, key: str = None):
        with self._get_conn() as conn:
            if key:
                conn.execute("DELETE FROM cache WHERE project_id = ? AND key = ?", (project_id, key))
            else:
                conn.execute("DELETE FROM cache WHERE project_id = ?", (project_id,))


class TransformerLayer:
    """
    Transforms raw code/data into Agent-Friendly formats.
    """
    @staticmethod
    def generate_skeleton(code: str, file_path: str) -> str:
        """
        Parses code and returns a skeleton (signatures + docstrings only).
        Uses simple regex/heuristics for MVP, or Tree-sitter if available.
        For robust MVP without complex Tree-sitter traversal logic here, 
        we'll use a smart line-filter approach.
        """
        lines = code.splitlines()
        skeleton = []
        
        # Simple heuristic for Python
        if file_path.endswith(".py"):
            for line in lines:
                stripped = line.strip()
                # Keep imports
                if stripped.startswith(("import ", "from ")):
                    skeleton.append(line)
                # Keep classes/functions
                elif stripped.startswith(("class ", "def ", "@")):
                    skeleton.append(line)
                # Keep docstrings (naive check)
                elif stripped.startswith(('"""', "'''")):
                    skeleton.append(line)
                # Keep returns (sometimes useful for type hints)
                elif stripped.startswith("return ") and len(stripped) < 20:
                     skeleton.append(line)
                # Empty lines for readability
                elif not stripped:
                    skeleton.append(line)
            
            return "\n".join(skeleton)
            
        # For other files, just return first 50 lines?
        return "\n".join(lines[:50]) + "\n... (truncated)"
