import pytest
from core.models import SymbolType
# We will implement the actual parser in core/parser.py
# For now, this test will fail as expected (TDD)

def test_extract_python_symbols():
    from core.parser import PythonParser
    
    code = """
class AppointmentManager:
    \"\"\"Manages appointments logic.\"\"\"
    def create_appointment(self, date: str):
        pass

def global_helper():
    return True
"""
    parser = PythonParser()
    symbols = parser.parse_text(code, "test.py")
    
    assert len(symbols) == 3
    
    # Check Class
    cls = next(s for s in symbols if s.type == SymbolType.CLASS)
    assert cls.name == "AppointmentManager"
    assert cls.docstring == "Manages appointments logic."
    
    # Check Method
    method = next(s for s in symbols if s.type == SymbolType.METHOD)
    assert method.name == "create_appointment"
    assert method.parent == "AppointmentManager"
    
    # Check Global Function
    func = next(s for s in symbols if s.type == SymbolType.FUNCTION)
    assert func.name == "global_helper"
    assert func.parent is None
