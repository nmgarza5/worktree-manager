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
from pathlib import Path
from typing import Dict, List, Optional, Any


class Colors:
    """ANSI color codes for terminal output"""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


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

    def get_next_port_offset(self, repo_alias: str) -> int:
        """Get the next available port offset for a repository"""
        if repo_alias not in self.metadata:
            return 0

        used_offsets = [
            wt_data.get('port_offset', 0)
            for wt_data in self.metadata[repo_alias].values()
        ]

        if not used_offsets:
            return 0

        # Find next available offset (increment by 10)
        next_offset = 0
        while next_offset in used_offsets:
            next_offset += 10

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
            print(f"{self.colors.RED}Command failed: {cmd if isinstance(cmd, str) else ' '.join(cmd)}{self.colors.END}")
            if e.stderr:
                print(f"{self.colors.RED}{e.stderr}{self.colors.END}")
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

    def execute_step(self, step: Dict[str, Any]):
        """Execute a single setup step"""
        step_type = step.get("type")
        step_name = step.get("name", step_type)

        self._print_step(step_name)

        if step_type == "python_venv":
            self._setup_python_venv()
        elif step_type == "pip_install":
            self._pip_install(step.get("requirements", []))
        elif step_type == "pip_install_editable":
            self._pip_install_editable(step.get("path", "."))
        elif step_type == "pip_install_package":
            self._pip_install_package(step.get("package"))
        elif step_type == "playwright_install":
            self._playwright_install()
        elif step_type == "precommit_install":
            self._precommit_install(step.get("path", "."))
        elif step_type == "npm_install":
            self._npm_install(step.get("path", "."))
        elif step_type == "command":
            self._run_custom_command(step.get("command"), step.get("cwd"))
        elif step_type == "docker_compose_override":
            # This will be handled externally by WorktreeManager
            return
        else:
            print(f"{self.colors.YELLOW}⚠ Unknown step type: {step_type}{self.colors.END}")
            return

        self._print_success(f"{step_name} complete")

    def _setup_python_venv(self):
        """Create Python virtual environment"""
        self._run_command(["python3", "-m", "venv", str(self.venv_path)])

    def _pip_install(self, requirements: List[str]):
        """Install Python packages from requirements files"""
        pip_path = self._get_pip_path()
        for req_file in requirements:
            req_path = self.worktree_path / req_file
            if req_path.exists():
                print(f"  Installing from {req_file}...")
                self._run_command([str(pip_path), "install", "-r", str(req_path)])
            else:
                print(f"{self.colors.YELLOW}  Skipping {req_file} (not found){self.colors.END}")

    def _pip_install_editable(self, path: str):
        """Install package in editable mode"""
        pip_path = self._get_pip_path()
        install_path = self.worktree_path / path
        self._run_command([str(pip_path), "install", "-e", str(install_path)])

    def _pip_install_package(self, package: str):
        """Install a single Python package"""
        pip_path = self._get_pip_path()
        self._run_command([str(pip_path), "install", package])

    def _playwright_install(self):
        """Install Playwright browsers"""
        playwright_path = self._get_executable_path("playwright")
        self._run_command([str(playwright_path), "install"])

    def _precommit_install(self, path: str):
        """Install pre-commit hooks"""
        precommit_path = self._get_executable_path("pre-commit")
        install_path = self.worktree_path / path
        self._run_command([str(precommit_path), "install"], cwd=install_path)

    def _npm_install(self, path: str):
        """Install Node dependencies"""
        install_path = self.worktree_path / path
        if install_path.exists():
            self._run_command(["npm", "install"], cwd=install_path)
        else:
            print(f"{self.colors.YELLOW}  Skipping npm install (path not found: {path}){self.colors.END}")

    def _run_custom_command(self, command: str, cwd: Optional[str] = None):
        """Run a custom shell command"""
        work_dir = self.worktree_path / cwd if cwd else self.worktree_path
        self._run_command([command], cwd=work_dir, shell=True)

    def _generate_docker_compose_override(self, worktree_name: str, port_offset: int, config: Dict[str, Any]):
        """Generate Docker Compose override file for worktree"""
        services_config = config.get('services', {})
        compose_dir = config.get('compose_dir', 'deployment/docker_compose')

        compose_path = self.worktree_path / compose_dir
        if not compose_path.exists():
            print(f"{self.colors.YELLOW}  Docker compose directory not found: {compose_path}{self.colors.END}")
            return None

        # Calculate ports for each service
        ports_map = {}
        services_override = {}

        for service_name, service_config in services_config.items():
            internal_port = service_config.get('internal')
            if internal_port:
                external_port = internal_port + port_offset
                ports_map[service_name] = external_port

                # Build service override
                service_override = {
                    'container_name': f"{service_name}-{worktree_name}",
                    'ports': [f"{external_port}:{internal_port}"]
                }

                # Add environment overrides if specified
                env_overrides = service_config.get('environment', {})
                if env_overrides:
                    service_override['environment'] = env_overrides

                # Handle volume renaming for data isolation
                if service_name in ['relational_db', 'cache', 'index', 'minio']:
                    volumes = service_config.get('volumes', [])
                    renamed_volumes = []
                    for vol in volumes:
                        if ':' in vol:
                            vol_name, mount_point = vol.split(':', 1)
                            renamed_vol_name = f"{vol_name}-{worktree_name}"
                            renamed_volumes.append(f"{renamed_vol_name}:{mount_point}")
                        else:
                            renamed_volumes.append(vol)
                    if renamed_volumes:
                        service_override['volumes'] = renamed_volumes

                services_override[service_name] = service_override

        # Create the override file content
        override_content = {
            'name': f'onyx-{worktree_name}',
            'services': services_override
        }

        # Add volume definitions for renamed volumes
        volumes_def = {}
        for service_name, service_config in services_config.items():
            if service_name in ['relational_db', 'cache', 'index', 'minio']:
                volumes = service_config.get('volumes', [])
                for vol in volumes:
                    if ':' in vol:
                        vol_name = vol.split(':', 1)[0]
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

    def _load_setup_config(self) -> Optional[Dict]:
        """Load setup configuration if it exists"""
        possible_configs = [
            self.main_repo / ".worktree-setup.json",
            Path.home() / ".worktree-setup.json",
        ]

        for config_path in possible_configs:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        return json.load(f)
                except json.JSONDecodeError as e:
                    print(f"{Colors.YELLOW}⚠ Warning: Invalid JSON in {config_path}: {e}{Colors.END}")
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

    def create_worktree(self, name: str, base_branch: str = "origin/main", skip_setup: bool = False):
        """Create a new worktree with optional environment setup"""
        worktree_path = self._get_worktree_path(name)

        if worktree_path.exists():
            print(f"{Colors.RED}Error: Worktree '{name}' already exists at {worktree_path}{Colors.END}")
            sys.exit(1)

        self.worktree_base.mkdir(exist_ok=True)

        self._print_step(f"Creating worktree '{name}' from {base_branch}")
        self._run_command([
            "git", "worktree", "add", "-b", name, str(worktree_path), base_branch
        ])
        self._print_success(f"Worktree created at {worktree_path}")

        # Handle Docker Compose configuration if present
        docker_config = None
        ports_map = None

        if not skip_setup:
            setup_config = self._load_setup_config()

            # Check for Docker Compose configuration
            if setup_config and "docker_compose" in setup_config:
                docker_config = setup_config["docker_compose"]
                port_offset = self.metadata.get_next_port_offset(self.repo_alias)

                self._print_step("Generating Docker Compose override")
                executor = SetupExecutor(worktree_path, Colors)
                ports_map = executor._generate_docker_compose_override(name, port_offset, docker_config)

                if ports_map:
                    self._print_success("Docker Compose override generated")
                    # Save metadata
                    self.metadata.add_worktree(self.repo_alias, name, port_offset, ports_map)

            # Run other setup steps
            if setup_config and "setup_steps" in setup_config:
                print(f"\n{Colors.BOLD}Running setup steps...{Colors.END}\n")
                executor = SetupExecutor(worktree_path, Colors)

                for step in setup_config["setup_steps"]:
                    try:
                        executor.execute_step(step)
                    except Exception as e:
                        self._print_warning(f"Setup step failed: {step.get('name', step.get('type'))} - {str(e)}")
                        print(f"{Colors.YELLOW}Continuing with remaining steps...{Colors.END}")

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

        self._print_step(f"Removing worktree '{name}'")
        force_flag = ["--force"] if force else []
        self._run_command(["git", "worktree", "remove", *force_flag, str(worktree_path)])
        self._print_success(f"Worktree removed: {worktree_path}")

        branch_name = existing_worktrees[name]
        if branch_name != 'detached':
            try:
                self._print_step(f"Deleting branch '{branch_name}'")
                self._run_command(["git", "branch", "-D", branch_name], check=False)
                self._print_success(f"Branch '{branch_name}' deleted")
            except subprocess.CalledProcessError:
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

        self._print_step(f"Starting services for worktree '{name}'")

        cmd = [
            "docker-compose",
            "-f", str(base_file),
            "-f", str(override_file),
            "up", "-d"
        ]

        if build:
            cmd.append("--build")

        if services:
            cmd.extend(services)

        self._run_command(cmd, cwd=Path(compose_dir))
        self._print_success("Services started")

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

        self._print_step(f"Stopping services for worktree '{name}'")

        if services:
            # Stop specific services
            cmd = [
                "docker-compose",
                "-f", str(base_file),
                "-f", str(override_file),
                "stop"
            ]
            cmd.extend(services)
        else:
            # Stop all services
            cmd = [
                "docker-compose",
                "-f", str(base_file),
                "-f", str(override_file),
                "down"
            ]
            if remove_volumes:
                cmd.append("-v")

        self._run_command(cmd, cwd=Path(compose_dir))
        self._print_success("Services stopped")

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

        self._print_step(f"Restarting services for worktree '{name}'")

        cmd = [
            "docker-compose",
            "-f", str(base_file),
            "-f", str(override_file),
            "restart"
        ]

        if services:
            cmd.extend(services)

        self._run_command(cmd, cwd=Path(compose_dir))
        self._print_success("Services restarted")

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
            "docker-compose",
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
            "docker-compose",
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


def main():
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

        wt_args = wt_parser.parse_args(sys.argv[2:])

        if not wt_args.wt_command:
            wt_parser.print_help()
            sys.exit(1)

        manager = WorktreeManager(repo_path, repo_alias)

        if wt_args.wt_command == "new":
            manager.create_worktree(wt_args.name, wt_args.base, wt_args.skip_setup)
        elif wt_args.wt_command == "rm":
            manager.remove_worktree(wt_args.name, wt_args.force)
        elif wt_args.wt_command == "select":
            manager.select_worktree(wt_args.name, getattr(wt_args, 'shell_mode', False))
        elif wt_args.wt_command == "list":
            manager.list_worktrees()
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
