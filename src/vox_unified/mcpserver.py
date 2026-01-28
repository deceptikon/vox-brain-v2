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
mcp = FastMCP("VOX Unified", dependencies=["chromadb", "psycopg", "pgvector", "ollama"])

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
    # Construct signature for FastMCP (Pydantic validation under hood)
    parameters = []
    for param in params_config:
        name = param["name"].replace("-", "_")
        p_type_str = param.get("type", "string")
        py_type = TYPE_MAP.get(p_type_str, str)
        
        default_val = param.get("default")
        is_required = param.get("required", False)
        
        # FastMCP uses standard Python typing for validation
        if not is_required:
            annotation = Optional[py_type]
            default = default_val # Can be None
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

    # Wrapper must be async for FastMCP best practice, though sync works too.
    # We'll make it async and call the sync manager method.
    async def wrapper(**kwargs):
        # We might need to handle output capture since Manager prints to stdout for CLI
        # But for now, we just return the result of the method if it returns something,
        # or capture stdout if it doesn't.
        # Manager methods generally print. Ideally Manager should return objects/strings.
        # We modified Manager to return values in some cases (ask_question).
        # For others, we might just return "Command executed."
        
        try:
            result = method(**kwargs)
            if result is not None:
                return str(result)
            return "Command executed successfully (check logs/stdout for details)."
        except Exception as e:
            return f"Error: {e}"

    # Create dynamic function
    dynamic_func = create_function(sig, wrapper, func_name=func_name, doc=help_text)
    return dynamic_func


# Register Tools
for group_name, commands in COMMANDS_CONFIG.items():
    # We skip 'server' group for MCP tools usually, as you don't start server from within server
    if group_name == "server":
        continue

    for cmd_name, cmd_config in commands.items():
        tool_name = f"{group_name}_{cmd_name}"
        method_name = f"{group_name}_{cmd_name}"
        
        if not hasattr(manager, method_name):
            continue
            
        method = getattr(manager, method_name)
        
        wrapper = create_mcp_wrapper(
            func_name=tool_name,
            method=method,
            help_text=cmd_config.get("description", ""),
            params_config=cmd_config.get("parameters", [])
        )
        
        mcp.tool(name=tool_name)(wrapper)

# Resources?
# We can statically define resources or map them if we had a config for resources.
# For now, we'll keep the static resources from previous implementation if needed, 
# but per request we strictly follow YAML command set for tools.
# Resources are strictly read-only access points, distinct from commands.

def run():
    mcp.run()