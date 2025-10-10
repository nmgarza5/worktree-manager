# Worktree Manager

A simple CLI tool for managing git worktrees across multiple repositories **from anywhere**.

Built for the [Onyx](https://github.com/danswer-ai/danswer) open-source project, but works with any Git repository.

## Why Use This?

Work on multiple branches simultaneously without:
- Stashing changes
- Switching branches
- Rebuilding dependencies
- Losing context

Just create a new worktree and start coding!

## Features

- **Manage from anywhere**: `worktree onyx new feature-xyz` works from any directory
- **Multiple repos**: Configure aliases for all your repositories
- **Organized**: Worktrees stored in `<repo-name>-worktrees` directories
- **Optional setup**: Automated environment setup per repository
- **Simple**: Just configure once, then use 4 commands

## Installation

```bash
./install.sh
```

Then add to your shell configuration:

**For Zsh (`~/.zshrc`):**
```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.worktree-wrapper.sh
```

**For Bash (`~/.bashrc` or `~/.bash_profile`):**
```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.worktree-wrapper.sh
```

Reload your shell:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

**Note:** The shell wrapper enables the `select` command to automatically change directories.

## Quick Start

### 1. Configure Your Repositories

```bash
# Add repository aliases
worktree repo add onyx ~/onyx
worktree repo add myapp ~/projects/myapp

# List configured repos
worktree repo list
```

### 2. Manage Worktrees from Anywhere

```bash
# From ANY directory:
worktree onyx new feature-xyz        # Create worktree
worktree onyx list                   # List worktrees
worktree onyx select feature-xyz     # Get switch commands
worktree onyx rm feature-xyz         # Remove worktree

# Different repo, same commands:
worktree myapp new hotfix-123
worktree myapp list
worktree myapp rm hotfix-123
```

## Commands

### Repository Management

```bash
# Add a repository alias
worktree repo add <alias> <path>

# List all configured repositories
worktree repo list

# Remove a repository alias
worktree repo rm <alias>
```

**Example:**
```bash
worktree repo add onyx ~/onyx
worktree repo add dotfiles ~/.dotfiles
worktree repo list
```

### Worktree Commands

All worktree commands follow this pattern: `worktree <repo-alias> <command>`

#### Create Worktree

```bash
worktree <repo> new <name>                    # From origin/main
worktree <repo> new <name> --base develop     # From different branch
worktree <repo> new <name> --skip-setup       # Skip automated setup
```

**Examples:**
```bash
worktree onyx new feature-auth
worktree onyx new hotfix-123 --base origin/production
worktree myapp new quick-test --skip-setup
```

#### List Worktrees

```bash
worktree <repo> list
```

**Output:**
```
Existing worktrees:
Location: /Users/you/onyx-worktrees

  ✓ feature-auth
    Branch: feature-auth
    Path: /Users/you/onyx-worktrees/feature-auth

  ✓ hotfix-123
    Branch: hotfix-123
    Path: /Users/you/onyx-worktrees/hotfix-123
```

#### Switch to Worktree

```bash
worktree <repo> select <name>
```

**Automatically changes to the worktree directory!** (requires shell wrapper setup)

```bash
worktree onyx select feature-auth
# You are now in /Users/you/onyx-worktrees/feature-auth
# Virtual environment activated automatically if present
```

#### Remove Worktree

```bash
worktree <repo> rm <name>            # With confirmation
worktree <repo> rm <name> --force    # Skip confirmation
```

### Docker Compose Services (Optional)

If your repository uses Docker Compose, the worktree manager can automatically manage services with unique ports for each worktree. **All service commands must be run from within the worktree directory.**

#### Typical Workflow

```bash
# 1. Switch to worktree
worktree onyx select dev1

# 2. Start services
worktree onyx services start

# 3. View logs
worktree onyx services logs api_server

# 4. Stop services
worktree onyx services stop
```

#### Start Services

```bash
worktree <repo> services start                     # Start all services
worktree <repo> services start --build             # Rebuild and start
worktree <repo> services start --svcs db cache     # Start specific services
```

#### Stop Services

```bash
worktree <repo> services stop                      # Stop all services
worktree <repo> services stop --svcs api_server    # Stop specific services
worktree <repo> services stop --volumes            # Stop and remove data
```

#### Restart Services

```bash
worktree <repo> services restart                   # Restart all services
worktree <repo> services restart --svcs api_server # Restart specific services
```

#### Check Status

```bash
worktree <repo> services status                    # Show running services
```

#### View Logs

```bash
worktree <repo> services logs                      # All service logs
worktree <repo> services logs api_server           # Specific service
worktree <repo> services logs api_server -f        # Follow logs
worktree <repo> services logs --tail 100           # Last 100 lines
```

**See [DOCKER.md](DOCKER.md) for complete Docker Compose documentation.**

## How It Works

### Directory Structure

```
~/
  onyx/                # Main repository
  onyx-worktrees/      # All onyx worktrees
    ├── feature-auth/
    ├── hotfix-123/
    └── refactor-db/

  myapp/               # Another repository
  myapp-worktrees/     # All myapp worktrees
    ├── feature-xyz/
    └── bugfix-456/
```

### Repository Configuration

Repository aliases are stored in `~/.worktree-repos.json`:

```json
{
  "onyx": "/Users/you/onyx",
  "myapp": "/Users/you/projects/myapp"
}
```

You manage this with `worktree repo` commands.

## Optional: Automated Setup

Configure automated environment setup to run when creating new worktrees.

### Setup Configuration

Create `.worktree-setup.json` in your repository root:

```bash
# For Onyx open-source project
# Full configuration with Docker Compose and all setup steps
cp onyx-setup.json ~/onyx/.worktree-setup.json

# Or use the simplified example without Docker
cp onyx-setup.example.json ~/onyx/.worktree-setup.json

# Or create your own
cat > ~/myproject/.worktree-setup.json << 'EOF'
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
EOF
```

### Real-World Example: Onyx

This tool was built for the [Onyx](https://github.com/danswer-ai/danswer) open-source project. See [`onyx-setup.json`](onyx-setup.json) for a complete configuration including:
- Docker Compose service management (PostgreSQL, Redis, Vespa, Minio)
- Python virtual environment setup
- Backend and frontend dependency installation
- Pre-commit hooks
- Playwright browsers

The configuration enables running multiple Onyx worktrees simultaneously with isolated services on different ports.

### Available Setup Steps

**Python:**
- `python_venv` - Create virtual environment
- `pip_install` - Install from requirements files
- `pip_install_editable` - Install package in editable mode
- `pip_install_package` - Install specific package
- `playwright_install` - Install Playwright browsers
- `precommit_install` - Setup pre-commit hooks

**Node.js:**
- `npm_install` - Install Node dependencies

**Custom:**
- `command` - Run custom shell command

See `onyx-setup.example.json` for a complete configuration example.

## Workflow Examples

### Feature Development

```bash
# From anywhere
worktree onyx new feature-auth

# Switch to it
cd ~/onyx-worktrees/feature-auth
source .venv/bin/activate

# Work on feature...
git add .
git commit -m "Add authentication"
git push origin feature-auth

# Clean up when done
worktree onyx rm feature-auth
```

### Multiple Features

```bash
# Start multiple features (from anywhere!)
worktree onyx new feature-a
worktree onyx new feature-b

# Switch between them
cd ~/onyx-worktrees/feature-a
# work...

cd ~/onyx-worktrees/feature-b
# work...

# Check all active worktrees
worktree onyx list
```

### Emergency Hotfix

```bash
# Currently working in feature-a
cd ~/onyx-worktrees/feature-a

# Emergency hotfix needed! Create from production
worktree onyx new hotfix-123 --base origin/production

# Fix the bug
cd ~/onyx-worktrees/hotfix-123
# fix, commit, push...

# Clean up and return to feature
worktree onyx rm hotfix-123
cd ~/onyx-worktrees/feature-a
```

### Multiple Repositories

```bash
# Configure multiple repos
worktree repo add frontend ~/work/frontend
worktree repo add backend ~/work/backend
worktree repo add docs ~/work/docs

# Work across all of them simultaneously
worktree frontend new feature-xyz
worktree backend new feature-xyz
worktree docs new feature-xyz

# Check status across all repos
worktree frontend list
worktree backend list
worktree docs list
```

## Advanced Usage

### Different Base Branch

```bash
worktree onyx new my-branch --base origin/develop
worktree onyx new hotfix --base origin/v1.2.3
```

### Skip Automated Setup

```bash
worktree onyx new quick-test --skip-setup
```

### Remove Without Confirmation

```bash
worktree onyx rm old-feature --force
```

## Troubleshooting

### Command not found

Ensure `~/.local/bin` is in your PATH:
```bash
echo $PATH | grep ".local/bin"
```

### Repository not found

List configured repositories:
```bash
worktree repo list
```

Add missing repository:
```bash
worktree repo add myrepo ~/path/to/repo
```

### Setup fails

Setup steps continue even if one fails. Check the error and ensure required tools are installed:
- Python 3.7+
- Node.js (if using npm steps)
- Additional tools as specified in your setup config

## Requirements

- Python 3.7+
- Git 2.5+ (for worktree support)
- Additional tools as needed by your setup configuration

## Why Worktrees?

**Traditional workflow:**
```bash
# Working on feature-a
git add .
git stash
git checkout main
git checkout -b hotfix
# fix bug
git checkout feature-a
git stash pop
# conflicts? dependencies changed?
```

**With worktree manager:**
```bash
# Working on feature-a
worktree onyx new hotfix
cd ~/onyx-worktrees/hotfix
# fix bug, commit, done
cd ~/onyx-worktrees/feature-a
# continue exactly where you left off
```

Benefits:
- No stashing
- No branch switching
- Each worktree has its own dependencies
- Work on multiple features simultaneously
- No context loss

## License

MIT
