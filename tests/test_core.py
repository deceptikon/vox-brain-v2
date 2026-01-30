from vox_unified.middleware import TransformerLayer, CacheLayer
from vox_unified.datalayer import LocalMetaStorage

# --- TEST 1: Transformer (Skeleton) ---
def test_skeleton_keeps_imports_strips_body():
    code = """
import os
from typing import List

class MyClass:
    def __init__(self):
        self.x = 1
        print("Body logic")

    def method(self) -> int:
        return self.x
"""
    skeleton = TransformerLayer.generate_skeleton(code, "test.py")
    
    lines = skeleton.splitlines()
    assert "import os" in lines
    assert "from typing import List" in lines
    assert "class MyClass:" in lines
    assert "    def __init__(self):" in lines
    assert '        print("Body logic")' not in lines  # Body should be gone
    assert "    def method(self) -> int:" in lines

# --- TEST 2: Cache Layer ---
def test_cache_set_get(tmp_path):
    db_path = tmp_path / "cache.db"
    cache = CacheLayer(db_path)
    
    cache.set("proj_1", "my_key", {"foo": "bar"})
    
    result = cache.get("proj_1", "my_key")
    assert result == {"foo": "bar"}
    
    assert cache.get("proj_1", "wrong_key") is None

# --- TEST 3: Registry (SQLite) ---
def test_registry_create_project(tmp_path):
    # Mock HOME to use tmp_path
    import os
    os.environ["VOX_HOME"] = str(tmp_path)
    
    local = LocalMetaStorage()
    
    local.add_project("vx_123", "Test Project", "/tmp/code")
    
    proj = local.get_project("vx_123")
    assert proj is not None
    assert proj["name"] == "Test Project"
    assert proj["path"] == "/tmp/code"
    
    # Clean up env
    del os.environ["VOX_HOME"]
