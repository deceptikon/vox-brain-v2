import os
import yaml
import inspect
from pathlib import Path
from typing import Optional, Any
from mcp.server.fastmcp import FastMCP
from makefun import create_function

from vox_unified.manager import VoxManager

# Initialize Manager
manager = VoxManager()

# Initialize MCP
mcp = FastMCP("VOX Unified", dependencies=["psycopg", "pgvector", "ollama", "sqlite3"])

# Load Config
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "commands.yaml"
with open(CONFIG_PATH, "r") as f:
    COMMANDS_CONFIG = yaml.safe_load(f)

TYPE_MAP = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "array": list 
}

def create_mcp_wrapper(func_name, method, help_text, params_config):
    parameters = []
    
    # SYSTEMIC FIX: Required arguments must come before default arguments in Python signatures.
    # We sort the config to ensure correct order.
    sorted_params = sorted(params_config, key=lambda x: not x.get("required", False))

    for param in sorted_params:
        name = param["name"].replace("-", "_")
        p_type_str = param.get("type", "string")
        py_type = TYPE_MAP.get(p_type_str, str)
        
        default_val = param.get("default")
        is_required = param.get("required", False)
        
        if not is_required:
            annotation = Optional[py_type]
            default = default_val
        else:
            annotation = py_type
            default = inspect.Parameter.empty

        param_obj = inspect.Parameter(
            name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=default,
            annotation=annotation
        )
        parameters.append(param_obj)

    sig = inspect.Signature(parameters)


    async def wrapper(**kwargs):
        try:
            result = method(**kwargs)
            if result is not None:
                # FastMCP handles dicts/lists as JSON automatically
                return result
            return "Command executed successfully."
        except Exception as e:
            return f"Error: {e}"


    dynamic_func = create_function(sig, wrapper, func_name=func_name, doc=help_text)
    return dynamic_func


# Register Tools from YAML
for group_name, commands in COMMANDS_CONFIG.items():
    if group_name == "server": continue

    for cmd_name, cmd_config in commands.items():
        tool_name = f"{group_name}_{cmd_name}"
        method_name = f"{group_name}_{cmd_name}"
        
        if not hasattr(manager, method_name): continue
            
        method = getattr(manager, method_name)
        
        wrapper = create_mcp_wrapper(
            func_name=tool_name,
            method=method,
            help_text=cmd_config.get("description", ""),
            params_config=cmd_config.get("parameters", [])
        )
        
        mcp.tool(name=tool_name)(wrapper)

# --- MCP Resources & Prompts ---

@mcp.resource("vox://{project_id}/skeleton/{file_path}")
def get_skeleton(project_id: str, file_path: str) -> str:
    """Read a lightweight skeleton of a file (signatures only)."""
    return manager.get_file_skeleton(project_id, file_path)

@mcp.resource("vox://{project_id}/tree")
def get_tree(project_id: str) -> str:
    """Get the full file tree of the project."""
    return manager.get_project_tree(project_id)

@mcp.prompt("onboard")
def onboard_prompt(project_id: str) -> str:
    """
    Guides an Agent to understand the project structure, rules, and how to use VOX tools.
    """
    tree = manager.get_project_tree(project_id)
    # Get rules from SQLite
    docs = manager.datalayer.local.list_documents(project_id)
    rules = [d['content'] for d in docs if d['type'] == 'rule']
    rules_text = "\n".join(rules) if rules else "No specific rules defined."
    
    return f"""
    You are onboarding to Project ID: {project_id}. 
    
    ### STRATEGY FOR CONTEXT
    1.  **Search First**: Use 'search_run' to find relevant code or docs.
    2.  **Locate Source**: Every search result contains a 'source' (file path). 
    3.  **Read Deep**: Don't rely on search snippets alone. Use 'vox://{project_id}/skeleton/<path>' to see the file structure, or use your standard file-reading tools to read the actual file at the 'source' path.
    4.  **Follow Rules**: Adhere to the project rules listed below.

    ### PROJECT RULES
    {rules_text}

    ### PROJECT STRUCTURE
    {tree}
    """


import logging
import sys

def run(verbose: bool = False):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr
    )
    # FastMCP might have its own logger, we can set it too
    logging.getLogger("mcp").setLevel(log_level)
    
    mcp.run()

