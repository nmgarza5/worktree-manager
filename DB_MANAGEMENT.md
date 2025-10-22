# Database Management

Complete guide to managing PostgreSQL databases across multiple Onyx worktree instances.

## Overview

The worktree manager provides comprehensive database management features:
- Create dumps from any instance
- Restore dumps to any worktree
- Copy databases between instances
- Direct PostgreSQL shell access
- Automatic dump management

## Quick Start

```bash
# Dump your main Onyx database
worktree onyx db dump
# → Saves to ~/.worktree-dumps/onyx/main-{timestamp}.sql

# Create new worktree with copy of main database
worktree onyx new feature-branch --copy-db-from-main

# List all dumps
worktree onyx db list-dumps

# Restore a dump to a worktree
worktree onyx db restore feature-branch main-20250115-143022.sql

# Connect to a worktree's database
worktree onyx db shell feature-branch
```

## Database Dump Commands

### Create a Dump

#### From Main Installation

```bash
# Dump from your main ~/onyx installation
worktree onyx db dump
```

This:
1. Finds the main postgres container (without worktree suffix)
2. Waits for PostgreSQL to be ready
3. Creates pg_dump
4. Saves to `~/.worktree-dumps/onyx/main-{timestamp}.sql`

**Requirements:**
- Main Onyx instance must be running
- PostgreSQL container must be accessible

#### From a Worktree

```bash
# Dump from a specific worktree
worktree onyx db dump feature-auth
```

This:
1. Finds the `relational_db-feature-auth` container
2. Waits for PostgreSQL to be ready
3. Creates pg_dump
4. Saves to `~/.worktree-dumps/onyx/feature-auth-{timestamp}.sql`

**Requirements:**
- Worktree's Docker services must be running
- Use `worktree onyx services start` if not running

#### Custom Output Location

```bash
# Specify custom output file
worktree onyx db dump feature-auth -o /path/to/backup.sql
worktree onyx db dump -o ~/backups/onyx-production.sql
```

### List Available Dumps

```bash
worktree onyx db list-dumps
```

Output:
```
Available database dumps:
Location: /Users/you/.worktree-dumps/onyx

  feature-auth-20250115-143022.sql
    Size: 45.3 MB
    Modified: 2025-01-15 14:30:22

  main-20250115-120000.sql
    Size: 120.7 MB
    Modified: 2025-01-15 12:00:00

  feature-search-20250114-093045.sql
    Size: 38.2 MB
    Modified: 2025-01-14 09:30:45
```

Dumps are:
- Sorted by modification time (newest first)
- Stored in `~/.worktree-dumps/{repo-alias}/`
- Persisted even after worktree removal
- Named with worktree name and timestamp

## Database Restore Commands

### Restore to a Worktree

```bash
# Restore from a dump file
worktree onyx db restore feature-auth main-20250115.sql
```

This:
1. Verifies the dump file exists
2. Checks the PostgreSQL container is running
3. Terminates existing connections
4. Drops and recreates the database
5. Restores the dump
6. Verifies restoration success

**Important:**
- This is **destructive** - all data in the target database is lost
- The worktree's services must be running first
- You can use just the filename if the dump is in `~/.worktree-dumps/onyx/`

### Restore from Different Locations

```bash
# From dumps directory (just filename)
worktree onyx db restore feature-auth main-20250115.sql

# From absolute path
worktree onyx db restore feature-auth /path/to/dump.sql

# From home directory
worktree onyx db restore feature-auth ~/backups/production.sql
```

The tool automatically:
- Checks if the file exists
- Looks in `~/.worktree-dumps/{repo}/` if only a filename is provided
- Expands `~` for home directory
- Converts relative paths to absolute

## Worktree Creation with Database

### Copy from Main Installation

```bash
# Create worktree and copy main database
worktree onyx new feature-auth --copy-db-from-main
```

This workflow:
1. Creates the git worktree
2. Runs setup steps (installs dependencies, etc.)
3. Generates Docker Compose override with unique ports
4. **Starts PostgreSQL container**
5. **Dumps main installation database**
6. **Restores dump to new worktree**
7. Shows success message with ports

**Perfect for:**
- Working with production-like data
- Testing migrations against real data
- Debugging issues that require actual data

### Restore from Specific Dump

```bash
# Create worktree and restore from dump
worktree onyx new feature-auth --restore-db main-20250115.sql
```

This workflow:
1. Creates the git worktree
2. Runs setup steps
3. Generates Docker Compose override
4. **Starts PostgreSQL container**
5. **Restores specified dump**
6. Shows success message

**Perfect for:**
- Reproducing specific database states
- Testing against known data sets
- Sharing data snapshots with team

### Combine with Other Flags

```bash
# Create from different branch and restore database
worktree onyx new hotfix --base origin/production --restore-db prod-dump.sql

# Create with verbose output and database copy
worktree onyx new feature-xyz --copy-db-from-main --verbose
```

## Direct Database Access

### Connect to Database Shell

```bash
# Connect to a worktree's PostgreSQL
worktree onyx db shell feature-auth
```

This opens an interactive `psql` session connected to the worktree's database.

**You can:**
- Run SQL queries
- Inspect schema
- Check data
- Run manual migrations
- Debug database issues

**Example session:**
```sql
postgres=# \dt
-- List all tables

postgres=# SELECT COUNT(*) FROM users;
-- Query data

postgres=# \q
-- Exit
```

### Connect to Main Installation

```bash
# Connect to main installation's database
worktree onyx db shell
```

Omitting the worktree name connects to your main `~/onyx` database.

### Using psql Directly

You can also connect manually:
```bash
# Find the port for your worktree
worktree onyx instances

# Connect using psql
psql -h localhost -p 5442 -U postgres postgres
```

## Complete Workflows

### Workflow 1: Test Migration on Copy

```bash
# 1. Create worktree with copy of main database
worktree onyx new test-migration --copy-db-from-main

# 2. Switch to worktree
cd ~/onyx-worktrees/test-migration

# 3. Create migration
alembic revision -m "add new column"

# 4. Edit migration file
# ... make your changes ...

# 5. Test migration
alembic upgrade head

# 6. Check it worked
worktree onyx db shell test-migration
# Run queries to verify

# 7. If successful, apply to main
cd ~/onyx
alembic upgrade head

# 8. Clean up test worktree
worktree onyx rm test-migration
```

### Workflow 2: Share Database State

```bash
# Developer A: Save database state
worktree onyx db dump feature-auth
# → Creates feature-auth-20250115.sql

# Developer A: Share the dump
# (copy file to shared location or send to teammate)

# Developer B: Create worktree with that state
worktree onyx new debug-issue --restore-db feature-auth-20250115.sql

# Developer B: Now has exact same database state
worktree onyx db shell debug-issue
```

### Workflow 3: Snapshot Before Dangerous Operations

```bash
# 1. Save current state
worktree onyx db dump feature-auth
# → Backup created

# 2. Try dangerous operation
worktree onyx db shell feature-auth
postgres=# DELETE FROM large_table WHERE ...;

# 3. Oops, that was wrong! Restore backup
worktree onyx db restore feature-auth feature-auth-20250115-140022.sql

# 4. Back to original state
```

### Workflow 4: Multiple Parallel Tests

```bash
# Create base worktree with test data
worktree onyx new test-base --restore-db test-dataset.sql

# Dump it
worktree onyx db dump test-base

# Create multiple test instances from the same base
worktree onyx new test-1 --restore-db test-base-20250115.sql
worktree onyx new test-2 --restore-db test-base-20250115.sql
worktree onyx new test-3 --restore-db test-base-20250115.sql

# Run different tests in parallel, all starting from same state
```

## Dump File Management

### Storage Location

All dumps are stored in:
```
~/.worktree-dumps/
  └── {repo-alias}/
      ├── main-{timestamp}.sql
      ├── {worktree-name}-{timestamp}.sql
      └── ...
```

For Onyx:
```
~/.worktree-dumps/onyx/
```

### Naming Convention

Dumps are automatically named:
```
{source}-{timestamp}.sql
```

Where:
- `source`: `main` or worktree name
- `timestamp`: `YYYYMMDD-HHMMSS`

Examples:
- `main-20250115-143022.sql`
- `feature-auth-20250115-120000.sql`
- `hotfix-123-20250114-093045.sql`

### Manual Cleanup

Dumps persist after worktree removal. Clean up manually:

```bash
# List dumps
worktree onyx db list-dumps

# Remove old dumps
rm ~/.worktree-dumps/onyx/old-dump.sql

# Or remove all dumps
rm -rf ~/.worktree-dumps/onyx/
```

### Disk Space Considerations

Database dumps can be large (50-500+ MB). Monitor disk usage:

```bash
# Check dumps directory size
du -sh ~/.worktree-dumps/onyx/

# List dumps by size
ls -lhS ~/.worktree-dumps/onyx/
```

## Troubleshooting

### Container Not Found

**Error:**
```
Error: Container 'relational_db-feature-auth' not found
```

**Solution:**
Start the services first:
```bash
worktree onyx services start
# Or just postgres:
worktree onyx services start --svcs relational_db
```

### Dump File Not Found

**Error:**
```
Error: Dump file not found: my-dump.sql
```

**Solution:**
Use full path or check dumps directory:
```bash
worktree onyx db list-dumps
worktree onyx db restore feature-auth /full/path/to/dump.sql
```

### PostgreSQL Not Ready

**Error:**
```
Error: Postgres in container 'relational_db-feature-auth' did not become ready
```

**Solution:**
The container might still be starting. Wait and retry:
```bash
# Check container status
docker ps -a | grep relational_db-feature-auth

# Check logs
docker logs relational_db-feature-auth

# Restart if needed
worktree onyx services restart --svcs relational_db
```

### Restore Failed

**Error:**
```
Error: Failed to restore dump
```

**Possible causes:**
1. Dump from incompatible PostgreSQL version
2. Dump file corrupted
3. Insufficient disk space
4. Connection issues

**Solution:**
```bash
# Check PostgreSQL version compatibility
docker exec relational_db-feature-auth psql -U postgres -c "SELECT version();"

# Check disk space
df -h

# Try restoring manually to see full error
docker exec -i relational_db-feature-auth psql -U postgres postgres < dump.sql
```

### Permission Denied

**Error:**
```
Error: Permission denied accessing dump file
```

**Solution:**
```bash
# Check file permissions
ls -l ~/.worktree-dumps/onyx/

# Fix if needed
chmod 644 ~/.worktree-dumps/onyx/*.sql
```

## Advanced Usage

### Scripted Database Operations

```bash
#!/bin/bash
# Save database, make changes, restore if failed

WORKTREE="feature-auth"
BACKUP=$(worktree onyx db dump $WORKTREE | grep "Path:" | awk '{print $2}')

# Run risky operation
if ! run_risky_migration.sh; then
    echo "Migration failed! Restoring backup..."
    worktree onyx db restore $WORKTREE $BACKUP
    exit 1
fi

echo "Migration successful!"
```

### Automated Backups

```bash
#!/bin/bash
# Backup all worktrees daily

for worktree in $(worktree onyx list | grep "✓" | awk '{print $2}'); do
    echo "Backing up $worktree..."
    worktree onyx db dump $worktree
done
```

### Database Comparison

```bash
# Dump both databases
worktree onyx db dump feature-a
worktree onyx db dump feature-b

# Use tools to compare schemas
pg_dump -s postgres://localhost:5432/postgres > feature-a-schema.sql
pg_dump -s postgres://localhost:5442/postgres > feature-b-schema.sql
diff feature-a-schema.sql feature-b-schema.sql
```

## Best Practices

### 1. Regular Backups

Create dumps before:
- Running migrations
- Testing destructive operations
- Major refactoring
- Pulling updates from main

### 2. Meaningful Names

Use custom output names for important dumps:
```bash
worktree onyx db dump feature-auth -o auth-before-migration.sql
```

### 3. Clean Up Old Dumps

Remove dumps you no longer need:
```bash
# Keep only recent dumps
find ~/.worktree-dumps/onyx/ -name "*.sql" -mtime +30 -delete
```

### 4. Share Carefully

Dumps may contain:
- User data
- Passwords (hashed)
- API keys
- Sensitive information

Only share with authorized team members.

### 5. Test Restores

Periodically verify dumps can be restored:
```bash
# Create test worktree
worktree onyx new test-restore --restore-db important-dump.sql

# Verify data
worktree onyx db shell test-restore

# Clean up
worktree onyx rm test-restore --force
```

## See Also

- [ISOLATION.md](ISOLATION.md) - How instances are isolated
- [DOCKER.md](DOCKER.md) - Docker Compose integration
- [README.md](README.md) - General worktree manager documentation
