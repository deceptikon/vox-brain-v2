import os
import yaml
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

# Tree-sitter
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser as TSParser

# LangChain (Header Splitter Only)
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from vox_unified.models import Symbol, SymbolType, Document

IGNORE_DIRS = {
    'node_modules', '.next', 'dist', 'build', '.vercel',
    'venv', '.venv', '__pycache__', '.git', '.github', '.vscode', 'tests'
}

class BaseParser:
    def _get_text(self, node, code_bytes):
        return code_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")

class PythonParser(BaseParser):
    def __init__(self):
        try:
            self.PY_LANGUAGE = Language(tree_sitter_python.language())
            self.parser = TSParser(self.PY_LANGUAGE)
        except Exception:
            self.parser = None

    def parse_text(self, code: str, file_path: str) -> List[Symbol]:
        if not self.parser: return []
        code_bytes = bytes(code, "utf8")
        try:
            tree = self.parser.parse(code_bytes)
        except Exception:
            return []
        
        symbols = []
        self._traverse(tree.root_node, code_bytes, file_path, symbols)
        return symbols

    def _traverse(self, node, code_bytes, file_path, symbols, parent_name=None):
        symbol = None
        current_name = None

        if node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                current_name = self._get_text(name_node, code_bytes)
                symbol = Symbol(
                    name=current_name,
                    type=SymbolType.CLASS,
                    file_path=file_path,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    code=self._get_text(node, code_bytes),
                    docstring="",
                    parent=parent_name
                )
        elif node.type == 'function_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                current_name = self._get_text(name_node, code_bytes)
                stype = SymbolType.METHOD if parent_name else SymbolType.FUNCTION
                symbol = Symbol(
                    name=current_name,
                    type=stype,
                    file_path=file_path,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    code=self._get_text(node, code_bytes),
                    parent=parent_name
                )

        if symbol:
            symbols.append(symbol)

        for child in node.children:
            self._traverse(child, code_bytes, file_path, symbols, parent_name=current_name or parent_name)

class TypeScriptParser(BaseParser):
    def __init__(self, is_tsx=True):
        try:
            lang = tree_sitter_typescript.language_tsx() if is_tsx else tree_sitter_typescript.language_typescript()
            self.TS_LANGUAGE = Language(lang)
            self.parser = TSParser(self.TS_LANGUAGE)
        except Exception:
            self.parser = None

    def parse_text(self, code: str, file_path: str) -> List[Symbol]:
        if not self.parser: return []
        code_bytes = bytes(code, "utf8")
        try:
            tree = self.parser.parse(code_bytes)
        except Exception:
            return []
        
        symbols = []
        self._traverse(tree.root_node, code_bytes, file_path, symbols)
        return symbols

    def _traverse(self, node, code_bytes, file_path, symbols, parent_name=None):
        symbol = None
        current_name = None

        # Capture Classes, Interfaces, Types, and Functions/Methods
        if node.type in ['class_declaration', 'interface_declaration', 'type_alias_declaration']:
            name_node = node.child_by_field_name('name')
            if name_node:
                current_name = self._get_text(name_node, code_bytes)
                stype = SymbolType.CLASS if node.type == 'class_declaration' else SymbolType.OTHER
                symbol = Symbol(
                    name=current_name,
                    type=stype,
                    file_path=file_path,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    code=self._get_text(node, code_bytes),
                    parent=parent_name
                )
        elif node.type in ['function_declaration', 'method_definition', 'function_expression', 'arrow_function']:
            # For methods/functions, finding the name is trickier in TS tree
            name_node = node.child_by_field_name('name')
            if not name_node and node.type == 'method_definition':
                name_node = node.child_by_field_name('name') # Usually works for methods
            
            if name_node:
                current_name = self._get_text(name_node, code_bytes)
                stype = SymbolType.METHOD if parent_name else SymbolType.FUNCTION
                symbol = Symbol(
                    name=current_name,
                    type=stype,
                    file_path=file_path,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    code=self._get_text(node, code_bytes),
                    parent=parent_name
                )

        if symbol:
            symbols.append(symbol)

        for child in node.children:
            self._traverse(child, code_bytes, file_path, symbols, parent_name=current_name or parent_name)


class Gatherer:
    def __init__(self):
        self.py_parser = PythonParser()
        self.ts_parser = TypeScriptParser(is_tsx=True)
        # Smart Text Splitting: Only split by logical headers
        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")]
        )
        # Safety Splitter: For massive blocks (logs, huge code blocks) that defy headers
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )

    def scan_project(self, root_path: str) -> Tuple[List[Dict[str, Any]], List[Symbol]]:
        """
        Returns:
            text_chunks: List of dicts {content: str, type: str}
            symbols: List of Symbol objects
        """
        text_chunks = []
        symbols = []
        
        abs_root = os.path.abspath(root_path)
        print(f"🚀 Scanning project at: {abs_root}")

        for dirpath, dirnames, filenames in os.walk(abs_root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            
            # Skip .cursor directory in scan
            if '.cursor' in dirpath:
                continue

            for filename in filenames:
                file_ext = os.path.splitext(filename)[1].lower()
                full_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(full_path, abs_root)

                # 1. Code Symbols (.py, .ts, .tsx, .js, .jsx)
                if file_ext in ['.py', '.ts', '.tsx', '.js', '.jsx']:
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        file_symbols = []
                        if file_ext == '.py':
                            file_symbols = self.py_parser.parse_text(content, relative_path)
                        else:
                            file_symbols = self.ts_parser.parse_text(content, relative_path)
                            
                        symbols.extend(file_symbols)
                    except Exception:
                        pass

                # 2. Markdown Knowledge (.md)
                elif file_ext == '.md':
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        md_docs = self.md_splitter.split_text(content)
                        for doc in md_docs:
                            # Check size
                            if len(doc.page_content) > 1000:
                                # Recursively split large chunks
                                sub_docs = self.recursive_splitter.split_text(doc.page_content)
                                for sub in sub_docs:
                                    text_chunks.append({
                                        "content": sub,
                                        "type": "markdown",
                                        "source": relative_path
                                    })
                            else:
                                text_chunks.append({
                                    "content": doc.page_content,
                                    "type": "markdown",
                                    "source": relative_path
                                })
                    except Exception:
                        pass

        print(f"✅ Scan complete: {len(text_chunks)} text blocks, {len(symbols)} symbols.")
        return text_chunks, symbols