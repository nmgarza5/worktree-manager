# Docker Compose Integration

The worktree manager includes built-in support for Docker Compose-based development environments with automatic port management and container isolation.

## Overview

When working with multiple worktrees simultaneously, each worktree needs its own set of services (databases, caches, APIs, etc.) running on different ports to avoid conflicts. The worktree manager automatically:

- Assigns unique port offsets to each worktree
- Generates Docker Compose override files with port mappings
- Creates isolated Docker networks and volumes per worktree
- Tracks port assignments in metadata

## Configuration

### Setup File Structure

Add a `docker_compose` section to your `.worktree-setup.json`:

```json
{
  "docker_compose": {
    "compose_dir": "deployment/docker_compose",
    "services": {
      "nginx": {
        "internal": 80,
        "description": "Web interface"
      },
      "api_server": {
        "internal": 8080,
        "description": "Backend API"
      },
      "relational_db": {
        "internal": 5432,
        "description": "PostgreSQL",
        "volumes": ["db_volume"]
      },
      "index": {
        "internal": 19071,
        "description": "Vespa search",
        "volumes": ["vespa_volume"]
      },
      "cache": {
        "internal": 6379,
        "description": "Redis"
      },
      "minio": {
        "internal": 9000,
        "description": "S3 storage",
        "volumes": ["minio_data"]
      }
    }
  },
  "setup_steps": [
    // ... your setup steps
  ]
}
```

### Configuration Fields

- **compose_dir**: Path to your docker-compose files (relative to repo root)
- **services**: Dictionary of service configurations
  - **internal**: Internal container port
  - **description**: Human-readable description (optional)
  - **volumes**: List of volume names that need isolation (optional)

## Port Management

### Port Offset System

Each worktree receives a unique port offset:
- First worktree: offset 0
- Second worktree: offset 10
- Third worktree: offset 20
- And so on...

### Port Mappings

External ports are calculated as: `internal_port + port_offset`

Example for two worktrees:

**dev1** (offset 0):
```yaml
ports:
  - "80:80"      # nginx
  - "8080:8080"  # api_server
  - "5432:5432"  # relational_db
```

**dev2** (offset 10):
```yaml
ports:
  - "90:80"      # nginx
  - "8090:8080"  # api_server
  - "5442:5432"  # relational_db
```

## Container Isolation

### Unique Container Names

Each service gets a unique container name:
```yaml
container_name: {service}-{worktree_name}
```

Examples: `api_server-dev1`, `relational_db-dev2`

### Isolated Networks

Each worktree gets its own Docker network:
```yaml
networks:
  default:
    name: {repo}-{worktree_name}-network
```

### Volume Isolation

Volumes specified in the configuration are renamed per worktree for complete data isolation:
```yaml
volumes:
  db_volume-dev1:
  vespa_volume-dev1:
```

This ensures:
- Separate database instances
- Independent migrations
- Isolated test data
- No schema conflicts

## Generated Files

When you create a worktree with Docker configuration, the tool generates:

**docker-compose.worktree-{name}.yml**

Located in your compose directory, this file contains:
- Service overrides with unique container names
- Port mappings with calculated offsets
- Network configuration
- Renamed volumes for isolation

## Usage

### Creating a Worktree

```bash
worktree <alias> new <name>
```

If your `.worktree-setup.json` includes Docker configuration, the tool will:
1. Generate the Docker Compose override file
2. Assign a unique port offset
3. Save metadata for port tracking
4. Display the port mappings

### Viewing Port Assignments

```bash
worktree <alias> list
```

This shows all worktrees with their port assignments.

### Managing Services

The worktree manager provides convenient commands to manage Docker Compose services. **All service commands must be run from within the worktree directory.**

#### Workflow

```bash
# 1. Switch to your worktree
worktree onyx select feature-auth

# Now you're in the worktree directory
# 2. Start services
worktree onyx services start

# 3. Check status
worktree onyx services status

# 4. View logs
worktree onyx services logs api_server -f

# 5. Stop when done
worktree onyx services stop
```

#### Start Services

```bash
# Start all services
worktree <alias> services start

# Start with rebuilding images
worktree <alias> services start --build

# Start specific services only
worktree <alias> services start --svcs api_server relational_db
worktree <alias> services start --services nginx cache  # --services also works
```

#### Stop Services

```bash
# Stop all services
worktree <alias> services stop

# Stop specific services only
worktree <alias> services stop --svcs api_server
worktree <alias> services stop --services nginx cache

# Stop and remove volumes (WARNING: deletes all data)
worktree <alias> services stop --volumes
```

#### Restart Services

```bash
# Restart all services
worktree <alias> services restart

# Restart specific services only
worktree <alias> services restart --svcs api_server
worktree <alias> services restart --services relational_db cache
```

#### Check Service Status

```bash
# View status of all services
worktree <alias> services status
```

This shows which containers are running and displays the port mappings.

#### View Logs

```bash
# View logs for all services
worktree <alias> services logs

# View logs for a specific service
worktree <alias> services logs api_server

# Follow logs in real-time
worktree <alias> services logs api_server -f

# Show last 100 lines
worktree <alias> services logs --tail 100

# Combine options
worktree <alias> services logs api_server -f --tail 50
```

### Manual Docker Compose Commands

You can also use Docker Compose directly if needed:

```bash
cd /path/to/worktree/compose-directory
docker-compose -f docker-compose.yml -f docker-compose.worktree-{name}.yml up -d
docker-compose -f docker-compose.yml -f docker-compose.worktree-{name}.yml down
docker-compose -f docker-compose.yml -f docker-compose.worktree-{name}.yml logs -f [service]
```

## Metadata Storage

Port assignments and worktree metadata are stored in:
```
~/.worktree-metadata.json
```

This file tracks:
- Which worktrees exist for each repository
- Port offset assigned to each worktree
- Port mappings for each service

## Example Workflow

```bash
# Create first worktree
worktree onyx new feature-auth
# → Gets port offset 0
# → nginx: 80, api: 8080, db: 5432

# Create second worktree
worktree onyx new feature-search
# → Gets port offset 10
# → nginx: 90, api: 8090, db: 5442

# Both can run simultaneously without conflicts!

# Work on feature-auth
worktree onyx select feature-auth
worktree onyx services start
worktree onyx services status
# Access at: http://localhost:80, API: http://localhost:8080

# Switch to feature-search
worktree onyx select feature-search
worktree onyx services start
worktree onyx services status
# Access at: http://localhost:90, API: http://localhost:8090

# View logs for specific service
worktree onyx services logs api_server -f

# Restart a service after making changes
worktree onyx services restart --svcs api_server

# Stop services when done
worktree onyx services stop

# Switch back to feature-auth
worktree onyx select feature-auth
worktree onyx services stop
```

## Benefits

### Complete Isolation
- Each worktree has its own database instance
- Separate volumes mean independent data
- Different schemas and migrations don't interfere

### Run Multiple Worktrees
- Test different branches simultaneously
- Compare implementations side-by-side
- Run integration tests in parallel

### Automatic Port Management
- No manual port configuration
- No port conflicts
- Consistent port offset system

### Clean Removal
- Removing a worktree cleans up metadata
- Port offsets are freed for reuse
- No orphaned Docker resources

## Troubleshooting

### Port Already in Use

If you get port conflicts:
1. Check for services running outside Docker: `lsof -i :<port>`
2. Stop conflicting services
3. Verify no other worktrees are using that offset

### Override File Not Found

Ensure:
1. The `.worktree-setup.json` file is in your repo root
2. The `docker_compose` section is properly configured
3. The worktree was created after adding Docker configuration

### Volume Data Persistence

To reset a worktree's database:
```bash
docker-compose -f docker-compose.yml -f docker-compose.worktree-{name}.yml down -v
```

The `-v` flag removes volumes and all data.

## Advanced Configuration

### Custom Port Ranges

The default port offset increment is 10. For services on higher ports (e.g., 19071), this provides adequate spacing. If you need different offsets, you can:

1. Manually edit the generated override file
2. Update metadata to reflect custom offsets
3. Use environment variables in your docker-compose.yml

### Additional Services

To add services not in the configuration:

1. Update `.worktree-setup.json` with new services
2. Regenerate override file or manually add to existing one
3. Ensure port spacing accommodates new services

### Shared Volumes

If you need to share data between worktrees (not recommended for databases):

1. Use absolute volume paths in docker-compose.yml
2. Don't include the volume in the `volumes` list in configuration
3. The volume won't be renamed per worktree

## See Also

- [README.md](README.md) - General worktree manager documentation
- [onyx-setup.example.json](onyx-setup.example.json) - Example configuration with Docker setup
- [onyx-docker-config.example.json](onyx-docker-config.example.json) - Standalone Docker configuration example
