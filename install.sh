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

# Create the wrapper script
cat <<EOF > "$WRAPPER_PATH"
#!/bin/bash
# Wrapper for VOX Unified CLI

# Set project directory
PROJECT_DIR="$PROJECT_DIR"

# If no arguments provided, default to --help
if [ \$# -eq 0 ]; then
    exec uv run --project "\$PROJECT_DIR" vox --help
else
    exec uv run --project "\$PROJECT_DIR" vox "\$@"
fi
EOF

chmod +x "$WRAPPER_PATH"

echo "✅ Installed '$WRAPPER_PATH'"

# 4. Setup Zsh Completion
echo "🐚 Setting up Zsh completion..."
ZSH_COMP_DIR="$HOME/.local/share/zsh/site-functions"
mkdir -p "$ZSH_COMP_DIR"

COMPLETION_FILE="$ZSH_COMP_DIR/_vox"
# We specifically ask Typer to generate Zsh completion
# The resulting script defines '_vox_completion' and calls 'compdef _vox_completion vox'
# BUT: Zsh autoloading expects the file '_vox' to contain the function body directly, or setup.
# Typer's output is designed to be SOURCED, not autoloaded via fpath usually.
# However, if we put it in fpath, we need to ensure it has the #compdef tag.

# Let's generate it and inspect/patch it.
uv run --project "$PROJECT_DIR" vox --show-completion zsh > "$COMPLETION_FILE"

# Patch: Add #compdef at the top if missing (Typer usually adds it)
if ! grep -q "#compdef vox" "$COMPLETION_FILE"; then
    sed -i '1i #compdef vox' "$COMPLETION_FILE"
fi

echo "✅ Generated completion at '$COMPLETION_FILE'"

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

# 6. Check PATH and FPATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "⚠️  Warning: $BIN_DIR is not in your PATH."
    echo "   Add this to your shell config ($SHELL_CONFIG):"
    echo "   export PATH=\"$\"$HOME/.local/bin:$PATH\""
fi

# Check fpath for Zsh
if [ -n "$ZSH_VERSION" ] || [[ "$SHELL" == *"zsh"* ]]; then
    # Create .vox2env if not exists
    touch "$HOME/.vox2env"
    
    echo "ℹ️  Zsh detected. To enable Completion and Aliases:"
    echo "   1. Add this to your ~/.zshrc (BEFORE compinit):"
    echo "      fpath=(\"$\"$HOME/.local/share/zsh/site-functions\" \$fpath)"
    echo "   2. Add this to your ~/.zshrc (anywhere):"
    echo "      source \$HOME/.vox2env"
    echo "   3. Run: rm -f ~/.zcompdump; compinit"
fi

echo "🎉 Done! Usage: vox <command>"