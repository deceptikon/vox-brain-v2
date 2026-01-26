import os
from typing import List, Optional

from core.embeddings import EmbeddingEngine
from core.models import Symbol
from core.parser import PythonParser
from core.parser_ts import TSParser
from core.storage import Storage


class VoxEngine:
    def __init__(self, env_path: str = None):
        self.storage = Storage(env_path)
        self.embeddings = EmbeddingEngine()
        self.py_parser = PythonParser()
        self.ts_parser = TSParser()

    def index_project(self, root_path: str, project_id: Optional[str] = None):
        all_symbols = []
        IGNORE_SUBDIRS = {
            "node_modules",
            "__pycache__",
            "migrations",
            "dist",
            "build",
            ".next",
            ".git",
        }

        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [
                d for d in dirnames if d not in IGNORE_SUBDIRS and not d.startswith(".")
            ]
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_path)
                ext = os.path.splitext(filename)[1]
                parser = (
                    self.py_parser
                    if ext == ".py"
                    else (
                        self.ts_parser
                        if ext in [".ts", ".tsx", ".js", ".jsx"]
                        else None
                    )
                )
                if parser:
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            code = f.read()
                        symbols = parser.parse_text(code, rel_path)
                        all_symbols.extend(symbols)
                    except Exception as e:
                        print(f"Error parsing {rel_path}: {e}")

        if not all_symbols:
            return

        batch_size = 100
        abspath = os.path.abspath(root_path)
        for i in range(0, len(all_symbols), batch_size):
            batch = all_symbols[i : i + batch_size]
            texts_to_embed = [
                f"{s.type} {s.name}\nFile: {s.file_path}\n"
                + "\n".join(s.code.split("\n")[:15])
                for s in batch
            ]
            embeddings = self.embeddings.get_embeddings(texts_to_embed)
            # save with canonical project id (hex)
            self.storage.save_symbols(batch, embeddings, project_id=project_id)

    def ask(self, question: str, project_id: Optional[str] = None):
        q_emb = self.embeddings.get_embeddings([question])[0]
        # USE HYBRID SEARCH (filter by project_id if provided)
        results = self.storage.search_hybrid(
            question, q_emb, limit=10, project_id=project_id
        )

        if not results:
            return "No results found in database."

        context = f"Found {len(results)} relevant symbols:\n\n"
        for r in results:
            # SELECT order: name, symbol_type, file_path, project_id, project_path, code, docstring, distance, name_priority
            name, stype, path, proj_id, proj_path, code, docs, dist, priority = r
            proj_tag = proj_id or proj_path or "unknown"
            context += f"--- {stype.upper()}: {name} ({path}) | Project: {proj_tag} | Priority: {priority} | Dist: {dist:.4f} ---\n"
            if docs:
                context += f"Docstring: {docs}\n"
            indented_code = "\n".join(["  " + line for line in code.split("\n")[:40]])
            context += f"{indented_code}\n\n"

        return context
