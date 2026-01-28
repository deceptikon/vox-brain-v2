import os
import yaml
import inspect
import typer
from typing import Optional, Any, get_type_hints
from pathlib import Path
from makefun import create_function

from vox_unified.manager import VoxManager

app = typer.Typer(name="vox", help="VOX Unified CLI")
manager = VoxManager()

# Load Commands Config
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "commands.yaml"
with open(CONFIG_PATH, "r") as f:
    COMMANDS_CONFIG = yaml.safe_load(f)

# Type Mapping
TYPE_MAP = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "array": list 
}

def generate_signature(params_config):
    """
    Generates a signature string for makefun.
    """
    sig_parts = []
    
    # We must explicitly list parameters to preserve order and defaults
    for param in params_config:
        name = param["name"].replace("-", "_")
        p_type = TYPE_MAP.get(param.get("type"), str)
        default = param.get("default")
        required = param.get("required", False)
        
        type_name = p_type.__name__
        
        if not required:
            # Optional param
            # For Typer, we use typer.Option or defaults
            if default is not None:
                # Handle string quoting for default values in signature string
                if isinstance(default, str):
                    def_val = f"'{default}'"
                else:
                    def_val = str(default)
                sig_parts.append(f"{name}: {type_name} = {def_val}")
            else:
                sig_parts.append(f"{name}: Optional[{type_name}] = None")
        else:
            # Required param
            # In Typer, arguments are required by default if no default provided
            sig_parts.append(f"{name}: {type_name}")
            
    return f"({', '.join(sig_parts)})"

def create_command_wrapper(func_name, method, help_text, params_config):
    """
    Creates a wrapper function with the correct signature for Typer.
    """
    
    # 1. Define the signature
    # makefun requires a string signature 'func(a, b=1)'
    
    params_str = []
    for param in params_config:
        name = param["name"].replace("-", "_")
        p_type = param.get("type", "string")
        is_required = param.get("required", False)
        default = param.get("default")
        desc = param.get("description", "")
        
        # Typer Annotation Construction
        # We need to pass the actual python type and typer.Option/Argument to makefun
        # But makefun accepts a string signature. 
        # Actually makefun.create_function(signature, func)
        # It's easier to build the Signature object from inspect.Signature
        pass

    # Re-approach: Construct inspect.Signature manually
    parameters = []
    for param in params_config:
        name = param["name"].replace("-", "_")
        p_type_str = param.get("type", "string")
        py_type = TYPE_MAP.get(p_type_str, str)
        
        default_val = param.get("default")
        is_required = param.get("required", False)
        desc = param.get("description", "")
        
        # Typer specific: use typer.Option for flags/options, typer.Argument for positional?
        # Heuristic: if it's in the CLI alias as <arg>, it's Argument. If --arg, it's Option.
        # But for simplicity, let's treat required as Arguments and optional as Options.
        
        typer_info = typer.Option(default_val if default_val is not None else ..., help=desc) if not is_required else typer.Argument(..., help=desc)
        
        # If optional and no default, default is None
        if not is_required and default_val is None:
             typer_info = typer.Option(None, help=desc)

        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        
        # For bool flags, Typer expects bool = False
        if p_type_str == "boolean" and not is_required:
             if default_val is None: default_val = False
             typer_info = typer.Option(default_val, help=desc)
        
        param_obj = inspect.Parameter(
            name,
            kind,
            default=typer_info,
            annotation=py_type if is_required else Optional[py_type]
        )
        parameters.append(param_obj)

    sig = inspect.Signature(parameters)

    # 2. implementation that calls manager method
    def wrapper(**kwargs):
        # Map kwargs back to method args if needed, or just pass strictly
        # Manager methods should define args matching yaml names
        return method(**kwargs)

    # 3. Create dynamic function
    dynamic_func = create_function(sig, wrapper, func_name=func_name, doc=help_text)
    return dynamic_func


# --- Dynamic Registration ---

for group_name, commands in COMMANDS_CONFIG.items():
    # Create a Typer group
    group_app = typer.Typer(help=f"Manage {group_name}")
    app.add_typer(group_app, name=group_name)
    
    for cmd_name, cmd_config in commands.items():
        # Resolve manager method
        method_name = f"{group_name}_{cmd_name}"
        if not hasattr(manager, method_name):
            print(f"⚠️ Warning: Implementation for {method_name} not found in Manager.")
            continue
            
        method = getattr(manager, method_name)
        
        # Create dynamic wrapper
        dynamic_cmd = create_command_wrapper(
            func_name=cmd_name,
            method=method,
            help_text=cmd_config.get("description", ""),
            params_config=cmd_config.get("parameters", [])
        )
        
        # Register with Typer
        group_app.command(name=cmd_name)(dynamic_cmd)

# Register root alias 'ask' -> ask question
# Special case from YAML alias "vox ask"
# We can just manually bind it or add logic. For now, strict group structure is safer SSoT.

def main():
    app()