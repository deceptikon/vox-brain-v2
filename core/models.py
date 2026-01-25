from enum import Enum
from typing import List, Optional, Dict
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
    parent: Optional[str] = None # Name of parent symbol (e.g. class name for a method)
    signature: Optional[str] = None
    docstring: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list) # Imported symbols or calls

class FileSkeleton(BaseModel):
    file_path: str
    symbols: List[Symbol]
    imports: List[str]
