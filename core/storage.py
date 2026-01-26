import os
from typing import Any, List, Optional

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

from core.models import Symbol, SymbolType


class Storage:
    def __init__(self, env_path: str = None, table_name: Optional[str] = None):
        if env_path:
            load_dotenv(env_path)

        # Table name for symbols; configurable by parameter or SYMBOLS_TABLE env var
        # Default: symbols_v2
        self.table_name = table_name or os.getenv("SYMBOLS_TABLE", "symbols_v2")

        self.dbname = os.getenv("SQL_DATABASE", "tamga_local")
        self.user = os.getenv("SQL_USER", "tamga_user")
        self.password = os.getenv("SQL_PASSWORD", "tamga_pass")
        self.host = os.getenv("SQL_HOST", "localhost")
        self.port = os.getenv("SQL_PORT", "5432")

        self.conn_str = f"dbname={self.dbname} user={self.user} password={self.password} host={self.host} port={self.port}"
        self._init_db()

    def _init_db(self):
        with psycopg.connect(self.conn_str, autocommit=True) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                except Exception:
                    pass

                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        id SERIAL PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        symbol_type TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        start_line INTEGER,
                        end_line INTEGER,
                        code TEXT NOT NULL,
                        docstring TEXT,
                        parent_name TEXT,
                        embedding vector(768),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Ensure project_id exists for older schemas (we'll enforce NOT NULL after a safe backfill / repopulate)
                try:
                    cur.execute(
                        f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS project_id TEXT"
                    )
                except Exception:
                    pass
                # NOTE: column `project_path` removed from schema; use `project_id` for scoping and tracing.
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx ON {self.table_name} USING ivfflat (embedding vector_cosine_ops)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {self.table_name}_name_idx ON {self.table_name} (name)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {self.table_name}_project_id_idx ON {self.table_name} (project_id)"
                )

    def save_symbols(
        self,
        symbols: List[Symbol],
        embeddings: Optional[List[List[float]]] = None,
        project_id: str = None,
    ):
        if not project_id:
            raise ValueError("project_id is required when saving symbols")
        with psycopg.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                for i, symbol in enumerate(symbols):
                    embedding = embeddings[i] if embeddings else None
                    cur.execute(
                        f"""
                        INSERT INTO {self.table_name} (project_id, name, symbol_type, file_path, start_line, end_line, code, docstring, parent_name, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            project_id,
                            symbol.name,
                            symbol.type.value,
                            symbol.file_path,
                            symbol.start_line,
                            symbol.end_line,
                            symbol.code,
                            symbol.docstring,
                            symbol.parent,
                            embedding,
                        ),
                    )
                conn.commit()

    def search_hybrid(
        self,
        query_text: str,
        query_embedding: List[float],
        limit: int = 10,
        project_id: Optional[str] = None,
    ):
        with psycopg.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                # 1. Split query into words for name matching
                words = [w.strip() for w in query_text.split() if len(w) > 3]

                # 2. Build SQL dynamically (return a NULL project_path for compatibility)
                sql = """
                SELECT name, symbol_type, file_path, project_id, NULL::text AS project_path, code, docstring,
                       (embedding <=> %s::vector) as distance,
                       (CASE
                """
                params: List[Any] = [query_embedding]

                # Add name-priority conditions
                if words:
                    sql += " WHEN ("
                    conditions = []
                    for w in words:
                        conditions.append("name ILIKE %s")
                        params.append(f"%{w}%")
                    sql += " OR ".join(conditions)
                    sql += ") THEN 0 ELSE 1 END) as name_priority"
                else:
                    sql += " ELSE 1 END) as name_priority"

                # WHERE clauses (only add project filter when provided)
                where_clauses = []
                if project_id:
                    where_clauses.append("project_id = %s")
                    params.append(project_id)

                where_clauses.append("name NOT IN ('Meta', 'AppConfig')")
                where_clauses.append(
                    "file_path NOT LIKE 'tests/%%'"
                )  # Ignore test files

                sql += (
                    f"\nFROM {self.table_name}\nWHERE "
                    + " AND ".join(where_clauses)
                    + "\nORDER BY name_priority ASC, distance ASC\nLIMIT %s\n"
                )
                params.append(limit)

                cur.execute(sql, params)
                return cur.fetchall()
