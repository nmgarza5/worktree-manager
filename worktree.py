#!/usr/bin/env python3
"""
Git Worktree Manager

A tool to manage git worktrees across multiple repositories from anywhere.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class Colors:
    """ANSI color codes for terminal output"""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


class Spinner:
    """A simple terminal spinner for long-running operations"""

    def __init__(self, message: str = "Loading..."):
        self.message = message
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.running = False
        self.thread = None

    def _spin(self):
        """The spinner animation loop"""
        idx = 0
        while self.running:
            char = self.spinner_chars[idx % len(self.spinner_chars)]
            sys.stdout.write(f'\r{Colors.BLUE}{char}{Colors.END} {self.message}')
            sys.stdout.flush()
            time.sleep(0.1)
            idx += 1

    def start(self):
        """Start the spinner"""
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()

    def stop(self, final_message: Optional[str] = None):
        """Stop the spinner and optionally print a final message"""
        self.running = False
        if self.thread:
            self.thread.join()
        # Clear the spinner line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()
        if final_message:
            print(final_message)


class RepoConfig:
    """Manages repository configuration"""

    def __init__(self):
        self.config_file = Path.home() / ".worktree-repos.json"
        self.repos = self._load_repos()

    def _load_repos(self) -> Dict[str, str]:
        """Load repository aliases from config file"""
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"{Colors.RED}Error: Invalid JSON in {self.config_file}{Colors.END}")
            return {}

    def _save_repos(self):
        """Save repository aliases to config file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.repos, f, indent=2)

    def add_repo(self, alias: str, path: str):
        """Add a repository alias"""
        repo_path = Path(path).expanduser().resolve()

        if not repo_path.exists():
            print(f"{Colors.RED}Error: Path does not exist: {repo_path}{Colors.END}")
            sys.exit(1)

        # Verify it's a git repository
        if not (repo_path / ".git").exists():
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"{Colors.RED}Error: Not a git repository: {repo_path}{Colors.END}")
                sys.exit(1)

        self.repos[alias] = str(repo_path)
        self._save_repos()
        print(f"{Colors.GREEN}✓{Colors.END} Added repository alias '{alias}' -> {repo_path}")

    def remove_repo(self, alias: str):
        """Remove a repository alias"""
        if alias not in self.repos:
            print(f"{Colors.RED}Error: Repository alias '{alias}' not found{Colors.END}")
            sys.exit(1)

        del self.repos[alias]
        self._save_repos()
        print(f"{Colors.GREEN}✓{Colors.END} Removed repository alias '{alias}'")

    def list_repos(self):
        """List all repository aliases"""
        if not self.repos:
            print(f"{Colors.YELLOW}No repositories configured{Colors.END}")
            print(f"\nAdd a repository with:")
            print(f"  worktree repo add <alias> <path>")
            return

        print(f"{Colors.BOLD}Configured repositories:{Colors.END}\n")
        for alias, path in sorted(self.repos.items()):
            exists = Path(path).exists()
            indicator = f"{Colors.GREEN}✓{Colors.END}" if exists else f"{Colors.RED}✗{Colors.END}"
            print(f"  {indicator} {Colors.BOLD}{alias}{Colors.END}")
            print(f"      {path}")
            print()

    def get_repo_path(self, alias: str) -> Optional[Path]:
        """Get repository path from alias"""
        if alias not in self.repos:
            return None
        return Path(self.repos[alias])


class WorktreeMetadata:
    """Manages worktree metadata including port assignments"""

    def __init__(self):
        self.metadata_file = Path.home() / ".worktree-metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load worktree metadata from config file"""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"{Colors.RED}Error: Invalid JSON in {self.metadata_file}{Colors.END}")
            return {}

    def _save_metadata(self):
        """Save worktree metadata to config file"""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available on the system"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', port))
                return True
        except OSError:
            return False

    def get_next_port_offset(self, repo_alias: str, services_config: Dict[str, Any]) -> int:
        """Get the next available port offset for a repository

        Checks both metadata and actual port availability to avoid conflicts.
        """
        used_offsets = []

        if repo_alias in self.metadata:
            used_offsets = [
                wt_data.get('port_offset', 0)
                for wt_data in self.metadata[repo_alias].values()
            ]

        # Extract base ports from services config
        base_ports = []
        for service_name, service_config in services_config.items():
            internal_port = service_config.get('internal')
            if internal_port:
                base_ports.append(internal_port)

            # Also check additional ports (e.g., nginx has both 80 and 3000)
            additional_ports = service_config.get('additional_ports', [])
            base_ports.extend(additional_ports)

        if not base_ports:
            return 0

        # Find next available offset (increment by 10)
        # Check both metadata and actual port availability
        next_offset = 0
        max_attempts = 100  # Prevent infinite loop
        attempts = 0

        while attempts < max_attempts:
            # Check if this offset is already used in metadata
            if next_offset in used_offsets:
                next_offset += 10
                attempts += 1
                continue

            # Check if all ports with this offset are actually available
            all_ports_available = True
            for base_port in base_ports:
                test_port = base_port + next_offset
                if not self._is_port_available(test_port):
                    all_ports_available = False
                    break

            if all_ports_available:
                return next_offset

            # If any port is not available, try next offset
            next_offset += 10
            attempts += 1

        # If we couldn't find an available offset, warn and return a high offset
        print(f"{Colors.YELLOW}⚠ Warning: Could not find available ports after {max_attempts} attempts. Using offset {next_offset}{Colors.END}")
        return next_offset

    def add_worktree(self, repo_alias: str, worktree_name: str, port_offset: int, ports: Dict[str, int]):
        """Add worktree metadata"""
        if repo_alias not in self.metadata:
            self.metadata[repo_alias] = {}

        self.metadata[repo_alias][worktree_name] = {
            'port_offset': port_offset,
            'ports': ports,
            'created': subprocess.run(['date', '+%Y-%m-%d'], capture_output=True, text=True).stdout.strip()
        }

        self._save_metadata()

    def remove_worktree(self, repo_alias: str, worktree_name: str):
        """Remove worktree metadata"""
        if repo_alias in self.metadata and worktree_name in self.metadata[repo_alias]:
            del self.metadata[repo_alias][worktree_name]

            # Clean up empty repo entries
            if not self.metadata[repo_alias]:
                del self.metadata[repo_alias]

            self._save_metadata()

    def get_worktree_ports(self, repo_alias: str, worktree_name: str) -> Optional[Dict[str, int]]:
        """Get port assignments for a worktree"""
        if repo_alias in self.metadata and worktree_name in self.metadata[repo_alias]:
            return self.metadata[repo_alias][worktree_name].get('ports')
        return None

    def list_all_worktrees(self, repo_alias: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """List all worktrees, optionally filtered by repo"""
        if repo_alias:
            return {repo_alias: self.metadata.get(repo_alias, {})}
        return self.metadata


class DatabaseManager:
    """Manages database dump and restore operations"""

    def __init__(self, repo_alias: str):
        self.repo_alias = repo_alias
        self.dumps_dir = Path.home() / ".worktree-dumps" / repo_alias
        self.dumps_dir.mkdir(parents=True, exist_ok=True)

    def _get_container_name(self, worktree_name: Optional[str] = None) -> Optional[str]:
        """Get the postgres container name for a worktree or main installation"""
        if worktree_name is None:
            # Look for main onyx installation container
            # Try common postgres container names for Onyx
            result = subprocess.run(
                "docker ps --format '{{.Names}}' | grep -i postgres",
                shell=True,
                capture_output=True,
                text=True
            )
            containers = result.stdout.strip().split('\n')

            # Filter out worktree containers (they end with -{worktree_name})
            # Main containers are typically: onyx_postgres, postgres, relational_db, onyx-postgres-1, etc.
            # Worktree containers are: relational_db-{worktree_name}
            main_containers = []
            for c in containers:
                if not c:
                    continue
                # Skip if it matches the worktree pattern: relational_db-{name}
                if c.startswith('relational_db-'):
                    continue
                # This is likely a main installation postgres
                main_containers.append(c)

            if main_containers:
                return main_containers[0]
            return None
        else:
            # Worktree container name
            return f"relational_db-{worktree_name}"

    def _wait_for_postgres(self, container_name: str, max_attempts: int = 30) -> bool:
        """Wait for postgres to be ready"""
        for i in range(max_attempts):
            result = subprocess.run(
                f"docker exec {container_name} pg_isready -U postgres",
                shell=True,
                capture_output=True
            )
            if result.returncode == 0:
                return True
            time.sleep(1)
        return False

    def dump_database(self, worktree_name: Optional[str] = None, output_file: Optional[Path] = None) -> Path:
        """Create a database dump from a worktree or main installation

        Returns the path to the dump file
        """
        container_name = self._get_container_name(worktree_name)

        if not container_name:
            if worktree_name is None:
                raise Exception("No main postgres container found. Is your main Onyx instance running?")
            else:
                raise Exception(f"Container 'relational_db-{worktree_name}' not found. Is it running?")

        # Verify container is running
        result = subprocess.run(
            f"docker ps --filter 'name={container_name}' --format '{{{{.Names}}}}'",
            shell=True,
            capture_output=True,
            text=True
        )
        if container_name not in result.stdout:
            raise Exception(f"Container '{container_name}' is not running")

        # Wait for postgres to be ready
        if not self._wait_for_postgres(container_name):
            raise Exception(f"Postgres in container '{container_name}' did not become ready")

        # Determine output file
        if output_file is None:
            timestamp = subprocess.run(['date', '+%Y%m%d-%H%M%S'], capture_output=True, text=True).stdout.strip()
            dump_name = f"{worktree_name or 'main'}-{timestamp}.sql"
            output_file = self.dumps_dir / dump_name

        # Create dump
        spinner = Spinner(f"Creating database dump from '{worktree_name or 'main'}'")
        spinner.start()
        try:
            cmd = f"docker exec {container_name} pg_dump -U postgres postgres > {output_file}"
            subprocess.run(cmd, shell=True, check=True)
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Dump created: {output_file}")
        except subprocess.CalledProcessError as e:
            spinner.stop()
            raise Exception(f"Failed to create dump: {e}")

        return output_file

    def restore_database(self, worktree_name: str, dump_file: Path):
        """Restore a database dump to a worktree's postgres"""
        if not dump_file.exists():
            raise Exception(f"Dump file not found: {dump_file}")

        container_name = self._get_container_name(worktree_name)
        if not container_name:
            raise Exception(f"Container 'relational_db-{worktree_name}' not found")

        # Verify container is running
        result = subprocess.run(
            f"docker ps --filter 'name={container_name}' --format '{{{{.Names}}}}'",
            shell=True,
            capture_output=True,
            text=True
        )
        if container_name not in result.stdout:
            raise Exception(f"Container '{container_name}' is not running. Start services first.")

        # Wait for postgres to be ready
        if not self._wait_for_postgres(container_name):
            raise Exception(f"Postgres in container '{container_name}' did not become ready")

        # Drop and recreate database to ensure clean state
        spinner = Spinner(f"Preparing database in '{worktree_name}' for restore")
        spinner.start()
        try:
            # Terminate all existing connections to postgres database
            # Connect to template1 to avoid "cannot drop the currently open database" error
            subprocess.run(
                f"docker exec {container_name} psql -U postgres template1 -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'postgres';\"",
                shell=True,
                capture_output=True,
                check=False
            )

            # Give connections a moment to terminate
            time.sleep(0.5)

            # Drop database (connecting to template1, not postgres)
            result = subprocess.run(
                f"docker exec {container_name} psql -U postgres template1 -c 'DROP DATABASE IF EXISTS postgres;'",
                shell=True,
                check=False,
                capture_output=True,
                text=True
            )

            # If drop still fails due to active connections, retry with force
            if result.returncode != 0 and "being accessed by other users" in result.stderr:
                # Force terminate again and retry
                subprocess.run(
                    f"docker exec {container_name} psql -U postgres template1 -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'postgres';\"",
                    shell=True,
                    capture_output=True,
                    check=False
                )
                time.sleep(1)
                subprocess.run(
                    f"docker exec {container_name} psql -U postgres template1 -c 'DROP DATABASE postgres;'",
                    shell=True,
                    check=True,
                    capture_output=True
                )
            elif result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

            # Create fresh database
            subprocess.run(
                f"docker exec {container_name} psql -U postgres template1 -c 'CREATE DATABASE postgres;'",
                shell=True,
                check=True,
                capture_output=True
            )
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Database prepared for restore")
        except subprocess.CalledProcessError as e:
            spinner.stop()
            raise Exception(f"Failed to prepare database: {e}")

        # Restore dump
        spinner = Spinner(f"Restoring database dump to '{worktree_name}'")
        spinner.start()
        try:
            cmd = f"docker exec -i {container_name} psql -U postgres postgres < {dump_file}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Database restored successfully")
        except subprocess.CalledProcessError as e:
            spinner.stop()
            raise Exception(f"Failed to restore dump: {e}")

    def list_dumps(self) -> List[Path]:
        """List all available dumps for this repository"""
        if not self.dumps_dir.exists():
            return []
        return sorted(self.dumps_dir.glob("*.sql"), key=lambda p: p.stat().st_mtime, reverse=True)

    def get_dump_info(self, dump_file: Path) -> Dict[str, str]:
        """Get information about a dump file"""
        stat = dump_file.stat()
        size_mb = stat.st_size / (1024 * 1024)
        mtime = subprocess.run(['date', '-r', str(int(stat.st_mtime)), '+%Y-%m-%d %H:%M:%S'],
                             capture_output=True, text=True).stdout.strip()
        return {
            'name': dump_file.name,
            'size': f"{size_mb:.1f} MB",
            'modified': mtime,
            'path': str(dump_file)
        }


class SetupExecutor:
    """Executes setup steps based on configuration"""

    def __init__(self, worktree_path: Path, colors: 'Colors'):
        self.worktree_path = worktree_path
        self.colors = colors
        self.venv_path = worktree_path / ".venv"

    def _run_command(self, cmd: List[str], cwd: Optional[Path] = None,
                     capture_output: bool = False, check: bool = True, shell: bool = False) -> subprocess.CompletedProcess:
        """Run a shell command"""
        try:
            if shell:
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = subprocess.run(
                    cmd_str,
                    cwd=cwd or self.worktree_path,
                    capture_output=capture_output,
                    text=True,
                    check=check,
                    shell=True
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=cwd or self.worktree_path,
                    capture_output=capture_output,
                    text=True,
                    check=check
                )
            return result
        except subprocess.CalledProcessError as e:
            # Print error on new line after spinner is cleared
            print(f"\n{self.colors.RED}Command failed: {cmd if isinstance(cmd, str) else ' '.join(cmd)}{self.colors.END}")
            if e.stderr:
                print(f"{self.colors.RED}{e.stderr}{self.colors.END}")
            if e.stdout:
                print(f"{e.stdout}")
            raise

    def _print_step(self, message: str):
        """Print a step message"""
        print(f"{self.colors.BLUE}==>{self.colors.END} {self.colors.BOLD}{message}{self.colors.END}")

    def _print_success(self, message: str):
        """Print a success message"""
        print(f"{self.colors.GREEN}✓{self.colors.END} {message}")

    def _get_pip_path(self) -> Path:
        """Get path to pip in virtual environment"""
        if sys.platform == "win32":
            return self.venv_path / "Scripts" / "pip"
        return self.venv_path / "bin" / "pip"

    def _get_executable_path(self, name: str) -> Path:
        """Get path to an executable in virtual environment"""
        if sys.platform == "win32":
            return self.venv_path / "Scripts" / name
        return self.venv_path / "bin" / name

    def _convert_typed_step_to_command(self, step: Dict[str, Any]) -> Optional[str]:
        """Convert typed steps (python_venv, pip_install, etc.) to shell commands"""
        step_type = step.get("type")

        if not step_type:
            return None

        if step_type == "python_venv":
            return "python3 -m venv .venv"

        elif step_type == "pip_install":
            requirements = step.get("requirements", [])
            if not requirements:
                return None
            # Activate venv and install requirements
            req_files = " ".join([f"-r {r}" for r in requirements])
            return f"source .venv/bin/activate && pip install {req_files}"

        elif step_type == "pip_install_editable":
            path = step.get("path", ".")
            return f"source .venv/bin/activate && pip install -e {path}"

        elif step_type == "pip_install_package":
            package = step.get("package")
            if not package:
                return None
            return f"source .venv/bin/activate && pip install {package}"

        elif step_type == "precommit_install":
            path = step.get("path", ".")
            return f"source .venv/bin/activate && cd {path} && pre-commit install"

        elif step_type == "playwright_install":
            return "source .venv/bin/activate && playwright install"

        elif step_type == "npm_install":
            path = step.get("path", ".")
            return f"cd {path} && npm install"

        return None

    def execute_step(self, step: Dict[str, Any], verbose: bool = False):
        """Execute a single setup step by running the command from the setup file

        This executes arbitrary shell commands defined in the setup configuration.
        All errors are surfaced to the user so they can debug their commands.
        """
        step_name = step.get("name", "Unnamed step")
        command = step.get("command")
        cwd = step.get("cwd")

        # If no direct command, try to convert from type
        if not command:
            command = self._convert_typed_step_to_command(step)

        if not command:
            print(f"{self.colors.YELLOW}⚠ Step '{step_name}' has no command to execute{self.colors.END}")
            return

        # Start spinner for the step (only if not verbose)
        spinner = None
        if not verbose:
            spinner = Spinner(step_name)
            spinner.start()
        else:
            print(f"\n{self.colors.BOLD}Running: {step_name}{self.colors.END}")
            print(f"{self.colors.DIM}Command: {command}{self.colors.END}")

        try:
            # Determine working directory
            work_dir = self.worktree_path / cwd if cwd else self.worktree_path

            # Execute the command
            result = subprocess.run(
                command,
                cwd=work_dir,
                shell=True,
                capture_output=not verbose,  # Stream output if verbose
                text=True,
                check=True
            )

            if spinner:
                spinner.stop(f"{self.colors.GREEN}✓{self.colors.END} {step_name}")
            else:
                print(f"{self.colors.GREEN}✓{self.colors.END} {step_name} complete")

        except subprocess.CalledProcessError as e:
            if spinner:
                spinner.stop()
            # Surface all error details to the user
            print(f"\n{self.colors.RED}✗ Setup step failed: {step_name}{self.colors.END}")
            print(f"\n{self.colors.BOLD}Command:{self.colors.END}")
            print(f"  {command}")
            if cwd:
                print(f"\n{self.colors.BOLD}Working directory:{self.colors.END}")
                print(f"  {work_dir}")
            print(f"\n{self.colors.BOLD}Exit code:{self.colors.END} {e.returncode}")

            if e.stdout:
                print(f"\n{self.colors.BOLD}Standard output:{self.colors.END}")
                print(e.stdout)

            if e.stderr:
                print(f"\n{self.colors.BOLD}Standard error:{self.colors.END}")
                print(f"{self.colors.RED}{e.stderr}{self.colors.END}")

            print(f"\n{self.colors.YELLOW}This is a problem with your setup command, not the worktree tool.{self.colors.END}")
            print(f"{self.colors.YELLOW}Please fix the command in your setup configuration file.{self.colors.END}")
            raise

        except Exception as e:
            if spinner:
                spinner.stop()
            print(f"\n{self.colors.RED}✗ Unexpected error in step '{step_name}': {str(e)}{self.colors.END}")
            raise


    def _generate_docker_compose_override(self, worktree_name: str, port_offset: int, config: Dict[str, Any]):
        """Generate Docker Compose override file for worktree"""
        services_config = config.get('services', {})
        compose_dir = config.get('compose_dir', 'deployment/docker_compose')

        compose_path = self.worktree_path / compose_dir
        if not compose_path.exists():
            print(f"{self.colors.YELLOW}  Docker compose directory not found: {compose_path}{self.colors.END}")
            return None

        # Load base docker-compose.yml to extract volume configurations
        base_compose_file = compose_path / 'docker-compose.yml'
        base_services = {}

        if base_compose_file.exists():
            try:
                import yaml
                with open(base_compose_file, 'r') as f:
                    base_compose = yaml.safe_load(f)
                    base_services = base_compose.get('services', {})
            except ImportError:
                # If PyYAML is not available, parse manually (basic support)
                base_services = self._parse_yaml_manually(base_compose_file)
            except Exception as e:
                print(f"{self.colors.YELLOW}⚠ Warning: Could not parse base docker-compose.yml: {e}{self.colors.END}")

        # Calculate ports for each service
        ports_map = {}
        services_override = {}

        for service_name, service_config in services_config.items():
            # Skip services that are only meant to have ports commented out (not in Docker for dev)
            if service_config.get('skip_override', False):
                continue

            internal_port = service_config.get('internal')
            if internal_port:
                external_port = internal_port + port_offset
                ports_map[service_name] = external_port

                # Build port mappings list
                port_mappings = [f"{external_port}:{internal_port}"]

                # Add additional port mappings (e.g., nginx has both 80 and 3000 -> 80)
                additional_ports = service_config.get('additional_ports', [])
                for add_port in additional_ports:
                    add_external = add_port + port_offset
                    port_mappings.append(f"{add_external}:{internal_port}")

                # Build service override
                service_override = {
                    'container_name': f"{service_name}-{worktree_name}",
                    'ports': port_mappings
                }

                # Add environment overrides if specified
                env_overrides = service_config.get('environment', {})
                if env_overrides:
                    service_override['environment'] = env_overrides

                # Build volumes list (handles both hot reloading and data isolation)
                final_volumes = []

                # Add volume mounts if specified (for hot reloading)
                volume_mounts = service_config.get('volumes', [])
                if volume_mounts:
                    final_volumes.extend(volume_mounts)

                # Handle volume renaming for data isolation
                if service_config.get('isolate_data', False):
                    # Get volume configuration from base docker-compose.yml
                    base_service = base_services.get(service_name, {})
                    base_volumes = base_service.get('volumes', [])

                    if base_volumes:
                        for vol in base_volumes:
                            # Parse volume spec: volume_name:mount_path[:options]
                            if isinstance(vol, str) and ':' in vol:
                                parts = vol.split(':', 1)
                                vol_name = parts[0]
                                mount_spec = parts[1] if len(parts) > 1 else ''

                                # Rename the volume while preserving mount path
                                renamed_vol_name = f"{vol_name}-{worktree_name}"
                                final_volumes.append(f"{renamed_vol_name}:{mount_spec}")
                            else:
                                # Keep non-named volumes as-is
                                final_volumes.append(vol)
                else:
                    # If not isolating data, include base volumes
                    base_service = base_services.get(service_name, {})
                    base_volumes = base_service.get('volumes', [])
                    if base_volumes:
                        final_volumes.extend(base_volumes)

                if final_volumes:
                    service_override['volumes'] = final_volumes

                services_override[service_name] = service_override

        # Create the override file content
        override_content = {
            'name': f'onyx-{worktree_name}',
            'services': services_override
        }

        # Add volume definitions for renamed volumes
        volumes_def = {}
        for service_name, service_config in services_config.items():
            if service_config.get('isolate_data', False):
                # Get volume configuration from base docker-compose.yml
                base_service = base_services.get(service_name, {})
                base_volumes = base_service.get('volumes', [])

                for vol in base_volumes:
                    if isinstance(vol, str) and ':' in vol:
                        vol_name = vol.split(':', 1)[0]
                        # Only include named volumes (not bind mounts starting with . or /)
                        if not vol_name.startswith('.') and not vol_name.startswith('/'):
                            renamed_vol_name = f"{vol_name}-{worktree_name}"
                            volumes_def[renamed_vol_name] = {}

        if volumes_def:
            override_content['volumes'] = volumes_def

        # Write the override file
        override_file = compose_path / f'docker-compose.worktree-{worktree_name}.yml'

        import yaml
        try:
            with open(override_file, 'w') as f:
                yaml.dump(override_content, f, default_flow_style=False, sort_keys=False)
        except ImportError:
            # Fallback: write as JSON-like YAML manually
            self._write_yaml_manually(override_file, override_content)

        return ports_map

    def _parse_yaml_manually(self, filepath: Path) -> Dict[str, Any]:
        """Basic YAML parser for docker-compose.yml files (fallback when PyYAML unavailable)"""
        services = {}
        current_service = None
        in_volumes = False

        try:
            with open(filepath, 'r') as f:
                for line in f:
                    stripped = line.strip()

                    # Skip comments and empty lines
                    if not stripped or stripped.startswith('#'):
                        continue

                    # Check if we're in services section
                    if stripped == 'services:':
                        in_volumes = False
                        continue

                    # Service definition (2 spaces indent)
                    if line.startswith('  ') and not line.startswith('    ') and ':' in stripped:
                        service_name = stripped.rstrip(':')
                        current_service = service_name
                        services[service_name] = {'volumes': []}
                        in_volumes = False
                        continue

                    # Volumes section within a service
                    if current_service and stripped == 'volumes:':
                        in_volumes = True
                        continue

                    # Volume entry (6 spaces indent)
                    if in_volumes and line.startswith('      - '):
                        vol_spec = stripped[2:]  # Remove '- ' prefix
                        services[current_service]['volumes'].append(vol_spec)

        except Exception as e:
            print(f"{Colors.YELLOW}⚠ Warning: Manual YAML parsing failed: {e}{Colors.END}")

        return services

    def _write_yaml_manually(self, filepath: Path, data: Dict[str, Any]):
        """Write YAML file manually without PyYAML dependency"""
        with open(filepath, 'w') as f:
            f.write(f"# Auto-generated Docker Compose override\n")
            f.write(f"# Worktree: {filepath.stem.replace('docker-compose.worktree-', '')}\n\n")

            if 'name' in data:
                f.write(f"name: {data['name']}\n\n")

            if 'services' in data:
                f.write("services:\n")
                for service_name, service_config in data['services'].items():
                    f.write(f"  {service_name}:\n")
                    if 'container_name' in service_config:
                        f.write(f"    container_name: {service_config['container_name']}\n")
                    if 'ports' in service_config:
                        f.write(f"    ports:\n")
                        for port in service_config['ports']:
                            f.write(f"      - \"{port}\"\n")
                    if 'environment' in service_config:
                        f.write(f"    environment:\n")
                        for key, value in service_config['environment'].items():
                            f.write(f"      - {key}={value}\n")
                    if 'volumes' in service_config:
                        f.write(f"    volumes:\n")
                        for vol in service_config['volumes']:
                            f.write(f"      - {vol}\n")

            if 'volumes' in data:
                f.write("\nvolumes:\n")
                for vol_name in data['volumes'].keys():
                    f.write(f"  {vol_name}:\n")


class WorktreeManager:
    """Manages git worktrees with optional setup configuration"""

    def __init__(self, repo_path: Path, repo_alias: Optional[str] = None):
        self.main_repo = repo_path
        self.repo_alias = repo_alias or repo_path.name

        # Verify it's a git repository
        if not (self.main_repo / ".git").exists():
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.main_repo,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"{Colors.RED}Error: Not a git repository: {self.main_repo}{Colors.END}")
                sys.exit(1)

        # Create worktrees directory: <parent>/<repo-name>-worktrees/
        repo_name = self.main_repo.name
        self.worktree_base = self.main_repo.parent / f"{repo_name}-worktrees"

        # Initialize metadata tracker
        self.metadata = WorktreeMetadata()

        # Initialize database manager
        self.db_manager = DatabaseManager(self.repo_alias)

    def _load_setup_config(self) -> Optional[Dict]:
        """Load setup configuration if it exists (supports both YAML and JSON)"""
        # Look for repo-specific setup files first
        possible_configs = [
            # Repo-specific YAML (preferred)
            (self.main_repo / f"{self.repo_alias}-setup.yaml", "yaml"),
            (self.main_repo / f"{self.repo_alias}-setup.yml", "yaml"),
            # Repo-specific JSON (backward compatibility)
            (self.main_repo / f"{self.repo_alias}-setup.json", "json"),
            # Generic setup files in repo
            (self.main_repo / ".worktree-setup.yaml", "yaml"),
            (self.main_repo / ".worktree-setup.yml", "yaml"),
            (self.main_repo / ".worktree-setup.json", "json"),
            # Global setup files
            (Path.home() / ".worktree-setup.yaml", "yaml"),
            (Path.home() / ".worktree-setup.yml", "yaml"),
            (Path.home() / ".worktree-setup.json", "json"),
        ]

        for config_path, format_type in possible_configs:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        if format_type == "yaml":
                            if not HAS_YAML:
                                print(f"{Colors.YELLOW}⚠ Warning: PyYAML not installed, skipping {config_path}{Colors.END}")
                                print(f"{Colors.YELLOW}  Install with: pip install pyyaml{Colors.END}")
                                continue
                            return yaml.safe_load(f)
                        else:  # json
                            return json.load(f)
                except (json.JSONDecodeError, yaml.YAMLError) as e:
                    print(f"{Colors.YELLOW}⚠ Warning: Invalid {format_type.upper()} in {config_path}: {e}{Colors.END}")
                    continue

        return None

    def _run_command(self, cmd: List[str], cwd: Optional[Path] = None,
                     capture_output: bool = False, check: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.main_repo,
                capture_output=capture_output,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            print(f"{Colors.RED}Command failed: {' '.join(cmd)}{Colors.END}")
            if e.stderr:
                print(f"{Colors.RED}{e.stderr}{Colors.END}")
            raise

    def _print_step(self, message: str):
        """Print a step message"""
        print(f"{Colors.BLUE}==>{Colors.END} {Colors.BOLD}{message}{Colors.END}")

    def _print_success(self, message: str):
        """Print a success message"""
        print(f"{Colors.GREEN}✓{Colors.END} {message}")

    def _print_warning(self, message: str):
        """Print a warning message"""
        print(f"{Colors.YELLOW}⚠{Colors.END} {message}")

    def _get_worktree_path(self, name: str) -> Path:
        """Get the full path for a worktree"""
        return self.worktree_base / name

    def _remove_conflicting_ports(self, worktree_path: Path, docker_config: Dict[str, Any]):
        """Remove port mappings from base docker-compose.yml that conflict with override

        This prevents Docker Compose from merging base and override ports.
        """
        compose_dir = docker_config.get('compose_dir', 'deployment/docker_compose')
        base_compose_file = worktree_path / compose_dir / 'docker-compose.yml'

        if not base_compose_file.exists():
            return

        try:
            # Read the file
            with open(base_compose_file, 'r') as f:
                lines = f.readlines()

            # Track which services have ports configured in our setup
            services_with_overrides = set(docker_config.get('services', {}).keys())

            modified = False
            new_lines = []
            in_service = None
            in_ports_section = False
            indent_level = 0

            for i, line in enumerate(lines):
                # Detect service definition
                if line.strip() and not line.strip().startswith('#') and ':' in line:
                    # Check if this is a top-level service (2 spaces indent or less)
                    leading_spaces = len(line) - len(line.lstrip())
                    if leading_spaces <= 2 and line.strip().endswith(':'):
                        service_name = line.strip().rstrip(':')
                        if service_name in services_with_overrides:
                            in_service = service_name
                        else:
                            in_service = None

                # Detect ports section within our service
                if in_service and line.strip() == 'ports:':
                    in_ports_section = True
                    indent_level = len(line) - len(line.lstrip())
                    # Comment out the ports: line
                    new_lines.append(line.replace('ports:', '# ports:  # Managed by worktree override'))
                    modified = True
                    continue

                # If in ports section, comment out port mappings
                if in_ports_section:
                    current_indent = len(line) - len(line.lstrip())
                    # Check if we're still in the ports array
                    if current_indent > indent_level and (line.strip().startswith('-') or not line.strip()):
                        # Comment out this port mapping
                        if line.strip():
                            new_lines.append('#' + line)
                            modified = True
                        else:
                            new_lines.append(line)
                        continue
                    else:
                        # We've exited the ports section
                        in_ports_section = False

                new_lines.append(line)

            if modified:
                # Write back
                with open(base_compose_file, 'w') as f:
                    f.writelines(new_lines)
                self._print_success(f"Commented out conflicting ports in {base_compose_file.name}")

        except Exception as e:
            self._print_warning(f"Could not modify base docker-compose.yml: {e}")

    def _get_existing_worktrees(self) -> Dict[str, str]:
        """Get list of existing worktrees"""
        result = self._run_command(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True
        )

        worktrees = {}
        current_path = None
        current_branch = None

        for line in result.stdout.split('\n'):
            if line.startswith('worktree '):
                current_path = line.split(' ', 1)[1]
            elif line.startswith('branch '):
                current_branch = line.split('refs/heads/', 1)[1] if 'refs/heads/' in line else 'detached'
                if current_path and current_path != str(self.main_repo):
                    if str(self.worktree_base) in current_path:
                        worktrees[Path(current_path).name] = current_branch
                current_path = None
                current_branch = None

        return worktrees

    def create_worktree(self, name: str, base_branch: str = "origin/main", skip_setup: bool = False, verbose: bool = False, shell_mode: bool = False, restore_db: Optional[str] = None, copy_db_from_main: bool = False):
        """Create a new worktree with optional environment setup and database restore"""
        worktree_path = self._get_worktree_path(name)

        if worktree_path.exists():
            print(f"{Colors.RED}Error: Worktree '{name}' already exists at {worktree_path}{Colors.END}")
            sys.exit(1)

        self.worktree_base.mkdir(exist_ok=True)

        # Create worktree with spinner
        spinner = Spinner(f"Creating worktree '{name}' from {base_branch}")
        spinner.start()
        try:
            self._run_command([
                "git", "worktree", "add", "-b", name, str(worktree_path), base_branch
            ])
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Worktree created at {worktree_path}")
        except subprocess.CalledProcessError:
            spinner.stop()
            # Error already printed by _run_command
            sys.exit(1)
        except Exception as e:
            spinner.stop()
            raise

        # Handle Docker Compose configuration if present
        docker_config = None
        ports_map = None

        if not skip_setup:
            setup_config = self._load_setup_config()

            # Check for Docker Compose configuration
            if setup_config and "docker_compose" in setup_config:
                docker_config = setup_config["docker_compose"]
                services_config = docker_config.get('services', {})
                port_offset = self.metadata.get_next_port_offset(self.repo_alias, services_config)

                self._print_step("Generating Docker Compose override")
                executor = SetupExecutor(worktree_path, Colors)
                ports_map = executor._generate_docker_compose_override(name, port_offset, docker_config)

                if ports_map:
                    # Remove conflicting port mappings from base docker-compose.yml
                    self._remove_conflicting_ports(worktree_path, docker_config)

                    self._print_success("Docker Compose override generated")
                    # Save metadata
                    self.metadata.add_worktree(self.repo_alias, name, port_offset, ports_map)

            # Run other setup steps
            if setup_config and "setup_steps" in setup_config:
                print(f"\n{Colors.BOLD}Running setup steps...{Colors.END}\n")
                executor = SetupExecutor(worktree_path, Colors)

                for step in setup_config["setup_steps"]:
                    try:
                        executor.execute_step(step, verbose=verbose)
                    except Exception as e:
                        self._print_warning(f"Setup step failed: {step.get('name', step.get('type'))} - {str(e)}")
                        print(f"{Colors.YELLOW}Continuing with remaining steps...{Colors.END}")

        # Handle database restore if requested
        if (restore_db or copy_db_from_main) and not skip_setup:
            if not docker_config or 'relational_db' not in docker_config.get('services', {}):
                print(f"\n{Colors.YELLOW}⚠ Warning: Database restore requested but no PostgreSQL service configured{Colors.END}")
            else:
                # Start just the postgres service
                print(f"\n{Colors.BOLD}Database restore requested...{Colors.END}")
                base_file, override_file, compose_dir, _ = self._get_docker_compose_files(name)
                if base_file and override_file:
                    spinner = Spinner("Starting PostgreSQL service")
                    spinner.start()
                    try:
                        cmd = [
                            "docker", "compose",
                            "-f", str(base_file),
                            "-f", str(override_file),
                            "up", "-d", "relational_db"
                        ]
                        self._run_command(cmd, cwd=Path(compose_dir))
                        spinner.stop(f"{Colors.GREEN}✓{Colors.END} PostgreSQL started")

                        # Determine dump source
                        if copy_db_from_main:
                            # Create dump from main installation
                            try:
                                dump_file = self.db_manager.dump_database(worktree_name=None)
                                self.db_manager.restore_database(name, dump_file)
                            except Exception as e:
                                print(f"\n{Colors.RED}Error during database copy: {e}{Colors.END}")
                                print(f"{Colors.YELLOW}You can manually restore later with:{Colors.END}")
                                print(f"  worktree {self.repo_alias} db restore {name} <dump-file>")
                        elif restore_db:
                            # Restore from specified dump file
                            dump_path = Path(restore_db).expanduser()
                            if not dump_path.is_absolute():
                                # Try to find it in the dumps directory
                                dumps_dir_file = self.db_manager.dumps_dir / restore_db
                                if dumps_dir_file.exists():
                                    dump_path = dumps_dir_file
                            try:
                                self.db_manager.restore_database(name, dump_path)
                            except Exception as e:
                                print(f"\n{Colors.RED}Error during database restore: {e}{Colors.END}")
                                print(f"{Colors.YELLOW}You can manually restore later with:{Colors.END}")
                                print(f"  worktree {self.repo_alias} db restore {name} {dump_path}")
                    except subprocess.CalledProcessError:
                        spinner.stop()
                        print(f"\n{Colors.YELLOW}⚠ Could not start PostgreSQL service{Colors.END}")

        # In shell mode, output just the cd commands for the shell wrapper to eval
        if shell_mode:
            venv_activate = worktree_path / ".venv" / "bin" / "activate"
            print(f"cd {worktree_path}")
            if venv_activate.exists():
                print(f"source .venv/bin/activate")
        else:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Worktree '{name}' is ready!{Colors.END}")

            # Show port information if Docker Compose was configured
            if ports_map:
                print(f"\n{Colors.BOLD}Service Ports:{Colors.END}")
                for service, port in sorted(ports_map.items()):
                    print(f"  {service}: {port}")

    def remove_worktree(self, name: str, force: bool = False):
        """Remove a worktree and clean up its branch"""
        worktree_path = self._get_worktree_path(name)

        existing_worktrees = self._get_existing_worktrees()
        if name not in existing_worktrees:
            print(f"{Colors.RED}Error: Worktree '{name}' not found{Colors.END}")
            sys.exit(1)

        if not force:
            response = input(f"Are you sure you want to remove worktree '{name}'? [y/N]: ")
            if response.lower() != 'y':
                print("Cancelled.")
                return

        # Stop Docker Compose services if configured
        base_file, override_file, compose_dir, detected_name = self._get_docker_compose_files(name)
        if base_file and override_file and compose_dir:
            spinner = Spinner(f"Stopping services for worktree '{name}'")
            spinner.start()
            try:
                cmd = [
                    "docker", "compose",
                    "-f", str(base_file),
                    "-f", str(override_file),
                    "down"
                ]
                self._run_command(cmd, cwd=Path(compose_dir), check=False)
                spinner.stop(f"{Colors.GREEN}✓{Colors.END} Services stopped")
            except subprocess.CalledProcessError:
                spinner.stop()
                self._print_warning(f"Could not stop services (they may not be running)")
            except Exception as e:
                spinner.stop()
                self._print_warning(f"Could not stop services: {e}")

        # Remove worktree with spinner
        spinner = Spinner(f"Removing worktree '{name}'")
        spinner.start()
        try:
            force_flag = ["--force"] if force else []
            self._run_command(["git", "worktree", "remove", *force_flag, str(worktree_path)])
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Worktree removed: {worktree_path}")
        except subprocess.CalledProcessError as e:
            spinner.stop()
            # Check if it's the "contains modified files" error
            if "contains modified or untracked files" in (e.stderr or ""):
                print(f"\n{Colors.RED}Error: Worktree '{name}' contains uncommitted changes{Colors.END}")
                print(f"\n{Colors.YELLOW}Options:{Colors.END}")
                print(f"  1. Commit or stash your changes")
                print(f"  2. Use --force to delete anyway: {Colors.BOLD}worktree {self.repo_alias} rm {name} --force{Colors.END}")
            else:
                # Re-raise for other errors
                raise
            sys.exit(1)
        except Exception as e:
            spinner.stop()
            raise

        branch_name = existing_worktrees[name]
        if branch_name != 'detached':
            try:
                spinner = Spinner(f"Deleting branch '{branch_name}'")
                spinner.start()
                self._run_command(["git", "branch", "-D", branch_name], check=False)
                spinner.stop(f"{Colors.GREEN}✓{Colors.END} Branch '{branch_name}' deleted")
            except subprocess.CalledProcessError:
                spinner.stop()
                self._print_warning(f"Could not delete branch '{branch_name}' (may already be deleted)")

        # Clean up metadata
        self.metadata.remove_worktree(self.repo_alias, name)

        print(f"\n{Colors.GREEN}✓ Worktree '{name}' removed successfully{Colors.END}")

    def select_worktree(self, name: str, output_cd_command: bool = False):
        """Switch to a worktree"""
        worktree_path = self._get_worktree_path(name)

        existing_worktrees = self._get_existing_worktrees()
        if name not in existing_worktrees:
            print(f"{Colors.RED}Error: Worktree '{name}' not found{Colors.END}")
            print(f"\nAvailable worktrees:")
            for wt_name in existing_worktrees.keys():
                print(f"  - {wt_name}")
            sys.exit(1)

        venv_activate = worktree_path / ".venv" / "bin" / "activate"

        if output_cd_command:
            # Output just the cd command for shell function to eval
            print(f"cd {worktree_path}")
            if venv_activate.exists():
                print(f"source .venv/bin/activate")
        else:
            print(f"{Colors.GREEN}Switching to worktree '{name}'{Colors.END}")
            print(f"Path: {worktree_path}")
            print(f"Branch: {existing_worktrees[name]}")

            print(f"\n{Colors.YELLOW}Run the following commands:{Colors.END}")
            print(f"  cd {worktree_path}")
            if venv_activate.exists():
                print(f"  source .venv/bin/activate")

    def list_worktrees(self):
        """List all existing worktrees"""
        existing_worktrees = self._get_existing_worktrees()

        if not existing_worktrees:
            print(f"{Colors.YELLOW}No worktrees found{Colors.END}")
            print(f"Worktree directory: {self.worktree_base}")
            return

        print(f"{Colors.BOLD}Existing worktrees:{Colors.END}")
        print(f"Location: {self.worktree_base}\n")

        for name, branch in sorted(existing_worktrees.items()):
            worktree_path = self._get_worktree_path(name)
            status_indicator = "✓" if worktree_path.exists() else "✗"
            print(f"  {Colors.GREEN}{status_indicator}{Colors.END} {Colors.BOLD}{name}{Colors.END}")
            print(f"    Branch: {branch}")
            print(f"    Path: {worktree_path}")
            print()

    def _detect_current_worktree(self) -> Optional[tuple[str, Path]]:
        """Detect if we're currently in a worktree and return (name, path)"""
        cwd = Path.cwd()

        # Check if current directory is in a worktree
        existing_worktrees = self._get_existing_worktrees()
        for name, branch in existing_worktrees.items():
            worktree_path = self._get_worktree_path(name)
            try:
                # Check if cwd is the worktree or a subdirectory of it
                cwd.relative_to(worktree_path)
                return name, worktree_path
            except ValueError:
                continue

        return None

    def _get_docker_compose_files(self, name: Optional[str] = None) -> tuple[Optional[Path], Optional[Path], Optional[str], Optional[str]]:
        """Get Docker Compose file paths for a worktree

        If name is None, tries to detect from current directory
        Returns: (base_file, override_file, compose_dir, worktree_name)
        """
        if name is None:
            # Try to detect from current directory
            result = self._detect_current_worktree()
            if result is None:
                return None, None, None, None
            name, worktree_path = result
        else:
            worktree_path = self._get_worktree_path(name)

        # Load setup config to find compose directory
        setup_config = self._load_setup_config()
        if not setup_config or "docker_compose" not in setup_config:
            return None, None, None, None

        compose_dir = setup_config["docker_compose"].get("compose_dir", "deployment/docker_compose")
        compose_path = worktree_path / compose_dir

        if not compose_path.exists():
            return None, None, None, None

        base_file = compose_path / "docker-compose.yml"
        override_file = compose_path / f"docker-compose.worktree-{name}.yml"

        if not base_file.exists():
            return None, None, None, None

        if not override_file.exists():
            return None, None, None, None

        return base_file, override_file, str(compose_path), name

    def start_services(self, services: Optional[List[str]] = None, build: bool = False):
        """Start Docker Compose services in current worktree"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Docker Compose service management not available{Colors.END}")
            print(f"\n{Colors.BOLD}This worktree is not configured for Docker Compose service management.{Colors.END}")
            print(f"\nTo use service management commands:")
            print(f"  1. Add 'docker_compose' configuration to .worktree-setup.json")
            print(f"  2. Ensure you're running this command from within a worktree directory")
            print(f"\nSee DOCKER.md for configuration details.")
            sys.exit(1)

        # Start services with spinner
        spinner = Spinner(f"Starting services for worktree '{name}'")
        spinner.start()

        try:
            cmd = [
                "docker", "compose",
                "-f", str(base_file),
                "-f", str(override_file),
                "up", "-d"
            ]

            if build:
                cmd.append("--build")

            if services:
                cmd.extend(services)

            self._run_command(cmd, cwd=Path(compose_dir))
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Services started")
        except subprocess.CalledProcessError:
            spinner.stop()
            # Error already printed by _run_command
            sys.exit(1)
        except Exception as e:
            spinner.stop()
            raise

        # Show port information
        ports = self.metadata.get_worktree_ports(self.repo_alias, name)
        if ports:
            print(f"\n{Colors.BOLD}Service Ports:{Colors.END}")
            for svc, port in sorted(ports.items()):
                print(f"  {svc}: http://localhost:{port}")

    def stop_services(self, services: Optional[List[str]] = None, remove_volumes: bool = False):
        """Stop Docker Compose services in current worktree"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Docker Compose service management not available{Colors.END}")
            print(f"\n{Colors.BOLD}This worktree is not configured for Docker Compose service management.{Colors.END}")
            print(f"\nTo use service management commands:")
            print(f"  1. Add 'docker_compose' configuration to .worktree-setup.json")
            print(f"  2. Ensure you're running this command from within a worktree directory")
            print(f"\nSee DOCKER.md for configuration details.")
            sys.exit(1)

        # Stop services with spinner
        spinner = Spinner(f"Stopping services for worktree '{name}'")
        spinner.start()

        try:
            if services:
                # Stop specific services
                cmd = [
                    "docker", "compose",
                    "-f", str(base_file),
                    "-f", str(override_file),
                    "stop"
                ]
                cmd.extend(services)
            else:
                # Stop all services
                cmd = [
                    "docker", "compose",
                    "-f", str(base_file),
                    "-f", str(override_file),
                    "down"
                ]
                if remove_volumes:
                    cmd.append("-v")

            self._run_command(cmd, cwd=Path(compose_dir))
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Services stopped")
        except subprocess.CalledProcessError:
            spinner.stop()
            # Error already printed by _run_command
            sys.exit(1)
        except Exception as e:
            spinner.stop()
            raise

    def restart_services(self, services: Optional[List[str]] = None):
        """Restart Docker Compose services in current worktree"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Docker Compose service management not available{Colors.END}")
            print(f"\n{Colors.BOLD}This worktree is not configured for Docker Compose service management.{Colors.END}")
            print(f"\nTo use service management commands:")
            print(f"  1. Add 'docker_compose' configuration to .worktree-setup.json")
            print(f"  2. Ensure you're running this command from within a worktree directory")
            print(f"\nSee DOCKER.md for configuration details.")
            sys.exit(1)

        # Restart services with spinner
        spinner = Spinner(f"Restarting services for worktree '{name}'")
        spinner.start()

        try:
            cmd = [
                "docker", "compose",
                "-f", str(base_file),
                "-f", str(override_file),
                "restart"
            ]

            if services:
                cmd.extend(services)

            self._run_command(cmd, cwd=Path(compose_dir))
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Services restarted")
        except subprocess.CalledProcessError:
            spinner.stop()
            # Error already printed by _run_command
            sys.exit(1)
        except Exception as e:
            spinner.stop()
            raise

    def services_status(self):
        """Show status of Docker Compose services in current worktree"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Docker Compose service management not available{Colors.END}")
            print(f"\n{Colors.BOLD}This worktree is not configured for Docker Compose service management.{Colors.END}")
            print(f"\nTo use service management commands:")
            print(f"  1. Add 'docker_compose' configuration to .worktree-setup.json")
            print(f"  2. Ensure you're running this command from within a worktree directory")
            print(f"\nSee DOCKER.md for configuration details.")
            sys.exit(1)

        print(f"{Colors.BOLD}Service Status for worktree '{name}':{Colors.END}\n")

        cmd = [
            "docker", "compose",
            "-f", str(base_file),
            "-f", str(override_file),
            "ps"
        ]

        self._run_command(cmd, cwd=Path(compose_dir))

        # Show port information
        ports = self.metadata.get_worktree_ports(self.repo_alias, name)
        if ports:
            print(f"\n{Colors.BOLD}Service Ports:{Colors.END}")
            for svc, port in sorted(ports.items()):
                print(f"  {svc}: http://localhost:{port}")

    def services_logs(self, service: Optional[str] = None, follow: bool = False, tail: Optional[str] = None):
        """Show logs for Docker Compose services in current worktree"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Docker Compose service management not available{Colors.END}")
            print(f"\n{Colors.BOLD}This worktree is not configured for Docker Compose service management.{Colors.END}")
            print(f"\nTo use service management commands:")
            print(f"  1. Add 'docker_compose' configuration to .worktree-setup.json")
            print(f"  2. Ensure you're running this command from within a worktree directory")
            print(f"\nSee DOCKER.md for configuration details.")
            sys.exit(1)

        cmd = [
            "docker", "compose",
            "-f", str(base_file),
            "-f", str(override_file),
            "logs"
        ]

        if follow:
            cmd.append("-f")

        if tail:
            cmd.extend(["--tail", tail])

        if service:
            cmd.append(service)

        self._run_command(cmd, cwd=Path(compose_dir))

    def _get_worktree_env_file(self, worktree_path: Path, name: str) -> Optional[Path]:
        """Generate environment file with worktree-specific ports for Docker infrastructure and local services"""
        # Get port assignments for Docker services and port offset
        ports = self.metadata.get_worktree_ports(self.repo_alias, name)
        if not ports:
            return None

        # Get port offset from metadata to calculate local service ports
        port_offset = 0
        if self.repo_alias in self.metadata.metadata and name in self.metadata.metadata[self.repo_alias]:
            port_offset = self.metadata.metadata[self.repo_alias][name].get('port_offset', 0)

        # Calculate unique ports for local services
        backend_port = 8080 + port_offset
        model_server_port = 9000 + port_offset
        frontend_port = 3000 + port_offset

        env_file = worktree_path / ".env.worktree"

        with open(env_file, 'w') as f:
            f.write(f"# Auto-generated environment for worktree: {name}\n")
            f.write(f"# DO NOT EDIT - managed by worktree manager\n")
            f.write(f"# Port offset: {port_offset}\n\n")

            # Database configuration
            if 'relational_db' in ports:
                f.write(f"POSTGRES_HOST=localhost\n")
                f.write(f"POSTGRES_PORT={ports['relational_db']}\n")
                f.write(f"POSTGRES_USER=postgres\n")
                f.write(f"POSTGRES_PASSWORD=password\n")
                f.write(f"POSTGRES_DB=postgres\n")

            # Vespa search configuration
            if 'index' in ports:
                f.write(f"VESPA_HOST=localhost\n")
                f.write(f"VESPA_PORT={ports['index']}\n")
                f.write(f"VESPA_TENANT_PORT={ports['index']}\n")

            # Redis configuration
            if 'cache' in ports:
                f.write(f"REDIS_HOST=localhost\n")
                f.write(f"REDIS_PORT={ports['cache']}\n")

            # MinIO S3 configuration
            if 'minio' in ports:
                f.write(f"S3_ENDPOINT_URL=http://localhost:{ports['minio']}\n")
                f.write(f"S3_AWS_ACCESS_KEY_ID=minioadmin\n")
                f.write(f"S3_AWS_SECRET_ACCESS_KEY=minioadmin\n")

            # Model server configuration (running locally, not in Docker)
            f.write(f"\n# Model servers (running locally with unique ports)\n")
            f.write(f"MODEL_SERVER_HOST=localhost\n")
            f.write(f"MODEL_SERVER_PORT={model_server_port}\n")
            f.write(f"INDEXING_MODEL_SERVER_HOST=localhost\n")
            f.write(f"INDEXING_MODEL_SERVER_PORT={model_server_port}\n")

            # API server configuration (running locally with unique port)
            f.write(f"\n# API server (running locally with unique port)\n")
            f.write(f"INTERNAL_URL=http://localhost:{backend_port}\n")

            # Frontend configuration (running locally with unique port)
            f.write(f"\n# Frontend server (running locally with unique port)\n")
            f.write(f"NEXT_PUBLIC_API_URL=http://localhost:{backend_port}\n")
            f.write(f"PORT={frontend_port}\n")

        return env_file

    def dev_start(self):
        """Start all development services (Docker + Backend + Frontend)"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Development mode not available{Colors.END}")
            print(f"\n{Colors.BOLD}This worktree is not configured for development.{Colors.END}")
            sys.exit(1)

        worktree_path = self._get_worktree_path(name)

        print(f"{Colors.BOLD}Starting development environment for '{name}'...{Colors.END}\n")

        # 1. Start Docker services - only infrastructure services
        # Get the list of infrastructure services from setup config
        setup_config = self._load_setup_config()
        docker_config = setup_config.get('docker_compose', {})
        infrastructure_services = []

        # Only infrastructure services (those without skip_override flag)
        for service_name, service_config in docker_config.get('services', {}).items():
            if not service_config.get('skip_override', False):
                infrastructure_services.append(service_name)

        spinner = Spinner("Starting Docker infrastructure services")
        spinner.start()
        try:
            # Start only infrastructure services
            cmd = [
                "docker", "compose",
                "-f", str(base_file),
                "-f", str(override_file),
                "up", "-d", "--no-deps"  # --no-deps prevents starting dependent services
            ]
            cmd.extend(infrastructure_services)

            self._run_command(cmd, cwd=Path(compose_dir))
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Docker infrastructure services started")
        except subprocess.CalledProcessError:
            spinner.stop()
            sys.exit(1)

        # 2. Generate environment file and get port offset
        env_file = self._get_worktree_env_file(worktree_path, name)
        if env_file:
            self._print_success(f"Environment file generated: {env_file}")

        # Get port offset to calculate service ports
        port_offset = 0
        if self.repo_alias in self.metadata.metadata and name in self.metadata.metadata[self.repo_alias]:
            port_offset = self.metadata.metadata[self.repo_alias][name].get('port_offset', 0)

        # Calculate unique ports for local services
        backend_port = 8080 + port_offset
        model_server_port = 9000 + port_offset
        frontend_port = 3000 + port_offset

        # 3. Run database migrations
        print(f"\n{Colors.BLUE}==>{Colors.END} Running database migrations...")
        migration_cmd = f"cd {worktree_path}/backend && source ../.venv/bin/activate && set -a && source {env_file} && set +a && alembic upgrade head"
        try:
            subprocess.run(migration_cmd, shell=True, check=True, executable='/bin/bash')
            self._print_success(f"Database migrations completed")
        except subprocess.CalledProcessError as e:
            self._print_warning(f"Failed to run database migrations: {e}")
            print(f"{Colors.YELLOW}You may need to run migrations manually{Colors.END}")

        # 4. Start model server in background
        print(f"\n{Colors.BLUE}==>{Colors.END} Starting model server...")
        model_server_log = worktree_path / ".model-server.log"
        # Use a wrapper script to properly capture the PID
        model_server_cmd = f"""cd {worktree_path}/backend && source ../.venv/bin/activate && set -a && source {env_file} && set +a && {{
            uvicorn model_server.main:app --reload --port {model_server_port} > {model_server_log} 2>&1 &
            echo $! > {worktree_path}/.model-server.pid
        }}"""

        try:
            subprocess.run(model_server_cmd, shell=True, check=True, executable='/bin/bash')
            self._print_success(f"Model server started (logs: {model_server_log})")
        except subprocess.CalledProcessError as e:
            self._print_warning(f"Failed to start model server: {e}")

        # 5. Start backend API server in background
        print(f"{Colors.BLUE}==>{Colors.END} Starting backend API server...")
        backend_log = worktree_path / ".backend.log"
        backend_cmd = f"""cd {worktree_path}/backend && source ../.venv/bin/activate && set -a && source {env_file} && set +a && {{
            uvicorn onyx.main:app --reload --port {backend_port} > {backend_log} 2>&1 &
            echo $! > {worktree_path}/.backend.pid
        }}"""

        try:
            subprocess.run(backend_cmd, shell=True, check=True, executable='/bin/bash')
            self._print_success(f"Backend started (logs: {backend_log})")
        except subprocess.CalledProcessError as e:
            self._print_warning(f"Failed to start backend: {e}")

        # 6. Start Celery workers
        celery_workers = [
            ("primary", "celery", "--pool=threads --concurrency=4 --prefetch-multiplier=1"),
            ("light", "vespa_metadata_sync,connector_deletion,doc_permissions_upsert,index_attempt_cleanup", "--pool=threads --concurrency=64 --prefetch-multiplier=8"),
            ("heavy", "connector_pruning,connector_doc_permissions_sync,connector_external_group_sync", "--pool=threads --concurrency=4 --prefetch-multiplier=1"),
            ("docfetching", "connector_doc_fetching,user_files_indexing", "--pool=threads --concurrency=1 --prefetch-multiplier=1"),
            ("docprocessing", "docprocessing", "--pool=threads --concurrency=6 --prefetch-multiplier=1"),
            ("monitoring", "monitoring", "--pool=solo --concurrency=1 --prefetch-multiplier=1"),
            ("user_file_processing", "user_file_processing,user_file_project_sync", "--pool=threads"),
        ]

        print(f"{Colors.BLUE}==>{Colors.END} Starting Celery workers...")
        for worker_name, queues, pool_args in celery_workers:
            log_file = worktree_path / f".celery-{worker_name}.log"
            celery_cmd = f"""cd {worktree_path}/backend && source ../.venv/bin/activate && set -a && source {env_file} && set +a && {{
                celery -A onyx.background.celery.versioned_apps.{worker_name} worker --loglevel=INFO --hostname={worker_name}@%n -Q {queues} {pool_args} > {log_file} 2>&1 &
                echo $! > {worktree_path}/.celery-{worker_name}.pid
            }}"""

            try:
                subprocess.run(celery_cmd, shell=True, check=True, executable='/bin/bash')
            except subprocess.CalledProcessError as e:
                self._print_warning(f"Failed to start Celery worker {worker_name}: {e}")

        # Start Celery beat
        beat_log = worktree_path / ".celery-beat.log"
        beat_cmd = f"""cd {worktree_path}/backend && source ../.venv/bin/activate && set -a && source {env_file} && set +a && {{
            celery -A onyx.background.celery.versioned_apps.beat beat --loglevel=INFO > {beat_log} 2>&1 &
            echo $! > {worktree_path}/.celery-beat.pid
        }}"""

        try:
            subprocess.run(beat_cmd, shell=True, check=True, executable='/bin/bash')
            self._print_success(f"Celery workers started")
        except subprocess.CalledProcessError as e:
            self._print_warning(f"Failed to start Celery beat: {e}")

        # 7. Start frontend server in background
        print(f"{Colors.BLUE}==>{Colors.END} Starting frontend web server...")
        frontend_log = worktree_path / ".frontend.log"
        # Frontend will pick up env vars from both .vscode/.env and .env.worktree
        # Use grep to filter out lines with <REPLACE and then source
        vscode_env = worktree_path / ".vscode/.env"
        frontend_cmd = f"""cd {worktree_path}/web && set -a && grep -v '<REPLACE' {vscode_env} | grep -v '^#' | grep -v '^$' | while IFS= read -r line; do export \"$line\"; done && source {env_file} && set +a && {{
            npm run dev > {frontend_log} 2>&1 &
            echo $! > {worktree_path}/.frontend.pid
        }}"""

        try:
            subprocess.run(frontend_cmd, shell=True, check=True, executable='/bin/bash')
            self._print_success(f"Frontend started (logs: {frontend_log})")
        except subprocess.CalledProcessError as e:
            self._print_warning(f"Failed to start frontend: {e}")

        time.sleep(3)  # Give services a moment to start

        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Full development environment ready!{Colors.END}")
        print(f"\n{Colors.BOLD}Access your application:{Colors.END}")
        print(f"  Frontend:     http://localhost:{frontend_port}")
        print(f"  Backend API:  http://localhost:{backend_port}")
        print(f"  Model Server: http://localhost:{model_server_port}")

        ports = self.metadata.get_worktree_ports(self.repo_alias, name)
        if ports:
            print(f"\n{Colors.BOLD}Infrastructure ports:{Colors.END}")
            for svc, port in sorted(ports.items()):
                print(f"  {svc}: {port}")

        print(f"\n{Colors.BOLD}Running services:{Colors.END}")
        print(f"  - Backend API Server (uvicorn with hot reload)")
        print(f"  - Model Server (uvicorn with hot reload)")
        print(f"  - Frontend (Next.js dev server with hot reload)")
        print(f"  - 7 Celery workers (primary, light, heavy, docfetching, docprocessing, monitoring, user_file_processing)")
        print(f"  - Celery Beat scheduler")

        print(f"\n{Colors.BOLD}View logs:{Colors.END}")
        print(f"  Backend:        tail -f {backend_log}")
        print(f"  Model Server:   tail -f {model_server_log}")
        print(f"  Frontend:       tail -f {frontend_log}")
        print(f"  Celery Primary: tail -f {worktree_path}/.celery-primary.log")
        print(f"  All Celery:     tail -f {worktree_path}/.celery-*.log")

        print(f"\n{Colors.BOLD}Manage:{Colors.END}")
        print(f"  Check status: worktree {self.repo_alias} dev status")
        print(f"  Stop all:     worktree {self.repo_alias} dev stop")
        print(f"  Restart all:  worktree {self.repo_alias} dev restart")

    def dev_stop(self):
        """Stop all development services"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Development mode not available{Colors.END}")
            sys.exit(1)

        worktree_path = self._get_worktree_path(name)

        print(f"{Colors.BOLD}Stopping development environment for '{name}'...{Colors.END}\n")

        # Define services with their PID files and process search patterns
        services_to_stop = [
            ("Frontend", ".frontend.pid", f"npm.*{worktree_path}/web"),
            ("Backend API", ".backend.pid", f"uvicorn onyx.main.*{worktree_path}/backend"),
            ("Model Server", ".model-server.pid", f"uvicorn model_server.main.*{worktree_path}/backend"),
            ("Celery Primary", ".celery-primary.pid", f"celery.*primary.*{worktree_path}/backend"),
            ("Celery Light", ".celery-light.pid", f"celery.*light.*{worktree_path}/backend"),
            ("Celery Heavy", ".celery-heavy.pid", f"celery.*heavy.*{worktree_path}/backend"),
            ("Celery Docfetching", ".celery-docfetching.pid", f"celery.*docfetching.*{worktree_path}/backend"),
            ("Celery Docprocessing", ".celery-docprocessing.pid", f"celery.*docprocessing.*{worktree_path}/backend"),
            ("Celery Monitoring", ".celery-monitoring.pid", f"celery.*monitoring.*{worktree_path}/backend"),
            ("Celery User File Processing", ".celery-user_file_processing.pid", f"celery.*user_file_processing.*{worktree_path}/backend"),
            ("Celery Beat", ".celery-beat.pid", f"celery.*beat.*{worktree_path}/backend"),
        ]

        # First pass: try to kill by PID file
        pids_to_check = []
        for service_name, pid_file_name, pattern in services_to_stop:
            pid_file = worktree_path / pid_file_name
            if pid_file.exists():
                try:
                    with open(pid_file, 'r') as f:
                        pid = f.read().strip()
                    if pid:
                        # Verify PID is still running before killing
                        result = subprocess.run(f"ps -p {pid}", shell=True, capture_output=True)
                        if result.returncode == 0:
                            subprocess.run(f"kill {pid}", shell=True, check=False)
                            pids_to_check.append(pid)
                except Exception:
                    pass

        # Give processes time to shut down gracefully
        time.sleep(2)

        # Second pass: find and kill by process pattern (handles cases where PID file is stale)
        for service_name, pid_file_name, pattern in services_to_stop:
            try:
                # Find processes matching the pattern
                result = subprocess.run(
                    f"pgrep -f '{pattern}'",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        subprocess.run(f"kill {pid}", shell=True, check=False)
            except Exception:
                pass

        # Give processes another moment
        time.sleep(2)

        # Third pass: force kill any remaining processes
        for service_name, pid_file_name, pattern in services_to_stop:
            try:
                result = subprocess.run(
                    f"pgrep -f '{pattern}'",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        subprocess.run(f"kill -9 {pid}", shell=True, check=False)
            except Exception:
                pass

        # Clean up PID files
        for service_name, pid_file_name, pattern in services_to_stop:
            pid_file = worktree_path / pid_file_name
            if pid_file.exists():
                try:
                    pid_file.unlink()
                except Exception:
                    pass

        # Extra sleep to ensure ports are released
        time.sleep(1)

        self._print_success("All application services stopped")

        # 3. Stop Docker services
        spinner = Spinner("Stopping Docker services")
        spinner.start()
        try:
            cmd = [
                "docker", "compose",
                "-f", str(base_file),
                "-f", str(override_file),
                "down"
            ]
            self._run_command(cmd, cwd=Path(compose_dir))
            spinner.stop(f"{Colors.GREEN}✓{Colors.END} Docker services stopped")
        except subprocess.CalledProcessError:
            spinner.stop()

        print(f"\n{Colors.GREEN}✓ Development environment stopped{Colors.END}")

    def dev_restart(self):
        """Restart all development services"""
        self.dev_stop()
        time.sleep(1)
        self.dev_start()

    def dev_status(self):
        """Show status of all development services"""
        base_file, override_file, compose_dir, name = self._get_docker_compose_files()

        if not base_file or not override_file or not name:
            print(f"{Colors.RED}Error: Development mode not available{Colors.END}")
            sys.exit(1)

        worktree_path = self._get_worktree_path(name)

        print(f"{Colors.BOLD}Development Environment Status for '{name}':{Colors.END}\n")

        # Check all services
        services_to_check = [
            ("Frontend", ".frontend.pid"),
            ("Backend API", ".backend.pid"),
            ("Model Server", ".model-server.pid"),
            ("Celery Primary", ".celery-primary.pid"),
            ("Celery Light", ".celery-light.pid"),
            ("Celery Heavy", ".celery-heavy.pid"),
            ("Celery Docfetching", ".celery-docfetching.pid"),
            ("Celery Docprocessing", ".celery-docprocessing.pid"),
            ("Celery Monitoring", ".celery-monitoring.pid"),
            ("Celery User File Processing", ".celery-user_file_processing.pid"),
            ("Celery Beat", ".celery-beat.pid"),
        ]

        print(f"{Colors.BOLD}Application Services:{Colors.END}\n")
        for service_name, pid_file_name in services_to_check:
            pid_file = worktree_path / pid_file_name
            if pid_file.exists():
                try:
                    with open(pid_file, 'r') as f:
                        pid = f.read().strip()
                    result = subprocess.run(f"ps -p {pid}", shell=True, capture_output=True)
                    if result.returncode == 0:
                        print(f"{Colors.GREEN}✓{Colors.END} {service_name} (PID {pid})")
                    else:
                        print(f"{Colors.RED}✗{Colors.END} {service_name} (not running)")
                except Exception:
                    print(f"{Colors.RED}✗{Colors.END} {service_name} (error)")
            else:
                print(f"{Colors.YELLOW}○{Colors.END} {service_name} (not started)")

        # Check Docker services
        print(f"\n{Colors.BOLD}Docker Services:{Colors.END}\n")
        cmd = [
            "docker", "compose",
            "-f", str(base_file),
            "-f", str(override_file),
            "ps"
        ]
        self._run_command(cmd, cwd=Path(compose_dir))

        # Show port information
        ports = self.metadata.get_worktree_ports(self.repo_alias, name)
        if ports:
            print(f"\n{Colors.BOLD}Service Ports:{Colors.END}")
            for svc, port in sorted(ports.items()):
                print(f"  {svc}: {port}")


def run_tests():
    """Run the test suite in an isolated virtual environment"""
    script_dir = Path(__file__).parent
    test_venv = script_dir / ".test-venv"
    test_dir = script_dir / "tests"

    if not test_dir.exists():
        print(f"{Colors.RED}Error: Tests directory not found at {test_dir}{Colors.END}")
        sys.exit(1)

    # Create test virtual environment if it doesn't exist
    if not test_venv.exists():
        print(f"{Colors.BLUE}==>{Colors.END} Creating test virtual environment...")
        try:
            subprocess.run(
                ["python3", "-m", "venv", str(test_venv)],
                check=True
            )
            print(f"{Colors.GREEN}✓{Colors.END} Test venv created")
        except subprocess.CalledProcessError as e:
            print(f"{Colors.RED}Failed to create test venv{Colors.END}")
            sys.exit(1)

        # Install test dependencies
        print(f"{Colors.BLUE}==>{Colors.END} Installing test dependencies...")
        pip_path = test_venv / "bin" / "pip"
        requirements_path = script_dir / "test-requirements.txt"

        if not requirements_path.exists():
            print(f"{Colors.RED}Error: test-requirements.txt not found{Colors.END}")
            sys.exit(1)

        try:
            subprocess.run(
                [str(pip_path), "install", "-q", "--upgrade", "pip"],
                check=True
            )
            subprocess.run(
                [str(pip_path), "install", "-q", "-r", str(requirements_path)],
                check=True
            )
            print(f"{Colors.GREEN}✓{Colors.END} Dependencies installed")
        except subprocess.CalledProcessError:
            print(f"{Colors.RED}Failed to install test dependencies{Colors.END}")
            sys.exit(1)

    # Run tests
    print(f"\n{Colors.BOLD}Running tests...{Colors.END}\n")
    pytest_path = test_venv / "bin" / "pytest"

    # Pass through any additional arguments to pytest
    extra_args = sys.argv[2:] if len(sys.argv) > 2 else []

    try:
        result = subprocess.run(
            [str(pytest_path), "-v"] + extra_args + [str(test_dir)],
            cwd=script_dir
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted{Colors.END}")
        sys.exit(130)


def run_e2e_test():
    """Run end-to-end integration test"""
    script_dir = Path(__file__).parent
    e2e_script = script_dir / "e2e-test.sh"

    if not e2e_script.exists():
        print(f"{Colors.RED}Error: E2E test script not found at {e2e_script}{Colors.END}")
        sys.exit(1)

    # Get repository alias from command line (after 'test-e2e')
    repo_alias = sys.argv[2] if len(sys.argv) > 2 else None

    if not repo_alias:
        print(f"{Colors.BOLD}Running end-to-end integration test{Colors.END}\n")
        print(f"{Colors.YELLOW}Usage: worktree test-e2e <repo-alias>{Colors.END}")
        print(f"\nExample: worktree test-e2e onyx\n")

        # Show available repositories
        config = RepoConfig()
        if config.repos:
            print(f"{Colors.BOLD}Available repositories:{Colors.END}")
            for alias, path in config.repos.items():
                print(f"  {alias} → {path}")
        else:
            print(f"{Colors.YELLOW}No repositories configured yet.{Colors.END}")
            print(f"Add one with: worktree repo add <alias> <path>")
        sys.exit(1)

    try:
        result = subprocess.run(
            [str(e2e_script), repo_alias],
            cwd=script_dir
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}E2E test interrupted{Colors.END}")
        sys.exit(130)


def main():
    # Check for special commands first
    if len(sys.argv) > 1:
        if sys.argv[1] == "run-tests":
            run_tests()
            return
        elif sys.argv[1] == "test-e2e":
            run_e2e_test()
            return

    # Check if first argument is a repository alias before argparse
    config = RepoConfig()

    if len(sys.argv) > 1 and sys.argv[1] != "repo" and sys.argv[1] in config.repos:
        # This is a repository alias command
        repo_alias = sys.argv[1]
        repo_path = config.get_repo_path(repo_alias)

        if not repo_path.exists():
            print(f"{Colors.RED}Error: Repository path no longer exists: {repo_path}{Colors.END}")
            sys.exit(1)

        # Parse the worktree command
        wt_parser = argparse.ArgumentParser(
            prog=f"worktree {repo_alias}",
            description=f"Manage worktrees for '{repo_alias}' repository"
        )
        wt_subparsers = wt_parser.add_subparsers(dest="wt_command")

        # New command
        new_parser = wt_subparsers.add_parser("new", help="Create a new worktree")
        new_parser.add_argument("name", help="Name for the new worktree")
        new_parser.add_argument("--base", default="origin/main", help="Base branch (default: origin/main)")
        new_parser.add_argument("--skip-setup", action="store_true", help="Skip setup steps")
        new_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output from setup steps")
        new_parser.add_argument("--restore-db", metavar="DUMP_FILE", help="Restore database from dump file during creation")
        new_parser.add_argument("--copy-db-from-main", action="store_true", help="Copy database from main installation during creation")
        new_parser.add_argument("--shell-mode", action="store_true", help=argparse.SUPPRESS)  # Hidden flag for shell wrapper

        # Remove command
        rm_parser = wt_subparsers.add_parser("rm", help="Remove a worktree")
        rm_parser.add_argument("name", help="Name of the worktree to remove")
        rm_parser.add_argument("--force", "-f", action="store_true", help="Force removal without confirmation")

        # Select command
        select_parser = wt_subparsers.add_parser("select", help="Switch to a worktree")
        select_parser.add_argument("name", help="Name of the worktree to switch to")
        select_parser.add_argument("--shell-mode", action="store_true", help=argparse.SUPPRESS)  # Hidden flag for shell wrapper

        # List command
        wt_subparsers.add_parser("list", help="List all worktrees")

        # Dev command (simplified development workflow)
        dev_parser = wt_subparsers.add_parser("dev", help="Development commands (run from worktree directory)")
        dev_subparsers = dev_parser.add_subparsers(dest="dev_command")
        dev_subparsers.add_parser("start", help="Start all services (Docker + Backend + Frontend)")
        dev_subparsers.add_parser("stop", help="Stop all services")
        dev_subparsers.add_parser("restart", help="Restart all services")
        dev_status_parser = dev_subparsers.add_parser("status", help="Show status of all services")

        # Services command
        services_parser = wt_subparsers.add_parser("services", help="Manage Docker Compose services (run from worktree directory)")
        services_subparsers = services_parser.add_subparsers(dest="services_command")

        # Start services
        start_parser = services_subparsers.add_parser("start", help="Start services")
        start_parser.add_argument("--services", "--svcs", nargs="+", help="Start specific services")
        start_parser.add_argument("--build", action="store_true", help="Build images before starting")

        # Stop services
        stop_parser = services_subparsers.add_parser("stop", help="Stop services")
        stop_parser.add_argument("--services", "--svcs", nargs="+", help="Stop specific services")
        stop_parser.add_argument("--volumes", "-v", action="store_true", help="Remove volumes (WARNING: deletes all data)")

        # Restart services
        restart_parser = services_subparsers.add_parser("restart", help="Restart services")
        restart_parser.add_argument("--services", "--svcs", nargs="+", help="Restart specific services")

        # Status of services
        services_subparsers.add_parser("status", help="Show service status")

        # Logs command
        logs_parser = services_subparsers.add_parser("logs", help="View service logs")
        logs_parser.add_argument("service", nargs="?", help="Specific service to view logs for")
        logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output")
        logs_parser.add_argument("--tail", help="Number of lines to show from end of logs")

        # Database commands
        db_parser = wt_subparsers.add_parser("db", help="Database management commands")
        db_subparsers = db_parser.add_subparsers(dest="db_command")

        # Dump database
        dump_parser = db_subparsers.add_parser("dump", help="Create database dump")
        dump_parser.add_argument("worktree", nargs="?", help="Worktree name (omit for main installation)")
        dump_parser.add_argument("-o", "--output", help="Output file path")

        # Restore database
        restore_parser = db_subparsers.add_parser("restore", help="Restore database from dump")
        restore_parser.add_argument("worktree", help="Worktree name to restore to")
        restore_parser.add_argument("dump_file", help="Dump file to restore from")

        # List dumps
        db_subparsers.add_parser("list-dumps", help="List available database dumps")

        # Database shell
        shell_parser = db_subparsers.add_parser("shell", help="Connect to worktree's PostgreSQL")
        shell_parser.add_argument("worktree", nargs="?", help="Worktree name (omit for main installation)")

        # Instances command
        wt_subparsers.add_parser("instances", help="Show all running worktree instances with ports")

        wt_args = wt_parser.parse_args(sys.argv[2:])

        if not wt_args.wt_command:
            wt_parser.print_help()
            sys.exit(1)

        manager = WorktreeManager(repo_path, repo_alias)

        if wt_args.wt_command == "new":
            manager.create_worktree(
                wt_args.name,
                wt_args.base,
                wt_args.skip_setup,
                wt_args.verbose,
                getattr(wt_args, 'shell_mode', False),
                restore_db=wt_args.restore_db,
                copy_db_from_main=wt_args.copy_db_from_main
            )
        elif wt_args.wt_command == "rm":
            manager.remove_worktree(wt_args.name, wt_args.force)
        elif wt_args.wt_command == "select":
            manager.select_worktree(wt_args.name, getattr(wt_args, 'shell_mode', False))
        elif wt_args.wt_command == "list":
            manager.list_worktrees()
        elif wt_args.wt_command == "dev":
            if wt_args.dev_command == "start":
                manager.dev_start()
            elif wt_args.dev_command == "stop":
                manager.dev_stop()
            elif wt_args.dev_command == "restart":
                manager.dev_restart()
            elif wt_args.dev_command == "status":
                manager.dev_status()
            else:
                dev_parser.print_help()
        elif wt_args.wt_command == "services":
            if wt_args.services_command == "start":
                manager.start_services(wt_args.services, wt_args.build)
            elif wt_args.services_command == "stop":
                manager.stop_services(wt_args.services, wt_args.volumes)
            elif wt_args.services_command == "restart":
                manager.restart_services(wt_args.services)
            elif wt_args.services_command == "status":
                manager.services_status()
            elif wt_args.services_command == "logs":
                manager.services_logs(wt_args.service, wt_args.follow, wt_args.tail)
            else:
                services_parser.print_help()
        elif wt_args.wt_command == "db":
            if wt_args.db_command == "dump":
                try:
                    output_file = Path(wt_args.output).expanduser() if wt_args.output else None
                    dump_file = manager.db_manager.dump_database(wt_args.worktree, output_file)
                    print(f"\n{Colors.GREEN}✓ Dump created successfully{Colors.END}")
                    info = manager.db_manager.get_dump_info(dump_file)
                    print(f"  Size: {info['size']}")
                    print(f"  Path: {info['path']}")
                except Exception as e:
                    print(f"{Colors.RED}Error: {e}{Colors.END}")
                    sys.exit(1)
            elif wt_args.db_command == "restore":
                try:
                    dump_path = Path(wt_args.dump_file).expanduser()
                    if not dump_path.is_absolute():
                        # Try to find it in dumps directory
                        dumps_dir_file = manager.db_manager.dumps_dir / wt_args.dump_file
                        if dumps_dir_file.exists():
                            dump_path = dumps_dir_file
                    manager.db_manager.restore_database(wt_args.worktree, dump_path)
                    print(f"\n{Colors.GREEN}✓ Database restored successfully{Colors.END}")
                except Exception as e:
                    print(f"{Colors.RED}Error: {e}{Colors.END}")
                    sys.exit(1)
            elif wt_args.db_command == "list-dumps":
                dumps = manager.db_manager.list_dumps()
                if not dumps:
                    print(f"{Colors.YELLOW}No database dumps found{Colors.END}")
                    print(f"Dumps directory: {manager.db_manager.dumps_dir}")
                else:
                    print(f"{Colors.BOLD}Available database dumps:{Colors.END}")
                    print(f"Location: {manager.db_manager.dumps_dir}\n")
                    for dump_file in dumps:
                        info = manager.db_manager.get_dump_info(dump_file)
                        print(f"  {Colors.BOLD}{info['name']}{Colors.END}")
                        print(f"    Size: {info['size']}")
                        print(f"    Modified: {info['modified']}")
                        print()
            elif wt_args.db_command == "shell":
                container_name = manager.db_manager._get_container_name(wt_args.worktree)
                if not container_name:
                    if wt_args.worktree:
                        print(f"{Colors.RED}Error: Container for worktree '{wt_args.worktree}' not found{Colors.END}")
                    else:
                        print(f"{Colors.RED}Error: No main postgres container found{Colors.END}")
                    sys.exit(1)

                print(f"{Colors.GREEN}Connecting to PostgreSQL in '{wt_args.worktree or 'main'}'...{Colors.END}")
                try:
                    subprocess.run(
                        f"docker exec -it {container_name} psql -U postgres postgres",
                        shell=True
                    )
                except KeyboardInterrupt:
                    print(f"\n{Colors.YELLOW}Connection closed{Colors.END}")
            else:
                db_parser.print_help()
        elif wt_args.wt_command == "instances":
            # Show all worktree instances with their ports
            all_worktrees = manager.metadata.list_all_worktrees(repo_alias)

            if not all_worktrees or repo_alias not in all_worktrees or not all_worktrees[repo_alias]:
                print(f"{Colors.YELLOW}No worktree instances found for '{repo_alias}'{Colors.END}")
            else:
                print(f"{Colors.BOLD}Running worktree instances for '{repo_alias}':{Colors.END}\n")

                for worktree_name, worktree_data in sorted(all_worktrees[repo_alias].items()):
                    port_offset = worktree_data.get('port_offset', 0)
                    ports = worktree_data.get('ports', {})
                    created = worktree_data.get('created', 'Unknown')

                    # Check if containers are actually running
                    containers_running = []
                    for service_name in ports.keys():
                        container_name = f"{service_name}-{worktree_name}"
                        result = subprocess.run(
                            f"docker ps --filter 'name={container_name}' --format '{{{{.Names}}}}'",
                            shell=True,
                            capture_output=True,
                            text=True
                        )
                        if container_name in result.stdout:
                            containers_running.append(service_name)

                    status_icon = f"{Colors.GREEN}●{Colors.END}" if containers_running else f"{Colors.DIM}○{Colors.END}"
                    print(f"  {status_icon} {Colors.BOLD}{worktree_name}{Colors.END}")
                    print(f"    Port offset: {port_offset}")
                    print(f"    Created: {created}")

                    if containers_running:
                        print(f"    Running services:")
                        for service_name in containers_running:
                            port = ports.get(service_name, 'N/A')
                            print(f"      - {service_name}: http://localhost:{port}")
                    else:
                        print(f"    {Colors.DIM}(No services running){Colors.END}")

                    if ports:
                        print(f"    All configured ports:")
                        for service_name, port in sorted(ports.items()):
                            running_mark = "✓" if service_name in containers_running else " "
                            print(f"      {running_mark} {service_name}: {port}")

                    print()
        return

    # Regular argparse for repo management
    parser = argparse.ArgumentParser(
        description="Git Worktree Manager - Manage worktrees across multiple repositories from anywhere",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Configure repositories
  worktree repo add onyx ~/onyx
  worktree repo add myapp ~/projects/myapp
  worktree repo list

  # Manage worktrees from anywhere
  worktree onyx new feature-xyz           Create worktree in onyx repo
  worktree onyx list                      List onyx worktrees
  worktree myapp new hotfix               Create worktree in myapp repo
  worktree myapp select hotfix            Switch to myapp hotfix worktree
  worktree onyx rm feature-xyz            Remove onyx worktree

  # Run tests
  worktree run-tests                      Run the test suite
  worktree run-tests -k test_name         Run specific tests
  worktree test-e2e <alias>               Run end-to-end integration test
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Repo management commands
    repo_parser = subparsers.add_parser("repo", help="Manage repository aliases")
    repo_subparsers = repo_parser.add_subparsers(dest="repo_command")

    repo_add = repo_subparsers.add_parser("add", help="Add a repository alias")
    repo_add.add_argument("alias", help="Alias name for the repository")
    repo_add.add_argument("path", help="Path to the git repository")

    repo_rm = repo_subparsers.add_parser("rm", help="Remove a repository alias")
    repo_rm.add_argument("alias", help="Alias to remove")

    repo_list = repo_subparsers.add_parser("list", help="List all repository aliases")

    args = parser.parse_args()

    # Handle repo management commands
    if args.command == "repo":
        if args.repo_command == "add":
            config.add_repo(args.alias, args.path)
        elif args.repo_command == "rm":
            config.remove_repo(args.alias)
        elif args.repo_command == "list":
            config.list_repos()
        else:
            repo_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
