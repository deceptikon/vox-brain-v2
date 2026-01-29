import sqlite3
import psycopg
import os
import yaml
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
        prefix = "SQL_" # Can be configurable
        self.dbname = os.getenv(f"{prefix}DATABASE", "tamga_local")
        self.user = os.getenv(f"{prefix}USER", "tamga_user")
        self.password = os.getenv(f"{prefix}PASSWORD", "tamga_pass")
        self.host = os.getenv(f"{prefix}HOST", "localhost")
        self.port = os.getenv(f"{prefix}PORT", "5432")
        
        self.conn_str = f"dbname={self.dbname} user={self.user} password={self.password} host={self.host} port={self.port}"
        
        self.symbols_table = "vox_symbols"
        self.text_table = "vox_textdata"
        
        self._init_db()

    def _init_db(self):
        try:
            with psycopg.connect(self.conn_str, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    
                    # 1. Symbols Table (Smart Code)
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.symbols_table} (
                            id SERIAL PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            symbol_type TEXT NOT NULL,
                            code TEXT NOT NULL,
                            embedding vector(768),
                            file_path TEXT,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {self.symbols_table}_emb_idx ON {self.symbols_table} USING ivfflat (embedding vector_cosine_ops)")
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {self.symbols_table}_pid_idx ON {self.symbols_table} (project_id)")
                    
                    # 2. TextData Table (Smart Docs/Markdown)
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.text_table} (
                            id SERIAL PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            content TEXT NOT NULL,
                            embedding vector(768),
                            source_type TEXT, -- 'markdown', 'rule', 'note'
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {self.text_table}_emb_idx ON {self.text_table} USING ivfflat (embedding vector_cosine_ops)")
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {self.text_table}_pid_idx ON {self.text_table} (project_id)")
                    
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize Postgres: {e}")

    # --- Symbols ---
    def save_symbols(self, symbols: List[Symbol], project_id: str, embeddings: List[List[float]]):
        with psycopg.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                # We don't cleanup here anymore because manager.index_run() handles project-wide cleanup
                for i, symbol in enumerate(symbols):
                    cur.execute(
                        f"""
                        INSERT INTO {self.symbols_table} (project_id, name, symbol_type, code, embedding, file_path)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            project_id, symbol.name, symbol.type.value,
                            symbol.code, embeddings[i], symbol.file_path
                        )
                    )

    def search_symbols(self, query_text: str, query_embedding: List[float], project_id: Optional[str] = None, limit: int = 10) -> List[SearchResult]:
        results = []
        try:
            with psycopg.connect(self.conn_str) as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    # Hybrid Search: Exact/Partial Name Match + Vector Distance
                    sql = f"""
                    SELECT name, code, file_path, (embedding <=> %s::vector) as distance
                    FROM {self.symbols_table}
                    WHERE 1=1
                    """
                    params = [query_embedding]

                    if project_id:
                        sql += " AND project_id = %s"
                        params.append(project_id)
                    
                    # Add a "keyword boost" order: matches name exactly, then starts with, then vector distance
                    sql += f"""
                    ORDER BY 
                        (name ILIKE %s) DESC,
                        (name ILIKE %s) DESC,
                        distance ASC
                    LIMIT %s
                    """
                    params.extend([query_text, f"{query_text}%", limit])

                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    
                    for row in rows:
                        name, code, fpath, dist = row
                        results.append(SearchResult(
                            content=f"Symbol: {name}\nCode:\n{code}",
                            source=fpath or "symbol",
                            relevance=1 - dist,
                            type="symbolic",
                            metadata={"name": name}
                        ))
        except Exception as e:
            print(f"⚠️ Symbol Search Error: {e}")
        return results


    # --- TextData (Docs/MD) ---
    def save_text_chunks(self, chunks: List[Dict[str, Any]], project_id: str, embeddings: List[List[float]]):
        with psycopg.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                for i, chunk in enumerate(chunks):
                    cur.execute(
                        f"""
                        INSERT INTO {self.text_table} (project_id, content, embedding, source_type)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (project_id, chunk["content"], embeddings[i], chunk.get("type", "unknown"))
                    )

    def search_text(self, query_embedding: List[float], project_id: Optional[str] = None, limit: int = 10) -> List[SearchResult]:
        results = []
        try:
            with psycopg.connect(self.conn_str) as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    sql = f"""
                    SELECT content, source_type, (embedding <=> %s::vector) as distance
                    FROM {self.text_table}
                    WHERE 1=1
                    """
                    params = [query_embedding]

                    if project_id:
                        sql += " AND project_id = %s"
                        params.append(project_id)

                    sql += " ORDER BY distance ASC LIMIT %s"
                    params.append(limit)

                    cur.execute(sql, params)
                    for row in cur.fetchall():
                        content, stype, dist = row
                        results.append(SearchResult(
                            content=content,
                            source=stype or "text",
                            relevance=1 - dist,
                            type="text",
                            metadata={}
                        ))
        except Exception as e:
            print(f"⚠️ Text Search Error: {e}")
        return results

    def delete_project_data(self, project_id: str):
        with psycopg.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {self.symbols_table} WHERE project_id = %s", (project_id,))
                cur.execute(f"DELETE FROM {self.text_table} WHERE project_id = %s", (project_id,))


class DataLayer:
    def __init__(self):
        self.local = LocalMetaStorage()
        self.vector = VectorStorage()
