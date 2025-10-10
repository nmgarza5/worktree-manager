#!/bin/bash

# Installation script for worktree manager

set -e

INSTALL_DIR="$HOME/.local/bin"
SCRIPT_NAME="worktree"
WRAPPER_FILE="$HOME/.worktree-wrapper.sh"

echo "Installing worktree manager..."

# Create installation directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Copy the script
cp "$(dirname "$0")/worktree.py" "$INSTALL_DIR/$SCRIPT_NAME"
chmod +x "$INSTALL_DIR/$SCRIPT_NAME"

# Copy the shell wrapper
cp "$(dirname "$0")/worktree-shell-wrapper.sh" "$WRAPPER_FILE"

echo "✓ Installed to $INSTALL_DIR/$SCRIPT_NAME"
echo "✓ Shell wrapper installed to $WRAPPER_FILE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Configuring Shell"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Determine shell config file
SHELL_CONFIG=""
if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        SHELL_CONFIG="$HOME/.bash_profile"
    else
        SHELL_CONFIG="$HOME/.bashrc"
    fi
fi

# Check if installation directory is in PATH
PATH_NEEDS_ADDING="no"
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    PATH_NEEDS_ADDING="yes"
fi

# Check if wrapper is already sourced in config
WRAPPER_NEEDS_ADDING="yes"
if [[ -f "$SHELL_CONFIG" ]] && grep -q "source.*worktree-wrapper.sh" "$SHELL_CONFIG"; then
    WRAPPER_NEEDS_ADDING="no"
fi

# Add to shell config if needed
if [[ -n "$SHELL_CONFIG" ]]; then
    if [[ "$PATH_NEEDS_ADDING" == "yes" ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG"
        echo "✓ Added PATH to $SHELL_CONFIG"
    else
        echo "✓ PATH already configured"
    fi

    if [[ "$WRAPPER_NEEDS_ADDING" == "yes" ]]; then
        echo 'source ~/.worktree-wrapper.sh' >> "$SHELL_CONFIG"
        echo "✓ Added shell wrapper to $SHELL_CONFIG"
    else
        echo "✓ Shell wrapper already configured"
    fi

    echo ""
    echo "✓ Reloading shell configuration..."
    # Source the wrapper in the current shell
    if [[ -n "$BASH_VERSION" ]]; then
        # For bash
        source "$WRAPPER_FILE" 2>/dev/null && echo "✓ Shell wrapper activated in current session"
    elif [[ -n "$ZSH_VERSION" ]]; then
        # For zsh
        source "$WRAPPER_FILE" 2>/dev/null && echo "✓ Shell wrapper activated in current session"
    fi
    echo ""
    echo "Ready to use! Open new terminals to have it auto-loaded."
else
    echo "⚠ Could not detect shell config file"
    echo ""
    echo "Manually add these lines to your shell config:"
    if [[ "$PATH_NEEDS_ADDING" == "yes" ]]; then
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
    echo "  source ~/.worktree-wrapper.sh"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Usage"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Configure repositories:"
echo "    worktree repo add <alias> <path>"
echo "    worktree repo list"
echo ""
echo "  Manage worktrees:"
echo "    worktree <alias> new <name>        Create worktree"
echo "    worktree <alias> list              List worktrees"
echo "    worktree <alias> select <name>     Switch to worktree (auto-cd!)"
echo "    worktree <alias> rm <name>         Remove worktree"
echo ""
