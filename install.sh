#!/bin/bash

# Installation script for worktree manager

set -e

INSTALL_DIR="$HOME/.local/bin"
SCRIPT_NAME="worktree"

echo "Installing worktree manager..."

# Create installation directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Copy the script
cp "$(dirname "$0")/worktree.py" "$INSTALL_DIR/$SCRIPT_NAME"
chmod +x "$INSTALL_DIR/$SCRIPT_NAME"

echo "✓ Installed to $INSTALL_DIR/$SCRIPT_NAME"

# Check if installation directory is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo "⚠ Warning: $INSTALL_DIR is not in your PATH"
    echo ""
    echo "Add the following line to your shell configuration file:"
    echo ""
    echo "For Zsh (default on macOS):"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
    echo "  source ~/.zshrc"
    echo ""
    echo "For Bash:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "  source ~/.bashrc"
    echo ""
    echo "For Bash (macOS/login shells):"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bash_profile"
    echo "  source ~/.bash_profile"
    echo ""
    echo "For Fish:"
    echo "  fish_add_path \$HOME/.local/bin"
    echo ""
    echo "Or manually add this line to your shell config:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
else
    echo ""
    echo "✓ Installation complete! You can now use 'worktree' command."
fi

echo ""
echo "Usage:"
echo "  worktree new <name>        Create a new worktree"
echo "  worktree list              List all worktrees"
echo "  worktree select <name>     Switch to a worktree"
echo "  worktree rm <name>         Remove a worktree"
