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

# 3. Setup CLI Wrapper in ~/.local/bin
echo "🔗 Setting up 'vox' executable in ~/.local/bin..."

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

WRAPPER_PATH="$BIN_DIR/vox"

# Create the wrapper script with Smart Fallback and Semantic Shortcuts
cat <<EOF > "$WRAPPER_PATH"
#!/bin/bash
PROJECT_DIR="$PROJECT_DIR"

# SEMANTIC SHORTCUTS: 
# If 'vox search' or 'vox ask' or 'vox index' is called without a valid subcommand
if [[ "\$1" == "search" || "\$1" == "ask" || "\$1" == "index" ]]; then
    if [[ "\$2" != "run" && "\$2" != "list" && "\$2" != "--help" && -n "\$2" ]]; then
        # Inject 'run' as the second argument
        set -- "\$1" "run" "\${@:2}"
    fi
fi

# Try running the command with --quiet to avoid extra info on stdout
uv run --quiet --project "\$PROJECT_DIR" vox "\$@"
EXIT_CODE=\$?

# If exit code is 2 (Typer usage error)
# AND we are NOT in completion mode (detected by _VOX_COMPLETE)
# AND we are NOT starting the server
if [ -z "\$_VOX_COMPLETE" ] && [[ "\$*" != *"server start"* ]]; then
    if [ \$EXIT_CODE -eq 2 ]; then
        if [ \$# -gt 0 ]; then
            echo -e "\n💡 [VOX Help Fallback]" >&2
            uv run --quiet --project "\$PROJECT_DIR" vox "\$@" --help >&2
        fi
    fi
fi

exit \$EXIT_CODE
EOF






chmod +x "$WRAPPER_PATH"

echo "✅ Installed '$WRAPPER_PATH'"

# 4. Cleanup old completion files that cause Zsh errors
echo "🧹 Cleaning up legacy completion files..."
ZSH_COMP_FILE="$HOME/.local/share/zsh/site-functions/_vox"
if [ -f "$ZSH_COMP_FILE" ]; then
    rm "$ZSH_COMP_FILE"
    echo "✅ Removed $ZSH_COMP_FILE"
fi

# 5. Clean up old aliases (legacy cleanup)
SHELL_CONFIG=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

if [ -n "$SHELL_CONFIG" ]; then
    if grep -q "alias vox=" "$SHELL_CONFIG"; then
        sed -i '/alias vox=/d' "$SHELL_CONFIG"
        echo "🧹 Removed legacy alias from $SHELL_CONFIG"
    fi
fi

# 6. Generate first version of ~/.vox2env (Aliases + Completion)
echo "🧬 Generating Aliases and Completion in ~/.vox2env..."
"$WRAPPER_PATH" project list > /dev/null

# 7. Check PATH and instructions
if [[ ":$PATH:" != ".*:"$BIN_DIR":"* ]]; then
    echo "⚠️  Warning: $BIN_DIR is not in your PATH."
    echo "   Add this to your shell config ($SHELL_CONFIG):"
    echo "   export PATH=\"$HOME/.local/bin:$PATH\""
fi

echo "ℹ️  To enable VOX features in your shell:"
echo "   1. Ensure 'source $HOME/.vox2env' is in your ~/.zshenv or ~/.zshrc."
echo "   2. Restart your shell (or 'exec zsh')."

echo "🎉 Done! Usage: vox <command>"
