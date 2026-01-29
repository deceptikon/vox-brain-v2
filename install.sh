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

# Generate completion script
# We pipe it to the file _vox. 
# Note: Typer generates completion for the script name it sees. 
# We might need to replace the script name in the generated file if it doesn't match 'vox'.
COMPLETION_FILE="$ZSH_COMP_DIR/_vox"
uv run --project "$PROJECT_DIR" vox --show-completion zsh > "$COMPLETION_FILE"

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
if [[ ":$PATH:" != ":::$BIN_DIR:"* ]]; then
    echo "⚠️  Warning: $BIN_DIR is not in your PATH."
    echo "   Add this to your shell config ($SHELL_CONFIG):"
    echo "   export PATH=\"$\"$HOME/.local/bin:$PATH\""
fi

# Check fpath for Zsh
if [ -n "$ZSH_VERSION" ] || [[ "$SHELL" == *"zsh"* ]]; then
    echo "ℹ️  Zsh detected. Ensure fpath includes $ZSH_COMP_DIR"
    echo "   Add this to your .zshrc BEFORE compinit:"
    echo "   fpath=(\"
$HOME/.local/share/zsh/site-functions\" \
$fpath)"
    echo "   autoload -U compinit; compinit"
fi

echo "🎉 Done! You can now run 'vox'. Restart your shell to apply completion."
