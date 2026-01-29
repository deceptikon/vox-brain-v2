import os
import yaml
import inspect
import typer
from typing import Optional, Any
from pathlib import Path
from makefun import create_function

from vox_unified.manager import VoxManager

# SSoT Constants
SYNONYMS = {
    "create": ["build", "add", "init", "new"],
    "build": ["create", "add", "init"],
    "list": ["ls", "show", "all"],
    "delete": ["remove", "rm", "purge"],
    "search": ["find", "query"],
    "ask": ["question", "chat"]
}

def get_app(name: str, help_text: str = ""):
    """Standardized App Factory for consistent behavior."""
    return typer.Typer(
        name=name, 
        help=help_text, 
        no_args_is_help=True, 
        add_completion=False,
        rich_markup_mode="rich"
    )

app = get_app("vox", "VOX Unified CLI")
manager = VoxManager()

# Load Commands Config
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "commands.yaml"
with open(CONFIG_PATH, "r") as f:
    COMMANDS_CONFIG = yaml.safe_load(f)

TYPE_MAP = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "array": list 
}

def resolve_manager_method(group: str, cmd: str):
    """
    Systemically resolves a manager method using semantic synonyms.
    Example: 'index create' -> tries manager.index_create, then manager.index_build.
    """
    # 1. Direct match
    direct_name = f"{group}_{cmd}"
    if hasattr(manager, direct_name):
        return getattr(manager, direct_name)
    
    # 2. Synonym match
    potential_synonyms = SYNONYMS.get(cmd, [])
    for syn in potential_synonyms:
        syn_name = f"{group}_{syn}"
        if hasattr(manager, syn_name):
            return getattr(manager, syn_name)
            
    return None

def create_command_wrapper(func_name, method, help_text, params_config):
    """Generates a Typer-compatible function with correct metadata."""
    parameters = []
    for param in params_config:
        name = param["name"].replace("-", "_")
        p_type_str = param.get("type", "string")
        py_type = TYPE_MAP.get(p_type_str, str)
        
        default_val = param.get("default")
        is_required = param.get("required", False)
        desc = param.get("description", "")
        
        if not is_required:
            typer_info = typer.Option(default_val, help=desc)
        else:
            typer_info = typer.Argument(..., help=desc)

        param_obj = inspect.Parameter(
            name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=typer_info,
            annotation=py_type if is_required else Optional[py_type]
        )
        parameters.append(param_obj)

    sig = inspect.Signature(parameters)
    def wrapper(**kwargs):
        return method(**kwargs)

    return create_function(sig, wrapper, func_name=func_name, doc=help_text)

# --- Systemic Registration ---
for group_name, commands in COMMANDS_CONFIG.items():
    group_app = get_app(group_name, f"Manage {group_name}")
    app.add_typer(group_app, name=group_name)
    
    # Track registered commands to avoid duplicates
    registered_cmds = set()

    for cmd_name, cmd_config in commands.items():
        # Smart Resolution
        method = resolve_manager_method(group_name, cmd_name)
        
        if not method:
            continue
            
        # Register the main command
        dynamic_cmd = create_command_wrapper(
            func_name=cmd_name,
            method=method,
            help_text=cmd_config.get("description", ""),
            params_config=cmd_config.get("parameters", [])
        )
        group_app.command(name=cmd_name)(dynamic_cmd)
        registered_cmds.add(cmd_name)

        # SYSTEMIC ALIASING: Register synonyms as hidden/extra commands
        synonyms = SYNONYMS.get(cmd_name, [])
        for syn in synonyms:
            if syn not in registered_cmds and syn not in commands:
                # Reuse the same wrapper/method but with a different name
                syn_cmd = create_command_wrapper(
                    func_name=syn,
                    method=method,
                    help_text=f"Alias for '{cmd_name}': {cmd_config.get('description', '')}",
                    params_config=cmd_config.get("parameters", [])
                )
                group_app.command(name=syn)(syn_cmd)
                registered_cmds.add(syn)


def main():
    app()

if __name__ == "__main__":
    main()
