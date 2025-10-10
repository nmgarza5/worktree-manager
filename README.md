# Worktree Manager

A comprehensive CLI tool for managing git worktrees with automatic environment setup for the Onyx project.

## Features

- Create new worktrees with a single command
- Automatic Python virtual environment setup
- Automatic installation of all Python dependencies (default, dev, ee, model_server)
- Automatic Playwright installation
- Pre-commit hooks setup
- Node.js dependencies installation
- Easy switching between worktrees
- Clean removal of worktrees with branch cleanup
- List all active worktrees

## Installation

```bash
cd /Users/nikolas/worktree-manager
./install.sh
```

The script will install the `worktree` command to `~/.local/bin`. Make sure this directory is in your PATH.

If not in PATH, add this to your `~/.zshrc` or `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload your shell:

```bash
source ~/.zshrc  # or source ~/.bashrc
```

## Usage

### Create a New Worktree

Create a new worktree with full environment setup:

```bash
worktree new feature-name
```

This will:
1. Create a new git worktree in `~/feature-name`
2. Create a new branch `feature-name` based on `origin/main`
3. Set up a Python virtual environment
4. Install all Python dependencies:
   - `backend/requirements/default.txt`
   - `backend/requirements/dev.txt`
   - `backend/requirements/ee.txt`
   - `backend/requirements/model_server.txt`
5. Install the package in editable mode
6. Install Playwright
7. Set up pre-commit hooks
8. Install Node.js dependencies

You can specify a different base branch:

```bash
worktree new feature-name --base origin/develop
```

### List Worktrees

View all existing worktrees:

```bash
worktree list
```

Example output:
```
Existing worktrees:

  ✓ feature-auth
    Branch: feature-auth
    Path: /Users/nikolas/feature-auth

  ✓ bugfix-api
    Branch: bugfix-api
    Path: /Users/nikolas/bugfix-api
```

### Switch to a Worktree

Get instructions for switching to a worktree:

```bash
worktree select feature-name
```

This will display the commands needed to switch:
```
Switching to worktree 'feature-name'
Path: /Users/nikolas/feature-name
Branch: feature-name

Run the following commands:
  cd /Users/nikolas/feature-name
  source .venv/bin/activate
```

### Remove a Worktree

Remove a worktree and its associated branch:

```bash
worktree rm feature-name
```

You'll be prompted for confirmation. To skip confirmation:

```bash
worktree rm feature-name --force
```

This will:
1. Remove the git worktree
2. Delete the local branch
3. Clean up the directory

## Workflow Example

```bash
# Create a new feature worktree
worktree new my-new-feature

# Switch to it
cd ~/my-new-feature
source .venv/bin/activate

# Start the development environment
cd deployment/docker_compose
docker compose up -d index relational_db cache minio

cd ../../backend
alembic upgrade head
python ./scripts/dev_run_background_jobs.py &
AUTH_TYPE=disabled uvicorn onyx.main:app --reload --port 8080 &

cd ../web
npm run dev

# ... do your work ...

# When done, switch back to main repo
cd ~/onyx

# Remove the worktree
worktree rm my-new-feature
```

## Requirements

- Python 3.11+
- Node.js v22.20.0 (use nvm to manage Node versions)
- Git 2.5+ (for worktree support)
- Docker (for running Onyx services)

## How It Works

The tool creates git worktrees in the same parent directory as your main Onyx repository. For example:

```
~/
  onyx/              # Main repository
  feature-auth/      # Worktree 1
  bugfix-api/        # Worktree 2
  refactor-db/       # Worktree 3
```

Each worktree:
- Has its own working directory
- Has its own branch
- Shares the git history with the main repo
- Has its own virtual environment
- Has its own node_modules

This allows you to work on multiple features simultaneously without switching branches or stashing changes.

## Troubleshooting

### Command not found

Make sure `~/.local/bin` is in your PATH:

```bash
echo $PATH | grep ".local/bin"
```

If not, add it to your shell config and reload.

### Python version issues

Ensure you're using Python 3.11:

```bash
python3 --version
```

### Node version issues

Use nvm to install and use Node 22:

```bash
nvm install 22 && nvm use 22
node -v
```

### Worktree already exists

If you get an error that a worktree already exists, list all worktrees:

```bash
worktree list
```

Remove the conflicting worktree or choose a different name.

## Advanced Usage

### Custom Repository Location

By default, the tool assumes your main repository is at `~/onyx`. If it's elsewhere, you can modify the `WorktreeManager` initialization in `worktree.py`:

```python
manager = WorktreeManager("/path/to/your/onyx")
```

### Skip Environment Setup

If you want to manually set up the environment, you can modify the `create_worktree` method to skip certain steps.

## Contributing

Feel free to submit issues or pull requests to improve this tool!

## License

MIT
