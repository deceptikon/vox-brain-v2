# Unified VOX Brain

Hybrid RAG System (SQLite + Postgres + pgvector).

## Architecture

1.  **Registry & Metadata (SQLite)**: `~/.vox-brain/context/vox_meta.db`.
2.  **Symbolic Data (Postgres)**: Table `vox_symbols`.
3.  **Semantic/Text Data (Postgres)**: Table `vox_textdata`.

## Commands SSoT

All CLI and MCP commands are dynamically generated from `config/commands.yaml`.

## Installation (Native UV)

```bash
cd vox-unified
./install.sh
source ~/.zshrc # or your shell config
```

## Usage

```bash
# Register
vox project create /path/to/project

# Index (Smart AST + Markdown Header Split)
vox index build <vxid>

# Docs (Saved to SQLite + Indexed in Postgres)
vox docs add --project_id <vxid> --title "My Rule" --content "Always use tabs" --type rule

# Search
vox search auto "How to auth?"
```

## Development

To add a command:
1.  Add it to `config/commands.yaml`.
2.  Implement `group_name_command_name` method in `src/vox_unified/manager.py`.
3.  Run `vox <command>`.
