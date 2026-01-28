import os
import uuid
import json
from typing import Optional, List, Dict, Any
from vox_unified.gatherer import Gatherer
from vox_unified.datalayer import DataLayer
from vox_unified.embeddings import get_ollama_embedding
from vox_unified.middleware import CacheLayer, TransformerLayer

class VoxManager:
    def __init__(self):
        self.datalayer = DataLayer()
        self.gatherer = Gatherer()
        self.cache = CacheLayer(self.datalayer.local.db_path)

    # --- PROJECT ---
    def project_create(self, path: str, name: Optional[str] = None):
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            print(f"❌ Error: Path {abs_path} does not exist.")
            return

        existing = self.datalayer.local.get_project_by_path(abs_path)
        if existing:
            print(f"ℹ️ Project already registered: {existing['name']} (ID: {existing['id']})")
            return existing['id']

        project_id = uuid.uuid4().hex[:16]
        project_name = name or os.path.basename(abs_path)
        
        self.datalayer.local.add_project(project_id, project_name, abs_path)
        print(f"✅ Project registered: {project_name} (ID: {project_id})")
        return project_id

    def project_list(self):
        projects = self.datalayer.local.list_projects()
        if not projects:
            print("No projects registered.")
            return
        
        print(f"{'ID':<20} {'Name':<20} {'Path'}")
        print("-" * 60)
        for p in projects:
            print(f"{p['id']:<20} {p['name']:<20} {p['path']}")

    def project_delete(self, project_id: str):
        self.datalayer.local.delete_project(project_id)
        self.datalayer.vector.delete_project_data(project_id)
        self.cache.invalidate(project_id)
        print(f"✅ Deleted project {project_id}")

    def project_stats(self, project_id: str):
        print("Stats not implemented.")

    def get_project_tree(self, project_id: str):
        # 1. Try Cache
        cached = self.cache.get(project_id, "file_tree")
        if cached:
            return cached
            
        # 2. Build Tree
        proj = self.datalayer.local.get_project(project_id)
        if not proj: return "Project not found"
        
        tree = []
        for root, dirs, files in os.walk(proj['path']):
            level = root.replace(proj['path'], '').count(os.sep)
            indent = ' ' * 4 * level
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                tree.append(f"{subindent}{f}")
        
        tree_str = "\n".join(tree)
        self.cache.set(project_id, "file_tree", tree_str)
        return tree_str

    # --- INDEX ---
    def index_build(self, project_id: str, type: str = "all", force: bool = False):
        project = self.datalayer.local.get_project(project_id)
        if not project:
            print(f"❌ Project {project_id} not found.")
            return

        print(f"🚀 Building index for {project['name']}...")

        if force:
            self.datalayer.vector.delete_project_data(project_id)
            self.cache.invalidate(project_id)

        # Re-cache tree immediately
        self.get_project_tree(project_id)

        # Scan
        text_chunks, symbols = self.gatherer.scan_project(project['path'])
        
        # Local Docs
        local_docs = self.datalayer.local.get_all_documents_for_indexing(project_id)
        for doc in local_docs:
            text_chunks.append({
                "content": f"Title: {doc.get('title')}\n{doc['content']}",
                "type": doc['type'],
                "source": "local_db"
            })

        # Embed Symbols
        if type in ["all", "symbolic"] and symbols:
            print(f"Embedding {len(symbols)} symbols...")
            sym_embeddings = []
            batch_texts = []
            for s in symbols:
                batch_texts.append(f"{s.type} {s.name}\n{s.code[:200]}")
            
            for txt in batch_texts:
                sym_embeddings.append(get_ollama_embedding(txt))

            self.datalayer.vector.save_symbols(symbols, project_id, sym_embeddings)
            print("✅ Symbols indexed.")

        # Embed Text
        if type in ["all", "semantic"] and text_chunks:
            print(f"Embedding {len(text_chunks)} text blocks...")
            text_embeddings = []
            for chunk in text_chunks:
                text_embeddings.append(get_ollama_embedding(chunk["content"]))
            
            self.datalayer.vector.save_text_chunks(text_chunks, project_id, text_embeddings)
            print("✅ Text data indexed.")

    def index_update(self, project_id: str):
        self.index_build(project_id, force=False)

    # --- DOCS ---
    def docs_add(self, project_id: str, content: Optional[str] = None, from_file: Optional[str] = None, type: str = "note", title: Optional[str] = None):
        if not content and not from_file:
            print("❌ Must provide content or file.")
            return

        final_content = content
        if from_file:
            try:
                with open(from_file, 'r') as f:
                    final_content = f.read()
            except Exception as e:
                print(f"Error reading file: {e}")
                return

        doc_id = self.datalayer.local.add_document(project_id, type, final_content, title, from_file)
        print(f"✅ Doc saved locally (ID: {doc_id}).")

        print("Syncing to vector search...")
        text_to_embed = f"Title: {title}\n{final_content}" if title else final_content
        emb = get_ollama_embedding(text_to_embed)
        
        chunk = {
            "content": text_to_embed,
            "type": type
        }
        self.datalayer.vector.save_text_chunks([chunk], project_id, [emb])
        print("✅ Doc indexed for search.")

    def docs_list(self, project_id: str):
        docs = self.datalayer.local.list_documents(project_id)
        for d in docs:
            print(f"[{d['id']}] {d['type'].upper()}: {d['title'] or 'No Title'} (Created: {d['created_at']})")

    def docs_get(self, project_id: str, doc_id: str):
        pass
        
    def docs_delete(self, project_id: str, doc_id: str):
        self.datalayer.local.delete_document(int(doc_id))
        print(f"✅ Document {doc_id} deleted locally. Run 'vox index build' to purge from search.")

    # --- SEARCH ---
    def search_semantic(self, query: str, project_id: Optional[str] = None, limit: int = 10):
        emb = get_ollama_embedding(query)
        results = self.datalayer.vector.search_text(emb, project_id, limit)
        for r in results:
            print(f"- [{r.relevance:.2f}] {r.content[:100]}...")
        return results

    def search_symbolic(self, query: str, project_id: Optional[str] = None, limit: int = 10):
        emb = get_ollama_embedding(query)
        results = self.datalayer.vector.search_symbols(query, emb, project_id, limit)
        for r in results:
            print(f"- [{r.relevance:.2f}] {r.content.splitlines()[0]}")
        return results

    def search_auto(self, query: str, project_id: Optional[str] = None):
        print("=== Text/Docs ===")
        self.search_semantic(query, project_id, 5)
        print("\n=== Code/Symbols ===")
        self.search_symbolic(query, project_id, 5)

    # --- ASK ---
    def ask_question(self, question: str, project_id: str, model: Optional[str] = None, reset_history: bool = False):
        emb = get_ollama_embedding(question)
        text_hits = self.datalayer.vector.search_text(emb, project_id, 5)
        sym_hits = self.datalayer.vector.search_symbols(question, emb, project_id, 5)
        
        context = "### DOCUMENTATION / NOTES\n"
        for t in text_hits:
            context += f"{t.content}\n---\n"
            
        context += "\n### CODE SYMBOLS\n"
        for s in sym_hits:
            context += f"{s.content}\n---\n"
            
        prompt = f"Question: {question}\n\nContext:\n{context}"
        
        import ollama
        resp = ollama.chat(model=model or "gemma3:4b-it-qat", messages=[{"role": "user", "content": prompt}])
        print(resp['message']['content'])
        return resp['message']['content']
    
    # --- UTILS for Agents ---
    def get_file_skeleton(self, project_id: str, file_path: str):
        proj = self.datalayer.local.get_project(project_id)
        if not proj: return "Project not found"
        
        abs_path = os.path.join(proj['path'], file_path)
        if not os.path.exists(abs_path): return "File not found"
        
        try:
            with open(abs_path, 'r') as f:
                code = f.read()
            return TransformerLayer.generate_skeleton(code, file_path)
        except Exception as e:
            return f"Error reading file: {e}"

    # --- SERVER ---
    def server_start(self):
        from vox_unified.mcpserver import run
        run()

    def server_status(self):
        pass
