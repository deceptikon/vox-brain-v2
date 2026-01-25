import tree_sitter_python
from tree_sitter import Language, Parser
from core.models import Symbol, SymbolType
from typing import List

class PythonParser:
    def __init__(self):
        self.PY_LANGUAGE = Language(tree_sitter_python.language())
        self.parser = Parser(self.PY_LANGUAGE)

    def parse_text(self, code: str, file_path: str) -> List[Symbol]:
        code_bytes = bytes(code, "utf8")
        tree = self.parser.parse(code_bytes)
        symbols = []
        
        # Рекурсивно обходим дерево
        self._traverse(tree.root_node, code_bytes, file_path, symbols)
        return symbols

    def _get_text(self, node, code_bytes):
        return code_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")

    def _traverse(self, node, code_bytes, file_path, symbols, parent_name=None):
        symbol = None
        current_name = None

        if node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                current_name = self._get_text(name_node, code_bytes)
                docstring = self._extract_docstring(node, code_bytes)
                symbol = Symbol(
                    name=current_name,
                    type=SymbolType.CLASS,
                    file_path=file_path,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    code=self._get_text(node, code_bytes),
                    docstring=docstring,
                    parent=parent_name
                )

        elif node.type == 'function_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                current_name = self._get_text(name_node, code_bytes)
                docstring = self._extract_docstring(node, code_bytes)
                stype = SymbolType.METHOD if parent_name else SymbolType.FUNCTION
                symbol = Symbol(
                    name=current_name,
                    type=stype,
                    file_path=file_path,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    code=self._get_text(node, code_bytes),
                    docstring=docstring,
                    parent=parent_name
                )

        if symbol:
            symbols.append(symbol)

        # Рекурсия для детей (чтобы найти методы внутри класса)
        for child in node.children:
            self._traverse(child, code_bytes, file_path, symbols, parent_name=current_name or parent_name)

    def _extract_docstring(self, node, code_bytes):
        body = node.child_by_field_name('body')
        if body and body.children:
            for child in body.children:
                if child.type == 'expression_statement':
                    string_node = child.named_child(0)
                    if string_node and string_node.type == 'string':
                        return self._get_text(string_node, code_bytes).strip('\"\' ')
                if child.type not in ['comment']:
                    break # Only first non-comment statement can be docstring
        return None
