#!/bin/bash
# Worktree Manager Shell Wrapper
# Auto-cd for 'new', 'select', and 'rm' commands

worktree() {
    # Check if this is a new command
    if [[ "$2" == "new" && -n "$3" ]]; then
        # Run the new command
        "$HOME/.local/bin/worktree" "$@"
        local exit_code=$?

        # If successful, cd into the new worktree
        if [[ $exit_code -eq 0 ]]; then
            # Extract the worktree path - strip ANSI color codes first
            local worktree_path
            worktree_path=$("$HOME/.local/bin/worktree" "$1" list 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -A 2 "✓ $3" | grep "Path:" | awk '{print $2}')

            if [[ -n "$worktree_path" && -d "$worktree_path" ]]; then
                cd "$worktree_path"
                echo ""
                echo "📂 Switched to $(pwd)"

                # Activate venv if it exists
                if [[ -f ".venv/bin/activate" ]]; then
                    source .venv/bin/activate
                    echo "🐍 Virtual environment activated"
                fi
            fi
        fi

        return $exit_code
    # Check if this is a select command
    elif [[ "$2" == "select" && -n "$3" ]]; then
        # Run the actual command with --shell-mode flag and eval the output
        local output
        output=$("$HOME/.local/bin/worktree" "$1" select "$3" --shell-mode 2>&1)
        local exit_code=$?

        if [[ $exit_code -eq 0 ]]; then
            # Execute the cd command(s) in the current shell
            eval "$output"
        else
            # If there was an error, just display it
            echo "$output"
            return $exit_code
        fi
    elif [[ "$2" == "rm" && -n "$3" ]]; then
        # For rm command, check if we're currently in the worktree being removed
        # Get the worktree path before removing
        local worktree_info
        worktree_info=$("$HOME/.local/bin/worktree" "$1" list 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -A 2 "✓ $3" | grep "Path:" | awk '{print $2}')

        # Run the rm command
        "$HOME/.local/bin/worktree" "$@"
        local exit_code=$?

        # If successful and we were in that directory, cd to parent and deactivate venv
        if [[ $exit_code -eq 0 && -n "$worktree_info" ]]; then
            if [[ "$PWD" == "$worktree_info"* ]]; then
                # Deactivate virtual environment if active
                if [[ -n "$VIRTUAL_ENV" ]]; then
                    deactivate 2>/dev/null
                fi

                cd "$(dirname "$worktree_info")" 2>/dev/null || cd "$HOME"
                echo ""
                echo "📂 Moved to $(pwd)"
            fi
        fi

        return $exit_code
    else
        # For all other commands, just pass through
        "$HOME/.local/bin/worktree" "$@"
    fi
}
