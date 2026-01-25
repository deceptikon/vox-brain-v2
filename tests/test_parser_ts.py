import pytest
from core.models import SymbolType
from core.parser_ts import TSParser

def test_extract_ts_symbols():
    code = """
interface UserProps {
    id: number;
    name: string;
}

export const UserProfile = ({ id, name }: UserProps) => {
    return <div>{name}</div>;
};

function InternalHelper() {
    return null;
}
"""
    parser = TSParser()
    symbols = parser.parse_text(code, "component.tsx")
    
    # Должны найти Interface, const UserProfile и function InternalHelper
    assert any(s.name == "UserProps" and s.type == SymbolType.INTERFACE for s in symbols)
    assert any(s.name == "UserProfile" and s.type == SymbolType.FUNCTION for s in symbols)
    assert any(s.name == "InternalHelper" and s.type == SymbolType.FUNCTION for s in symbols)
