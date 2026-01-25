import tree_sitter_typescript
from tree_sitter import Language, Parser
from core.models import Symbol, SymbolType
from typing import List

class TSParser:
    def __init__(self):
        self.TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
        self.parser = Parser(self.TSX_LANGUAGE)

    def parse_text(self, code: str, file_path: str) -> List[Symbol]:
        code_bytes = bytes(code, "utf8")
        tree = self.parser.parse(code_bytes)
        symbols = []
        self._traverse(tree.root_node, code_bytes, file_path, symbols)
        return symbols

    def _get_text(self, node, code_bytes):
        return code_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")

    def _traverse(self, node, code_bytes, file_path, symbols, parent_name=None):
        symbol = None
        current_name = None

        if node.type in ['interface_declaration', 'type_alias_declaration']:
            name_node = node.child_by_field_name('name')
            if name_node:
                current_name = self._get_text(name_node, code_bytes)
                symbol = Symbol(
                    name=current_name,
                    type=SymbolType.INTERFACE if node.type == 'interface_declaration' else SymbolType.TYPE,
                    file_path=file_path,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    code=self._get_text(node, code_bytes),
                    parent=parent_name
                )

        elif node.type in ['function_declaration', 'lexical_declaration']:
            name = self._extract_js_func_name(node, code_bytes)
            if name:
                current_name = name
                symbol = Symbol(
                    name=current_name,
                    type=SymbolType.FUNCTION,
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

    def _extract_js_func_name(self, node, code_bytes):
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            return self._get_text(name_node, code_bytes) if name_node else None
        
        if node.type == 'lexical_declaration':
            decl = node.named_child(0)
            if decl and decl.type == 'variable_declarator':
                name_node = decl.child_by_field_name('name')
                return self._get_text(name_node, code_bytes) if name_node else None
        return None
