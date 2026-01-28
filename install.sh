#!/bin/bash
set -e

echo "🚀 Installing VOX Unified (uv-native)..."

# 1. Check for uv
if ! command -v uv &> /dev/null; then
    echo "⚠️ 'uv' is not installed. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# 2. Setup environment
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "📦 Synchronizing dependencies..."
uv sync

# 3. Setup CLI Alias (uv run based)
echo "🔗 Setting up 'vox' alias..."
SHELL_CONFIG=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

if [ -n "$SHELL_CONFIG" ]; then
    # Remove old aliases
    sed -i '/alias vox=/d' "$SHELL_CONFIG"
    # New alias uses 'uv run' with explicit project path to work from anywhere
    echo "alias vox='uv run --project $PROJECT_DIR vox'" >> "$SHELL_CONFIG"
    echo "✅ Alias added to $SHELL_CONFIG. Run 'source $SHELL_CONFIG' to apply."
else
    echo "⚠️ Could not find shell config. Add this manually:"
    echo "alias vox='uv run --project $PROJECT_DIR vox'"
fi

echo "🎉 Done! Usage: vox <command>"