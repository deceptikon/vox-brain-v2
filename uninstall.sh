#!/bin/bash

echo "🗑️ Uninstalling VOX Unified..."

# 1. Remove Executable Wrapper
WRAPPER_PATH="$HOME/.local/bin/vox"
if [ -f "$WRAPPER_PATH" ]; then
    rm "$WRAPPER_PATH"
    echo "✅ Removed $WRAPPER_PATH"
else
    echo "ℹ️  Wrapper not found in ~/.local/bin"
fi

# 2. Clean up legacy aliases
SHELL_CONFIG=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

if [ -n "$SHELL_CONFIG" ]; then
    if grep -q "alias vox=" "$SHELL_CONFIG"; then
        sed -i '/alias vox=/d' "$SHELL_CONFIG"
        echo "✅ Removed legacy alias from $SHELL_CONFIG"
    fi
fi

# 3. Remove venv
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$PROJECT_DIR/.venv" ]; then
    rm -rf "$PROJECT_DIR/.venv"
    echo "✅ Virtual environment removed."
fi

# 4. Optional: Clean logs/data?
read -p "Do you want to delete all VOX data (~/.vox-brain)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf ~/.vox-brain
    echo "✅ Data directory removed."
fi

echo "👋 Uninstallation complete."