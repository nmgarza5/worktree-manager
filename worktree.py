#!/usr/bin/env python3
"""
Git Worktree Manager

A generic tool to manage git worktrees with optional environment setup.
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
                # For shell commands, join the list into a string
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
        # Run as shell command to support complex commands
        self._run_command([command], cwd=work_dir, shell=True)


class WorktreeManager:
    """Manages git worktrees with optional setup configuration"""

    def __init__(self, repo_path: Optional[str] = None):
        # Use provided repo path or current directory
        if repo_path:
            self.main_repo = Path(repo_path).expanduser().resolve()
        else:
            self.main_repo = Path.cwd()

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

    def _load_setup_config(self) -> Optional[Dict]:
        """Load setup configuration if it exists"""
        # Look for setup config in common locations
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
                    # Only include worktrees in our worktree directory
                    if str(self.worktree_base) in current_path:
                        worktrees[Path(current_path).name] = current_branch
                current_path = None
                current_branch = None

        return worktrees

    def create_worktree(self, name: str, base_branch: str = "origin/main", skip_setup: bool = False):
        """Create a new worktree with optional environment setup"""
        worktree_path = self._get_worktree_path(name)

        # Check if worktree already exists
        if worktree_path.exists():
            print(f"{Colors.RED}Error: Worktree '{name}' already exists at {worktree_path}{Colors.END}")
            sys.exit(1)

        # Create worktrees directory if it doesn't exist
        self.worktree_base.mkdir(exist_ok=True)

        # Create worktree and branch
        self._print_step(f"Creating worktree '{name}' from {base_branch}")
        self._run_command([
            "git", "worktree", "add", "-b", name, str(worktree_path), base_branch
        ])
        self._print_success(f"Worktree created at {worktree_path}")

        # Execute setup steps if config exists and not skipped
        if not skip_setup:
            setup_config = self._load_setup_config()
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
        print(f"\nLocation: {worktree_path}")
        print(f"\nTo start working:")
        print(f"  cd {worktree_path}")
        if (worktree_path / ".venv" / "bin" / "activate").exists():
            print(f"  source .venv/bin/activate")

    def remove_worktree(self, name: str, force: bool = False):
        """Remove a worktree and clean up its branch"""
        worktree_path = self._get_worktree_path(name)

        # Check if worktree exists
        existing_worktrees = self._get_existing_worktrees()
        if name not in existing_worktrees:
            print(f"{Colors.RED}Error: Worktree '{name}' not found{Colors.END}")
            sys.exit(1)

        # Confirm deletion unless force flag is used
        if not force:
            response = input(f"Are you sure you want to remove worktree '{name}'? [y/N]: ")
            if response.lower() != 'y':
                print("Cancelled.")
                return

        # Remove worktree
        self._print_step(f"Removing worktree '{name}'")
        force_flag = ["--force"] if force else []
        self._run_command(["git", "worktree", "remove", *force_flag, str(worktree_path)])
        self._print_success(f"Worktree removed: {worktree_path}")

        # Delete branch if it exists
        branch_name = existing_worktrees[name]
        if branch_name != 'detached':
            try:
                self._print_step(f"Deleting branch '{branch_name}'")
                self._run_command(["git", "branch", "-D", branch_name], check=False)
                self._print_success(f"Branch '{branch_name}' deleted")
            except subprocess.CalledProcessError:
                self._print_warning(f"Could not delete branch '{branch_name}' (may already be deleted)")

        print(f"\n{Colors.GREEN}✓ Worktree '{name}' removed successfully{Colors.END}")

    def select_worktree(self, name: str):
        """Switch to a worktree"""
        worktree_path = self._get_worktree_path(name)

        # Check if worktree exists
        existing_worktrees = self._get_existing_worktrees()
        if name not in existing_worktrees:
            print(f"{Colors.RED}Error: Worktree '{name}' not found{Colors.END}")
            print(f"\nAvailable worktrees:")
            for wt_name in existing_worktrees.keys():
                print(f"  - {wt_name}")
            sys.exit(1)

        venv_activate = worktree_path / ".venv" / "bin" / "activate"

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


def main():
    parser = argparse.ArgumentParser(
        description="Git Worktree Manager - Manage git worktrees with optional environment setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  worktree new feature-xyz              Create a new worktree
  worktree new hotfix --base main       Create from a different branch
  worktree new test --skip-setup        Create without running setup
  worktree list                         List all worktrees
  worktree select feature-xyz           Switch to a worktree
  worktree rm feature-xyz               Remove a worktree

Setup Configuration:
  Place a .worktree-setup.json file in your repository root or home directory
  to automatically run setup commands when creating new worktrees.
        """
    )

    parser.add_argument(
        "--repo",
        help="Path to git repository (default: current directory)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # New command
    new_parser = subparsers.add_parser("new", help="Create a new worktree")
    new_parser.add_argument("name", help="Name of the worktree (will also be the branch name)")
    new_parser.add_argument(
        "--base",
        default="origin/main",
        help="Base branch to create worktree from (default: origin/main)"
    )
    new_parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip running setup steps even if config exists"
    )

    # Remove command
    rm_parser = subparsers.add_parser("rm", help="Remove a worktree")
    rm_parser.add_argument("name", help="Name of the worktree to remove")
    rm_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force removal without confirmation"
    )

    # Select command
    select_parser = subparsers.add_parser("select", help="Switch to a worktree")
    select_parser.add_argument("name", help="Name of the worktree to switch to")

    # List command
    list_parser = subparsers.add_parser("list", help="List all worktrees")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = WorktreeManager(repo_path=args.repo)

    if args.command == "new":
        manager.create_worktree(args.name, args.base, args.skip_setup)
    elif args.command == "rm":
        manager.remove_worktree(args.name, args.force)
    elif args.command == "select":
        manager.select_worktree(args.name)
    elif args.command == "list":
        manager.list_worktrees()


if __name__ == "__main__":
    main()
