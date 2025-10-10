# Worktree Manager

A simple, generic CLI tool for managing git worktrees with optional environment setup.

## Features

- **Universal**: Works with any git repository
- **Organized**: Stores worktrees in a dedicated `<repo-name>-worktrees` directory
- **Optional Setup**: Configure automated environment setup per repository
- **Simple**: Just 4 commands to manage your workflow

## Installation

```bash
cd /Users/nikolas/worktree-manager
./install.sh
```

The script will install the `worktree` command to `~/.local/bin`.

If `~/.local/bin` isn't in your PATH, add this to your `~/.zshrc` or `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload: `source ~/.zshrc`

## Quick Start

```bash
# Navigate to your git repository
cd ~/my-project

# Create a new worktree
worktree new feature-xyz

# List all worktrees
worktree list

# Switch to a worktree (shows commands to run)
worktree select feature-xyz

# Remove a worktree
worktree rm feature-xyz
```

## How It Works

### Worktree Organization

Worktrees are stored in a separate directory alongside your main repository:

```
~/
  my-project/              # Your main repository
  my-project-worktrees/    # Worktrees directory
    ├── feature-auth/
    ├── bugfix-api/
    └── refactor-db/
```

This keeps your main repository clean and all worktrees organized in one place.

### Git Worktrees

Each worktree:
- Has its own working directory
- Has its own branch
- Shares git history with the main repo (no duplication!)
- Can have its own dependencies, virtual environment, etc.

Work on multiple branches simultaneously without stashing or switching!

## Commands

### `worktree new <name>`

Create a new worktree and branch.

```bash
# Create from origin/main (default)
worktree new feature-xyz

# Create from a different branch
worktree new hotfix --base origin/develop

# Skip automatic setup
worktree new quick-test --skip-setup
```

### `worktree list`

List all worktrees for the current repository.

```bash
worktree list
```

Example output:
```
Existing worktrees:
Location: /Users/you/my-project-worktrees

  ✓ feature-auth
    Branch: feature-auth
    Path: /Users/you/my-project-worktrees/feature-auth

  ✓ bugfix-api
    Branch: bugfix-api
    Path: /Users/you/my-project-worktrees/bugfix-api
```

### `worktree select <name>`

Show commands to switch to a worktree.

```bash
worktree select feature-xyz
```

Output:
```
Switching to worktree 'feature-xyz'
Path: /Users/you/my-project-worktrees/feature-xyz
Branch: feature-xyz

Run the following commands:
  cd /Users/you/my-project-worktrees/feature-xyz
  source .venv/bin/activate
```

### `worktree rm <name>`

Remove a worktree and delete its branch.

```bash
# With confirmation
worktree rm feature-xyz

# Skip confirmation
worktree rm feature-xyz --force
```

## Optional: Automated Setup

You can configure automated environment setup to run when creating new worktrees.

### Setup Configuration

Create a `.worktree-setup.json` file in either:
- Your repository root: `~/my-project/.worktree-setup.json`
- Your home directory: `~/.worktree-setup.json`

The tool will automatically run these setup steps when creating new worktrees.

### Configuration Format

```json
{
  "setup_steps": [
    {
      "name": "Display name",
      "type": "step_type",
      "...": "additional parameters"
    }
  ]
}
```

### Available Setup Steps

#### Create Python Virtual Environment

```json
{
  "name": "Python virtual environment",
  "type": "python_venv"
}
```

#### Install Python Dependencies

```json
{
  "name": "Python dependencies",
  "type": "pip_install",
  "requirements": [
    "requirements.txt",
    "requirements-dev.txt"
  ]
}
```

#### Install Package in Editable Mode

```json
{
  "name": "Install package",
  "type": "pip_install_editable",
  "path": "."
}
```

#### Install Specific Python Package

```json
{
  "name": "Install pre-commit",
  "type": "pip_install_package",
  "package": "pre-commit"
}
```

#### Install Playwright

```json
{
  "name": "Playwright browsers",
  "type": "playwright_install"
}
```

#### Setup Pre-commit Hooks

```json
{
  "name": "Pre-commit hooks",
  "type": "precommit_install",
  "path": "."
}
```

#### Install Node Dependencies

```json
{
  "name": "Node dependencies",
  "type": "npm_install",
  "path": "."
}
```

#### Run Custom Command

```json
{
  "name": "Run migrations",
  "type": "command",
  "command": "python manage.py migrate",
  "cwd": "."
}
```

## Example Configurations

### Python Project

`.worktree-setup.json`:
```json
{
  "setup_steps": [
    {
      "name": "Python virtual environment",
      "type": "python_venv"
    },
    {
      "name": "Install dependencies",
      "type": "pip_install",
      "requirements": ["requirements.txt"]
    }
  ]
}
```

### Node.js Project

`.worktree-setup.json`:
```json
{
  "setup_steps": [
    {
      "name": "Install dependencies",
      "type": "npm_install",
      "path": "."
    }
  ]
}
```

### Full-Stack Project

`.worktree-setup.json`:
```json
{
  "setup_steps": [
    {
      "name": "Python virtual environment",
      "type": "python_venv"
    },
    {
      "name": "Backend dependencies",
      "type": "pip_install",
      "requirements": ["backend/requirements.txt"]
    },
    {
      "name": "Frontend dependencies",
      "type": "npm_install",
      "path": "frontend"
    }
  ]
}
```

### Onyx Project

See `onyx-setup.example.json` for a complete Onyx setup configuration.

To use it:
```bash
cp onyx-setup.example.json ~/onyx/.worktree-setup.json
```

## Usage Patterns

### Feature Development

```bash
cd ~/my-project
worktree new feature-auth
cd ../my-project-worktrees/feature-auth

# Work on feature...
git add .
git commit -m "Add authentication"
git push origin feature-auth

# Back to main project
cd ~/my-project

# Clean up when done
worktree rm feature-auth
```

### Multiple Features in Parallel

```bash
cd ~/my-project

# Start two features
worktree new feature-a
worktree new feature-b

# Work on feature A
cd ../my-project-worktrees/feature-a
# ... make changes ...

# Switch to feature B
cd ../feature-b
# ... make changes ...

# List all active worktrees
cd ~/my-project
worktree list
```

### Hotfix While Working on Feature

```bash
# Currently working on a feature
cd ~/my-project-worktrees/my-feature

# Need to create a hotfix
cd ~/my-project
worktree new hotfix-123 --base origin/main

cd ../my-project-worktrees/hotfix-123
# Fix the bug, commit, push

# Clean up hotfix
cd ~/my-project
worktree rm hotfix-123

# Return to feature work
cd ../my-project-worktrees/my-feature
```

## Advanced Usage

### Different Repository

By default, the tool uses the current directory. To specify a different repository:

```bash
worktree --repo ~/other-project new feature-xyz
```

### Skip Setup

If you have a setup configuration but want to skip it for a specific worktree:

```bash
worktree new quick-test --skip-setup
```

## Troubleshooting

### Command not found

Ensure `~/.local/bin` is in your PATH:
```bash
echo $PATH | grep ".local/bin"
```

### Not a git repository

Make sure you're in a git repository:
```bash
cd ~/my-project
git status
```

### Setup fails

Setup steps will continue even if one fails. Check the error message and ensure required tools (python3, npm, etc.) are installed.

### Worktree already exists

Use `worktree list` to see existing worktrees, then either remove the old one or choose a different name.

## Requirements

- Python 3.7+
- Git 2.5+ (for worktree support)
- Additional tools as needed by your setup configuration (pip, npm, etc.)

## Why Use Worktrees?

**Instead of:**
```bash
git stash
git checkout main
git checkout -b new-feature
# work...
git checkout previous-branch
git stash pop
```

**Simply:**
```bash
worktree new new-feature
cd ../my-project-worktrees/new-feature
# work...
```

No more:
- Stashing changes
- Switching branches
- Rebuilding dependencies
- Losing context

Just create a new worktree and start coding!

## License

MIT
