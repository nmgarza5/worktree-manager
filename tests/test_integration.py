"""Integration tests for setup execution"""
import pytest
from pathlib import Path
import sys
import tempfile
import shutil

# Add parent directory to path to import worktree module
sys.path.insert(0, str(Path(__file__).parent.parent))

from worktree import SetupExecutor, Colors

# Try to import yaml, skip tests if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class TestSetupIntegration:
    """Integration tests for the complete setup workflow"""

    @pytest.fixture
    def temp_worktree(self, tmp_path):
        """Create a temporary worktree directory"""
        worktree_path = tmp_path / "test-worktree"
        worktree_path.mkdir(parents=True, exist_ok=True)
        return worktree_path

    @pytest.fixture
    def executor(self, temp_worktree):
        """Create a SetupExecutor instance"""
        return SetupExecutor(temp_worktree, Colors)

    def test_python_venv_creation(self, executor, temp_worktree):
        """Test creating a Python virtual environment"""
        step = {
            "name": "Create Python venv",
            "command": "python3 -m venv .venv"
        }

        executor.execute_step(step)

        # Verify venv was created
        venv_path = temp_worktree / ".venv"
        assert venv_path.exists()
        assert (venv_path / "bin" / "python").exists() or (venv_path / "Scripts" / "python.exe").exists()

    def test_pip_install_simulation(self, executor, temp_worktree):
        """Test simulated pip install (creating a requirements file)"""
        # Create a simple requirements file
        requirements = temp_worktree / "requirements.txt"
        requirements.write_text("# Test requirements\n")

        # First create venv
        step1 = {
            "name": "Create venv",
            "command": "python3 -m venv .venv"
        }
        executor.execute_step(step1)

        # Then try to install (will succeed with empty requirements)
        step2 = {
            "name": "Install requirements",
            "command": ".venv/bin/pip install -q -r requirements.txt"
        }
        executor.execute_step(step2)

    def test_file_operations(self, executor, temp_worktree):
        """Test file operations in setup steps"""
        steps = [
            {
                "name": "Create directory",
                "command": "mkdir -p testdir/subdir"
            },
            {
                "name": "Create files",
                "command": "touch testdir/file1.txt testdir/subdir/file2.txt"
            },
            {
                "name": "Write content",
                "command": "echo 'test content' > testdir/output.txt"
            }
        ]

        for step in steps:
            executor.execute_step(step)

        # Verify all operations
        assert (temp_worktree / "testdir").exists()
        assert (temp_worktree / "testdir" / "subdir").exists()
        assert (temp_worktree / "testdir" / "file1.txt").exists()
        assert (temp_worktree / "testdir" / "subdir" / "file2.txt").exists()
        assert "test content" in (temp_worktree / "testdir" / "output.txt").read_text()

    def test_working_directory_execution(self, executor, temp_worktree):
        """Test commands executed in specific working directories"""
        # Create subdirectory
        subdir = temp_worktree / "backend"
        subdir.mkdir()

        step = {
            "name": "Create file in backend",
            "command": "echo 'backend file' > test.txt",
            "cwd": "backend"
        }

        executor.execute_step(step)

        # Verify file was created in subdirectory
        assert (subdir / "test.txt").exists()
        assert "backend file" in (subdir / "test.txt").read_text()

    def test_multi_step_workflow(self, executor, temp_worktree):
        """Test a complete multi-step setup workflow"""
        steps = [
            {
                "name": "Setup project structure",
                "command": "mkdir -p src tests docs"
            },
            {
                "name": "Create source files",
                "command": "echo 'def main(): pass' > main.py",
                "cwd": "src"
            },
            {
                "name": "Create test files",
                "command": "echo 'def test_main(): pass' > test_main.py",
                "cwd": "tests"
            },
            {
                "name": "Create documentation",
                "command": "echo '# Project Docs' > README.md",
                "cwd": "docs"
            }
        ]

        for step in steps:
            executor.execute_step(step)

        # Verify entire structure
        assert (temp_worktree / "src" / "main.py").exists()
        assert (temp_worktree / "tests" / "test_main.py").exists()
        assert (temp_worktree / "docs" / "README.md").exists()

    def test_error_in_middle_of_workflow(self, executor, temp_worktree):
        """Test that error in one step doesn't prevent seeing the error"""
        steps = [
            {
                "name": "Step 1 - success",
                "command": "mkdir step1"
            },
            {
                "name": "Step 2 - failure",
                "command": "exit 1"
            },
            {
                "name": "Step 3 - would succeed",
                "command": "mkdir step3"
            }
        ]

        # First step should succeed
        executor.execute_step(steps[0])
        assert (temp_worktree / "step1").exists()

        # Second step should fail
        with pytest.raises(Exception):
            executor.execute_step(steps[1])

        # Third step never runs in normal workflow
        # (WorktreeManager continues on error but that's tested elsewhere)

    def test_shell_features(self, executor, temp_worktree):
        """Test various shell features work correctly"""
        # Test environment variables
        step1 = {
            "name": "Test env vars",
            "command": "export MY_VAR=hello && echo $MY_VAR > env_test.txt"
        }
        executor.execute_step(step1)
        assert "hello" in (temp_worktree / "env_test.txt").read_text()

        # Test pipes
        step2 = {
            "name": "Test pipes",
            "command": "echo 'line1\nline2\nline3' | grep line2 > pipe_test.txt"
        }
        executor.execute_step(step2)
        assert "line2" in (temp_worktree / "pipe_test.txt").read_text()

        # Test command chaining
        step3 = {
            "name": "Test chaining",
            "command": "mkdir chain_test && cd chain_test && touch file.txt && echo 'success' > ../chain_result.txt"
        }
        executor.execute_step(step3)
        assert (temp_worktree / "chain_test" / "file.txt").exists()
        assert "success" in (temp_worktree / "chain_result.txt").read_text()

    def test_command_with_special_characters(self, executor, temp_worktree):
        """Test commands with special characters"""
        step = {
            "name": "Special chars",
            "command": "echo 'quotes \"nested\" and $vars' > special.txt"
        }

        executor.execute_step(step)
        content = (temp_worktree / "special.txt").read_text()
        assert "quotes" in content
        assert "nested" in content

    @pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
    def test_yaml_config_execution(self, executor, temp_worktree):
        """Test executing steps loaded from YAML config"""
        config_file = temp_worktree / "test-setup.yaml"
        config_data = {
            "setup_steps": [
                {
                    "name": "Create directories",
                    "command": "mkdir -p app/src app/tests"
                },
                {
                    "name": "Create config",
                    "command": "echo 'DEBUG=true' > .env"
                }
            ]
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Load and execute
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        for step in config["setup_steps"]:
            executor.execute_step(step)

        # Verify
        assert (temp_worktree / "app" / "src").exists()
        assert (temp_worktree / "app" / "tests").exists()
        assert (temp_worktree / ".env").exists()
        assert "DEBUG=true" in (temp_worktree / ".env").read_text()
