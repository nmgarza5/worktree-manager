# Instance Isolation Strategy

This document explains how the worktree manager ensures complete isolation between multiple Onyx instances running simultaneously.

## Overview

When running multiple worktrees, each instance is completely isolated from others:
- Separate Docker containers with unique names
- Isolated data volumes (databases, caches, storage)
- Unique port assignments
- Independent processes (backend, frontend, workers)

This allows you to:
- Work on multiple features simultaneously
- Test different branches side-by-side
- Run integration tests without conflicts
- Maintain separate data states

## Port Isolation

### Automatic Port Assignment

Each worktree receives a unique port offset (increments of 10):
- First worktree: offset 0
- Second worktree: offset 10
- Third worktree: offset 20

### Port Calculation

External ports are calculated as: `base_port + port_offset`

**Example for two worktrees:**

**dev1** (offset 0):
```
PostgreSQL: 5432
Vespa:      19071
Redis:      6379
MinIO:      9000
Backend:    8080
Frontend:   3000
```

**dev2** (offset 10):
```
PostgreSQL: 5442
Vespa:      19081
Redis:      6389
MinIO:      9010
Backend:    8090
Frontend:   3010
```

### Port Conflict Detection

The system checks for port availability before assignment:
1. Checks existing worktree metadata
2. Verifies ports are actually available on the system
3. Increments offset if conflicts are detected
4. Retries up to 100 times to find available ports

## Container Isolation

### Unique Container Names

Each Docker container is named uniquely per worktree:
```
{service}-{worktree_name}
```

Examples:
- `relational_db-feature-auth`
- `index-feature-search`
- `cache-hotfix-123`

This ensures:
- No container name conflicts
- Easy identification of which instance a container belongs to
- Simple management with Docker commands

### Container Networks

Each worktree gets its own Docker Compose project name:
```yaml
name: onyx-{worktree_name}
```

This creates isolated networking between containers within the same worktree.

## Data Isolation

### Volume Renaming

Services configured with `isolate_data: true` get renamed volumes:

**Configuration:**
```yaml
docker_compose:
  services:
    relational_db:
      internal: 5432
      isolate_data: true
```

**Result:**
```yaml
volumes:
  db_volume-feature-auth:  # Instead of db_volume
  db_volume-feature-search:
```

### Why Data Isolation Matters

**Without isolation:**
- All worktrees share the same database
- Schema conflicts during migrations
- Test data affects all instances
- Cannot work on database changes independently

**With isolation:**
- Each worktree has its own database instance
- Independent schema evolution
- Separate test data
- Safe to experiment with migrations

### Isolated Services

By default, these services use isolated volumes:
- **PostgreSQL** (`relational_db`): Separate database for each worktree
- **Vespa** (`index`): Independent search indexes
- **MinIO** (`minio`): Isolated object storage

**Redis** (`cache`) shares data by default since cache state is typically transient.

## Process Isolation

### Local Services

Each worktree runs its own set of local processes:

1. **Backend API Server** (uvicorn)
   - Port: `8080 + offset`
   - Hot reload enabled
   - Separate virtual environment

2. **Model Server** (uvicorn)
   - Port: `9000 + offset`
   - Hot reload enabled
   - Independent from backend

3. **Frontend** (Next.js)
   - Port: `3000 + offset`
   - Hot reload enabled
   - Separate node_modules

4. **Celery Workers** (7 workers + beat)
   - All connected to the worktree's Redis
   - Process different queues
   - Isolated job execution

### Process Management

Processes are tracked via PID files:
```
.backend.pid
.model-server.pid
.frontend.pid
.celery-primary.pid
.celery-light.pid
... etc
```

## Environment Configuration

Each worktree gets a generated `.env.worktree` file with:
- Unique service ports
- Connection strings to the worktree's containers
- Environment variables for all services

Example:
```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5442  # Unique to this worktree

# Redis
REDIS_HOST=localhost
REDIS_PORT=6389

# Backend API
INTERNAL_URL=http://localhost:8090

# Frontend
PORT=3010
NEXT_PUBLIC_API_URL=http://localhost:8090
```

## Metadata Tracking

Worktree metadata is stored in `~/.worktree-metadata.json`:

```json
{
  "onyx": {
    "feature-auth": {
      "port_offset": 0,
      "ports": {
        "relational_db": 5432,
        "index": 19071,
        "cache": 6379,
        "minio": 9000
      },
      "created": "2025-01-15"
    },
    "feature-search": {
      "port_offset": 10,
      "ports": {
        "relational_db": 5442,
        "index": 19081,
        "cache": 6389,
        "minio": 9010
      },
      "created": "2025-01-15"
    }
  }
}
```

## Database Isolation Workflow

### Creating Isolated Instances

```bash
# Create first instance
worktree onyx new feature-auth
# → Creates isolated PostgreSQL volume

# Create second instance with copy of main database
worktree onyx new feature-search --copy-db-from-main
# → Creates new volume, dumps main DB, restores to new instance

# Create third instance from a dump
worktree onyx new hotfix-123 --restore-db main-20250115.sql
# → Creates new volume, restores from specified dump
```

### Managing Database State

```bash
# Save current database state
worktree onyx db dump feature-auth
# → Creates ~/.worktree-dumps/onyx/feature-auth-timestamp.sql

# Restore to a different worktree
worktree onyx db restore feature-search feature-auth-20250115.sql

# Connect directly to a worktree's database
worktree onyx db shell feature-auth
```

## Cleanup and Resource Management

### Removing Worktrees

When removing a worktree:
1. Stops all Docker containers
2. Removes Docker volumes (data is destroyed)
3. Deletes metadata
4. Frees port assignments for reuse
5. Kills all local processes

```bash
worktree onyx rm feature-auth
# All resources cleaned up automatically
```

### Persistent Dumps

Database dumps persist after worktree removal:
```bash
# List all saved dumps
worktree onyx db list-dumps

# Even after removing a worktree, dumps remain
worktree onyx rm feature-auth
worktree onyx db list-dumps  # Still shows feature-auth dumps
```

## Viewing All Instances

```bash
# See all worktree instances and their status
worktree onyx instances
```

Output:
```
Running worktree instances for 'onyx':

  ● feature-auth
    Port offset: 0
    Created: 2025-01-15
    Running services:
      - relational_db: http://localhost:5432
      - index: http://localhost:19071
      - cache: http://localhost:6379
      - minio: http://localhost:9000
    All configured ports:
      ✓ cache: 6379
      ✓ index: 19071
      ✓ minio: 9000
      ✓ relational_db: 5432

  ○ feature-search
    Port offset: 10
    Created: 2025-01-15
    (No services running)
    All configured ports:
        cache: 6389
        index: 19081
        minio: 9010
        relational_db: 5442
```

## Benefits of Complete Isolation

### Development Workflow
- Work on database migrations without affecting other branches
- Test different feature combinations independently
- Compare implementations side-by-side
- Run integration tests in parallel

### Safety
- No risk of data corruption between instances
- Mistakes in one worktree don't affect others
- Can experiment freely with schema changes

### Performance
- Each instance has dedicated resources
- No contention for database connections
- Independent scaling of services

## Troubleshooting

### Port Conflicts
If you get port conflicts even with automatic assignment:
1. Check for manually started services: `lsof -i :<port>`
2. Stop conflicting services
3. Remove and recreate the worktree

### Volume Conflicts
If volumes aren't isolated:
1. Verify `isolate_data: true` in setup config
2. Check override file has renamed volumes
3. Remove worktree and recreate

### Database Connection Issues
If services can't connect to the database:
1. Check `.env.worktree` has correct ports
2. Verify container is running: `docker ps`
3. Check logs: `docker logs relational_db-{worktree}`

## See Also

- [DB_MANAGEMENT.md](DB_MANAGEMENT.md) - Database dump and restore workflows
- [DOCKER.md](DOCKER.md) - Docker Compose integration details
- [README.md](README.md) - General worktree manager documentation
