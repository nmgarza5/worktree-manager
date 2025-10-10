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
    echo "  (e.g., ~/.bashrc, ~/.zshrc, ~/.bash_profile)"
    echo ""
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then restart your shell or run: source ~/.zshrc (or ~/.bashrc)"
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
