from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SymbolType(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE = "type"
    MODULE = "module"

class Symbol(BaseModel):
    name: str
    type: SymbolType
    file_path: str
    start_line: int
    end_line: int
    code: str
    parent: Optional[str] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)

class Document(BaseModel):
    page_content: str
    metadata: Dict[str, Any]

class SearchResult(BaseModel):
    content: str
    source: str
    relevance: float
    metadata: Optional[Dict[str, Any]] = None
    type: str = "semantic" # or "symbolic"
