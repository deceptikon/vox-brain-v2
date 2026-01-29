import pytest
import os
from vox_unified.manager import VoxManager

def test_manager_initialization(tmp_path):
    """
    Checks if Manager can be initialized without Syntax/Name errors.
    """
    os.environ["VOX_HOME"] = str(tmp_path)
    # This will trigger imports of datalayer, gatherer, middleware, etc.
    try:
        mgr = VoxManager()
        assert mgr is not None
    except Exception as e:
        pytest.fail(f"Manager failed to initialize: {e}")

def test_manager_methods_exist():
    """
    Ensures refactoring didn't accidentally hide methods inside other methods.
    """
    mgr = VoxManager()
    expected_methods = [
        "project_create", "project_list", "index_run", 
        "search_run", "ask_run", "docs_add", "server_start"
    ]
    for method in expected_methods:
        assert hasattr(mgr, method), f"Method {method} is missing from Manager!"

def test_server_start_import():
    """Checks if server_start can at least import its dependencies."""
    mgr = VoxManager()
    # We don't want to actually start the loop, but we check if the method is callable
    assert callable(mgr.server_start)

