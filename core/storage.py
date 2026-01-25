import os
import psycopg
from pgvector.psycopg import register_vector
from typing import List, Optional
from core.models import Symbol, SymbolType
from dotenv import load_dotenv

class Storage:
    def __init__(self, env_path: str = None):
        if env_path:
            load_dotenv(env_path)
        
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

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS symbols (
                        id SERIAL PRIMARY KEY,
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
                cur.execute("CREATE INDEX IF NOT EXISTS symbols_embedding_idx ON symbols USING ivfflat (embedding vector_cosine_ops)")
                cur.execute("CREATE INDEX IF NOT EXISTS symbols_name_idx ON symbols (name)")

    def save_symbols(self, symbols: List[Symbol], embeddings: List[List[float]] = None):
        with psycopg.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                for i, symbol in enumerate(symbols):
                    embedding = embeddings[i] if embeddings else None
                    cur.execute("""
                        INSERT INTO symbols (name, symbol_type, file_path, start_line, end_line, code, docstring, parent_name, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        symbol.name, 
                        symbol.type.value, 
                        symbol.file_path, 
                        symbol.start_line, 
                        symbol.end_line, 
                        symbol.code, 
                        symbol.docstring, 
                        symbol.parent, 
                        embedding
                    ))
                conn.commit()

    def search_hybrid(self, query_text: str, query_embedding: List[float], limit: int = 10):
        with psycopg.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                # 1. Разбираем запрос на слова для поиска по именам
                words = [w.strip() for w in query_text.split() if len(w) > 3]
                
                # 2. Строим SQL с динамическим количеством условий ILIKE
                sql = """
                SELECT name, symbol_type, file_path, code, docstring, 
                       (embedding <=> %s::vector) as distance,
                       (CASE 
                """
                
                params = [query_embedding]
                
                # Добавляем веса для каждого слова в имени
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

                sql += """
                FROM symbols
                WHERE name NOT IN ('Meta', 'AppConfig') 
                  AND file_path NOT LIKE 'tests/%%' -- Игнорируем тесты по умолчанию
                ORDER BY name_priority ASC, distance ASC
                LIMIT %s
                """
                params.append(limit)
                
                cur.execute(sql, params)
                return cur.fetchall()
