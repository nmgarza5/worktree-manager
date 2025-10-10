#!/usr/bin/env python3
"""
Git Worktree Manager for Onyx Development

A tool to manage git worktrees with automatic environment setup for the Onyx project.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


class Colors:
    """ANSI color codes for terminal output"""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


class WorktreeManager:
    """Manages git worktrees and their environment setup"""

    def __init__(self, main_repo: str = "~/onyx"):
        self.main_repo = Path(main_repo).expanduser().resolve()
        self.worktree_base = self.main_repo.parent

        if not self.main_repo.exists():
            print(f"{Colors.RED}Error: Main repository not found at {self.main_repo}{Colors.END}")
            sys.exit(1)

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
                    worktrees[Path(current_path).name] = current_branch
                current_path = None
                current_branch = None

        return worktrees

    def create_worktree(self, name: str, base_branch: str = "origin/main"):
        """Create a new worktree with full environment setup"""
        worktree_path = self._get_worktree_path(name)

        # Check if worktree already exists
        if worktree_path.exists():
            print(f"{Colors.RED}Error: Worktree '{name}' already exists at {worktree_path}{Colors.END}")
            sys.exit(1)

        # Step 1: Create worktree and branch
        self._print_step(f"Creating worktree '{name}' from {base_branch}")
        self._run_command([
            "git", "worktree", "add", "-b", name, str(worktree_path), base_branch
        ])
        self._print_success(f"Worktree created at {worktree_path}")

        # Step 2: Setup Python virtual environment
        self._print_step("Setting up Python virtual environment")
        venv_path = worktree_path / ".venv"
        self._run_command(["python3", "-m", "venv", str(venv_path)])
        self._print_success("Virtual environment created")

        # Determine pip path based on OS
        if sys.platform == "win32":
            pip_path = venv_path / "Scripts" / "pip"
        else:
            pip_path = venv_path / "bin" / "pip"

        # Step 3: Install Python dependencies
        self._print_step("Installing Python dependencies (this may take a few minutes)")
        backend_path = worktree_path / "backend"

        requirements_files = [
            backend_path / "requirements" / "default.txt",
            backend_path / "requirements" / "dev.txt",
            backend_path / "requirements" / "ee.txt",
            backend_path / "requirements" / "model_server.txt"
        ]

        for req_file in requirements_files:
            if req_file.exists():
                print(f"  Installing {req_file.name}...")
                self._run_command([str(pip_path), "install", "-r", str(req_file)])

        # Install package in editable mode
        self._run_command([str(pip_path), "install", "-e", "."], cwd=worktree_path)

        # Install pre-commit
        self._run_command([str(pip_path), "install", "pre-commit"])
        self._print_success("Python dependencies installed")

        # Step 4: Install Playwright
        self._print_step("Installing Playwright")
        playwright_path = venv_path / "bin" / "playwright" if sys.platform != "win32" else venv_path / "Scripts" / "playwright"
        self._run_command([str(playwright_path), "install"])
        self._print_success("Playwright installed")

        # Step 5: Setup pre-commit hooks
        self._print_step("Setting up pre-commit hooks")
        precommit_path = venv_path / "bin" / "pre-commit" if sys.platform != "win32" else venv_path / "Scripts" / "pre-commit"
        self._run_command([str(precommit_path), "install"], cwd=backend_path)
        self._print_success("Pre-commit hooks installed")

        # Step 6: Install Node dependencies
        self._print_step("Installing Node dependencies")
        web_path = worktree_path / "web"
        if web_path.exists():
            self._run_command(["npm", "install"], cwd=web_path)
            self._print_success("Node dependencies installed")

        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Worktree '{name}' is ready!{Colors.END}")
        print(f"\nTo start working:")
        print(f"  {Colors.BOLD}worktree select {name}{Colors.END}")
        print(f"\nOr manually:")
        print(f"  cd {worktree_path}")
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
        """Switch to a worktree by opening a new shell session"""
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

        # Generate activation script based on shell
        shell = os.environ.get('SHELL', '/bin/bash')

        if 'zsh' in shell:
            # For zsh, we can change directory and activate venv
            print(f"\n{Colors.YELLOW}Run the following commands:{Colors.END}")
            print(f"  cd {worktree_path}")
            if venv_activate.exists():
                print(f"  source .venv/bin/activate")
        elif 'bash' in shell:
            print(f"\n{Colors.YELLOW}Run the following commands:{Colors.END}")
            print(f"  cd {worktree_path}")
            if venv_activate.exists():
                print(f"  source .venv/bin/activate")
        else:
            print(f"\n{Colors.YELLOW}Navigate to:{Colors.END} {worktree_path}")

    def list_worktrees(self):
        """List all existing worktrees"""
        existing_worktrees = self._get_existing_worktrees()

        if not existing_worktrees:
            print(f"{Colors.YELLOW}No worktrees found (besides main repository){Colors.END}")
            return

        print(f"{Colors.BOLD}Existing worktrees:{Colors.END}\n")

        for name, branch in sorted(existing_worktrees.items()):
            worktree_path = self._get_worktree_path(name)
            status_indicator = "✓" if worktree_path.exists() else "✗"
            print(f"  {Colors.GREEN}{status_indicator}{Colors.END} {Colors.BOLD}{name}{Colors.END}")
            print(f"    Branch: {branch}")
            print(f"    Path: {worktree_path}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Git Worktree Manager for Onyx Development",
        formatter_class=argparse.RawDescriptionHelpFormatter
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

    manager = WorktreeManager()

    if args.command == "new":
        manager.create_worktree(args.name, args.base)
    elif args.command == "rm":
        manager.remove_worktree(args.name, args.force)
    elif args.command == "select":
        manager.select_worktree(args.name)
    elif args.command == "list":
        manager.list_worktrees()


if __name__ == "__main__":
    main()
