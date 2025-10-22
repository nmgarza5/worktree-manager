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
- **Complete isolation**: Run multiple instances with separate databases, ports, and containers
- **Database management**: Dump, restore, and copy databases between instances
- **Simple**: Just configure once, then use powerful commands

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

## Running Multiple Isolated Instances

The worktree manager supports complete isolation for running multiple Onyx instances simultaneously. Each instance has:
- Separate Docker containers with unique ports
- Isolated PostgreSQL databases
- Independent Redis, Vespa, and MinIO instances
- Separate backend, frontend, and worker processes

### Quick Example

```bash
# Create instance with copy of main database
worktree onyx new feature-auth --copy-db-from-main

# Create another instance
worktree onyx new feature-search --copy-db-from-main

# View all instances
worktree onyx instances

# Each runs on different ports - no conflicts!
# feature-auth: PostgreSQL on 5432, backend on 8080, frontend on 3000
# feature-search: PostgreSQL on 5442, backend on 8090, frontend on 3010
```

### Database Management

```bash
# Save database state
worktree onyx db dump feature-auth

# Restore to another worktree
worktree onyx db restore feature-search feature-auth-20250115.sql

# List all saved dumps
worktree onyx db list-dumps

# Connect to database
worktree onyx db shell feature-auth
```

**See [ISOLATION.md](ISOLATION.md) for complete isolation details and [DB_MANAGEMENT.md](DB_MANAGEMENT.md) for database workflows.**

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
worktree <repo> new <name>                           # From origin/main
worktree <repo> new <name> --base develop            # From different branch
worktree <repo> new <name> --skip-setup              # Skip automated setup
worktree <repo> new <name> --copy-db-from-main       # Copy database from main
worktree <repo> new <name> --restore-db <dump-file>  # Restore from dump
```

**Examples:**
```bash
worktree onyx new feature-auth
worktree onyx new hotfix-123 --base origin/production
worktree myapp new quick-test --skip-setup

# Create with database copy
worktree onyx new feature-auth --copy-db-from-main

# Create with specific database state
worktree onyx new debug-issue --restore-db main-20250115.sql
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

### Database Management

Manage PostgreSQL databases across worktree instances.

#### Create Database Dump

```bash
worktree <repo> db dump                        # Dump main installation
worktree <repo> db dump <worktree-name>        # Dump specific worktree
worktree <repo> db dump <worktree-name> -o file.sql  # Custom output
```

**Examples:**
```bash
worktree onyx db dump                          # Dump main ~/onyx database
worktree onyx db dump feature-auth             # Dump feature-auth worktree
worktree onyx db dump feature-auth -o backup.sql
```

#### Restore Database

```bash
worktree <repo> db restore <worktree> <dump-file>
```

**Examples:**
```bash
worktree onyx db restore feature-auth main-20250115.sql
worktree onyx db restore debug-issue ~/backups/production.sql
```

#### List Database Dumps

```bash
worktree <repo> db list-dumps
```

Shows all saved dumps with size and modification time.

#### Connect to Database

```bash
worktree <repo> db shell                       # Connect to main installation
worktree <repo> db shell <worktree-name>       # Connect to worktree
```

**Examples:**
```bash
worktree onyx db shell                         # psql to main database
worktree onyx db shell feature-auth            # psql to feature-auth database
```

**See [DB_MANAGEMENT.md](DB_MANAGEMENT.md) for complete database workflows.**

### View All Instances

```bash
worktree <repo> instances
```

Shows all worktree instances with:
- Port offsets
- Running services
- Service ports
- Creation dates

**Example output:**
```
Running worktree instances for 'onyx':

  ● feature-auth
    Port offset: 0
    Created: 2025-01-15
    Running services:
      - relational_db: http://localhost:5432
      - cache: http://localhost:6379
    All configured ports:
      ✓ relational_db: 5432
      ✓ cache: 6379
      ✓ minio: 9000

  ○ feature-search
    Port offset: 10
    Created: 2025-01-15
    (No services running)
```

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

Create a setup configuration file in your repository root (YAML format recommended):

```bash
# For Onyx open-source project
# Full configuration with Docker Compose and all setup steps
cp onyx-setup.yaml ~/onyx/onyx-setup.yaml

# Or create your own
cat > ~/myproject/.worktree-setup.yaml << 'EOF'
setup_steps:
  - name: Python virtual environment
    command: python3 -m venv .venv

  - name: Install dependencies
    command: .venv/bin/pip install -r requirements.txt

  - name: Install package in editable mode
    command: .venv/bin/pip install -e .
EOF
```

**Note:** The tool now uses arbitrary shell commands instead of predefined setup types. This gives you full flexibility to run any command you need during setup. If a command fails, full error output is surfaced so you can debug your setup script.

### Real-World Example: Onyx

This tool was built for the [Onyx](https://github.com/danswer-ai/danswer) open-source project. See [`onyx-setup.yaml`](onyx-setup.yaml) for a complete configuration including:
- Docker Compose service management (PostgreSQL, Redis, Vespa, Minio)
- Python virtual environment setup
- Backend and frontend dependency installation
- Pre-commit hooks
- Playwright browsers

The configuration enables running multiple Onyx worktrees simultaneously with isolated services on different ports.

**Important:** Add these lines to your repository's `.gitignore`:
```gitignore
# worktree manager
*-setup.yaml
*-setup.yml
.worktree-setup.yaml
.worktree-setup.yml
.worktree-setup.json
deployment/docker_compose/docker-compose.worktree-*.yml
```

This prevents committing the setup configuration and generated Docker Compose override files.

### Setup Step Format

Each setup step is defined with:
- `name`: A descriptive name for the step (shown in progress output)
- `command`: The shell command to execute
- `cwd` (optional): Working directory relative to worktree root

**Examples:**

```yaml
setup_steps:
  # Basic command
  - name: Create virtual environment
    command: python3 -m venv .venv

  # Command with working directory
  - name: Install pre-commit hooks
    command: ../.venv/bin/pre-commit install
    cwd: backend

  # Multiple commands using shell operators
  - name: Install and setup
    command: npm install && npm run build
    cwd: web
```

**Error Handling:**

If a setup command fails, the tool will display:
- The command that failed
- The exit code
- Full stdout and stderr output
- A reminder that this is a setup configuration issue

This helps you debug your setup scripts quickly.

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

### Show Verbose Setup Output

See detailed output from all setup commands (useful for debugging):

```bash
worktree onyx new feature-xyz --verbose
# or
worktree onyx new feature-xyz -v
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

Setup steps continue even if one fails. Check the error output which will show:
- The exact command that failed
- Exit code
- Full stdout and stderr output

Ensure all required tools are installed and your commands are correct in your setup configuration file.

## Development

### Running Tests

The project includes comprehensive unit and integration tests. Run them using:

```bash
worktree run-tests                    # Run all tests
worktree run-tests -k test_name       # Run specific tests
worktree run-tests -v                 # Verbose output
```

The test runner automatically:
- Creates an isolated test virtual environment (`.test-venv/`)
- Installs test dependencies (pytest, pyyaml, etc.)
- Runs all tests from the `tests/` directory

**Test Coverage:**
- **Unit tests**: `SetupExecutor.execute_step()` with various scenarios
- **Config loading**: YAML/JSON parsing, priority, error handling
- **Integration tests**: Complete setup workflows, file operations, shell features

### End-to-End Integration Test

Verify your installation works correctly by running the integration test against your actual repository:

```bash
worktree test-e2e <repo-alias>
```

For example:
```bash
worktree test-e2e onyx
```

This test automatically:
1. **Verifies** your repository configuration
2. **Creates** a temporary test setup configuration with command-based steps
3. **Creates** a test worktree (`e2e-test-wt`) from your main branch
4. **Runs** the test setup steps:
   - Creates test directories
   - Creates Python virtual environment
   - Creates test files and markers
   - Tests `cwd` (working directory) support
   - Tests multiple shell commands
5. **Verifies** all setup artifacts were created correctly
6. **Tests** basic worktree operations (file creation, git staging)
7. **Lists** all worktrees
8. **Deletes** the test worktree and cleans up ALL artifacts
9. **Verifies** complete cleanup (worktree, branch, and test files all removed)

**Expected output:**
```
================================
Worktree Manager E2E Test
Repository: onyx
================================

==> Step 1: Verifying repository configuration
✓ Repository configured: /Users/you/onyx
✓ Setup configuration found: onyx-setup.yaml

==> Step 2: Checking for existing test worktree
✓ Ready to create test worktree

==> Step 3: Creating test worktree
✓ Worktree created: /Users/you/onyx-worktrees/e2e-test-wt

==> Step 4: Verifying worktree
✓ Git branch created: e2e-test-wt
✓ Git working directory initialized

Checking setup execution:
✓ Virtual environment created
✓ Setup created 5 new items

==> Step 5: Listing all worktrees
[worktree list output]

==> Step 6: Testing worktree operations
✓ File creation works
✓ Git staging works

==> Step 7: Deleting test worktree
✓ Worktree deleted successfully
✓ Git branch deleted successfully

================================
Test Results
================================

✓ ALL TESTS PASSED
```

Run this test after installation or after making changes to verify everything works correctly with your actual repository.

## Requirements

- Python 3.7+
- Git 2.5+ (for worktree support)
- PyYAML (optional, for YAML config files): `pip install pyyaml`
- Additional tools as needed by your setup configuration

**Note:** JSON config files are still supported for backward compatibility, but YAML is recommended for better readability.

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
