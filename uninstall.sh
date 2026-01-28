#!/bin/bash

echo "🗑️ Uninstalling VOX Unified..."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Remove Alias
SHELL_CONFIG=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

if [ -n "$SHELL_CONFIG" ]; then
    sed -i '/alias vox=/d' "$SHELL_CONFIG"
    echo "✅ Alias removed from $SHELL_CONFIG"
fi

# 2. Remove venv
if [ -d "$PROJECT_DIR/.venv" ]; then
    rm -rf "$PROJECT_DIR/.venv"
    echo "✅ Virtual environment removed."
fi

# 3. Optional: Clean logs/data?
read -p "Do you want to delete all VOX data (~/.vox-brain)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf ~/.vox-brain
    echo "✅ Data directory removed."
fi

echo "👋 Uninstallation complete."
