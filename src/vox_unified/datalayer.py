import sqlite3
import psycopg
import os
import yaml
import json
from pathlib import Path

from typing import List, Optional, Dict, Any
from pgvector.psycopg import register_vector
from datetime import datetime

from vox_unified.models import Symbol, Document, SearchResult

# Load Config
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "storage.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        STORAGE_CONFIG = yaml.safe_load(f)
except Exception:
    STORAGE_CONFIG = {}

# --- Local Management Layer (SQLite) ---
class LocalMetaStorage:
    def __init__(self):
        self.vox_home = Path(os.environ.get("VOX_HOME", Path.home() / ".vox-brain"))
        self.db_path = self.vox_home / "context" / "vox_meta.db"
        
        # Ensure dir exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_conn() as conn:
            # Table: Projects
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Table: Documents (Rules, Notes, Docs)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    type TEXT NOT NULL, -- rule, note, doc
                    title TEXT,
                    content TEXT NOT NULL,
                    file_path TEXT, -- Optional, if linked to a file
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

    # Projects CRUD
    def add_project(self, project_id: str, name: str, path: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, path) VALUES (?, ?, ?)",
                (project_id, name, path)
            )

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT id, name, path, created_at FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row:
                return {"id": row[0], "name": row[1], "path": row[2], "created_at": row[3]}
        return None
        
    def get_project_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT id, name, path, created_at FROM projects WHERE path = ?", (path,)).fetchone()
            if row:
                return {"id": row[0], "name": row[1], "path": row[2], "created_at": row[3]}
        return None

    def list_projects(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id, name, path FROM projects").fetchall()
            return [{"id": r[0], "name": r[1], "path": r[2]} for r in rows]

    def delete_project(self, project_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # Documents CRUD
    def add_document(self, project_id: str, doc_type: str, content: str, title: str = None, file_path: str = None) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO documents (project_id, type, title, content, file_path) VALUES (?, ?, ?, ?, ?)",
                (project_id, doc_type, title, content, file_path)
            )
            return cur.lastrowid

    def list_documents(self, project_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, type, title, content, created_at FROM documents WHERE project_id = ?", 
                (project_id,)
            ).fetchall()
            return [{"id": r[0], "type": r[1], "title": r[2], "content": r[3], "created_at": r[4]} for r in rows]
    
    def get_all_documents_for_indexing(self, project_id: str) -> List[Dict[str, Any]]:
        """Used by the indexer to push docs to Postgres"""
        return self.list_documents(project_id)
        
    def delete_document(self, doc_id: int):
         with self._get_conn() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# --- Vector Search Layer (Postgres) ---
class VectorStorage:
    def __init__(self):
        prefix = "SQL_"
        self.dbname = os.getenv(f"{prefix}DATABASE", "tamga_local")
        self.user = os.getenv(f"{prefix}USER", "tamga_user")
        self.password = os.getenv(f"{prefix}PASSWORD", "tamga_pass")
        self.host = os.getenv(f"{prefix}HOST", "localhost")
        self.port = os.getenv(f"{prefix}PORT", "5432")
        self.conn_str = f"dbname={self.dbname} user={self.user} password={self.password} host={self.host} port={self.port}"
        self.index_table = "vox_index"
        self._init_db()

    def _init_db(self):
        try:
            with psycopg.connect(self.conn_str, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    # Unified Index Table
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.index_table} (
                            id SERIAL PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            content TEXT NOT NULL,
                            embedding vector(768),
                            file_path TEXT,
                            type TEXT NOT NULL, -- 'symbol', 'markdown', 'rule', 'note'
                            metadata JSONB DEFAULT '{{}}',
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {self.index_table}_emb_idx ON {self.index_table} USING ivfflat (embedding vector_cosine_ops)")
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {self.index_table}_pid_idx ON {self.index_table} (project_id)")
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {self.index_table}_type_idx ON {self.index_table} (type)")
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize Postgres: {e}")

    def save_to_index(self, items: List[Dict[str, Any]], project_id: str, embeddings: List[List[float]]):
        """Unified save for any indexable content."""
        with psycopg.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                for i, item in enumerate(items):
                    cur.execute(
                        f"""
                        INSERT INTO {self.index_table} (project_id, content, embedding, file_path, type, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            project_id, 
                            item["content"], 
                            embeddings[i], 
                            item.get("file_path"),
                            item.get("type", "unknown"),
                            json.dumps(item.get("metadata", {}))
                        )
                    )

    def search(self, query_text: str, query_embedding: List[float], project_id: Optional[str] = None, limit: int = 20) -> List[SearchResult]:
        results = []
        try:
            with psycopg.connect(self.conn_str) as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    # Type Weighting: 1 for Rule, 2 for Symbol, 3 for Note/Markdown
                    # We want lower numbers first or use a CASE statement in ORDER BY
                    sql = f"""
                    SELECT content, file_path, type, metadata, (embedding <=> %s::vector) as distance
                    FROM {self.index_table}
                    WHERE 1=1
                    """
                    params = [query_embedding]

                    if project_id:
                        sql += " AND project_id = %s"
                        params.append(project_id)
                    
                    # Hybrid Search with Type Priority
                    sql += """
                    ORDER BY 
                        (content ILIKE %s) DESC,
                        (CASE 
                            WHEN type = 'rule' THEN 1
                            WHEN type = 'symbol' THEN 2
                            ELSE 3 
                         END) ASC,
                        distance ASC
                    LIMIT %s
                    """
                    params.extend([f"%{query_text}%", limit])

                    cur.execute(sql, params)
                    for row in cur.fetchall():
                        content, fpath, itype, meta, dist = row
                        
                        # Extract line info for symbols
                        source_display = fpath or itype
                        if itype == 'symbol' and meta.get('start_line') is not None:
                            source_display = f"{fpath}:{meta['start_line'] + 1}"

                        results.append(SearchResult(
                            content=content,
                            source=source_display,
                            relevance=1 - dist,
                            type=itype,
                            metadata=meta
                        ))
        except Exception as e:
            print(f"⚠️ Search Error: {e}")
        return results


    def delete_project_data(self, project_id: str):
        with psycopg.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {self.index_table} WHERE project_id = %s", (project_id,))


class DataLayer:
    def __init__(self):
        self.local = LocalMetaStorage()
        self.vector = VectorStorage()
