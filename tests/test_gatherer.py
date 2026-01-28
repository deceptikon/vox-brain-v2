import pytest
from vox_unified.gatherer import Gatherer, PythonParser

def test_python_parser_extracts_symbols():
    parser = PythonParser()
    code = """
class Agent:
    def think(self):
        pass

def run_system():
    pass
"""
    symbols = parser.parse_text(code, "test.py")
    
    names = [s.name for s in symbols]
    assert "Agent" in names
    assert "think" in names
    assert "run_system" in names
    
    # Check types
    types = {s.name: s.type for s in symbols}
    assert types["Agent"] == "class"
    assert types["think"] == "method"
    assert types["run_system"] == "function"

def test_gatherer_markdown_splitting():
    gatherer = Gatherer()
    # Create a dummy md file content
    md_content = """# Title
Context for H1.
## Section A
Context for H2.
"""
    # Since scan_project works on files, we test the internal md_splitter logic 
    # indirectly or via a small refactor. 
    # For now, let's verify the splitter configuration in Gatherer.
    
    chunks = gatherer.md_splitter.split_text(md_content)
    assert len(chunks) >= 2
    assert "Title" in chunks[0].metadata.values() or "Title" in chunks[0].page_content
    assert "Section A" in chunks[1].metadata.values() or "Section A" in chunks[1].page_content

def test_gatherer_ignores_garbage_dirs(tmp_path):
    # Setup a temp project with a forbidden dir
    proj_dir = tmp_path / "my_proj"
    proj_dir.mkdir()
    (proj_dir / "node_modules").mkdir()
    (proj_dir / "node_modules" / "bad.py").write_text("print(1)")
    (proj_dir / "good.py").write_text("def ok(): pass")
    
    gatherer = Gatherer()
    text_chunks, symbols = gatherer.scan_project(str(proj_dir))
    
    # Should find ok() but NOT bad.py symbols
    names = [s.name for s in symbols]
    assert "ok" in names
    assert "print" not in str(names) # print is not a definition, but just in case
    
    # Check file paths
    files = [s.file_path for s in symbols]
    assert "good.py" in files
    assert any("node_modules" in f for f in files) == False
