"""Tests for SetupExecutor class"""
import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path to import worktree module
sys.path.insert(0, str(Path(__file__).parent.parent))

from worktree import SetupExecutor, Colors


class TestSetupExecutor:
    """Test the SetupExecutor class"""

    @pytest.fixture
    def temp_worktree(self, tmp_path):
        """Create a temporary worktree directory"""
        return tmp_path / "test-worktree"

    @pytest.fixture
    def executor(self, temp_worktree):
        """Create a SetupExecutor instance"""
        temp_worktree.mkdir(parents=True, exist_ok=True)
        return SetupExecutor(temp_worktree, Colors)

    def test_execute_step_success(self, executor, capsys):
        """Test successful command execution"""
        step = {
            "name": "Test command",
            "command": "echo 'Hello World'"
        }

        # Should not raise an exception
        executor.execute_step(step)

        # Check output contains success indicator
        captured = capsys.readouterr()
        assert "✓" in captured.out
        assert "Test command" in captured.out

    def test_execute_step_with_cwd(self, executor, temp_worktree):
        """Test command execution with working directory"""
        # Create a subdirectory
        subdir = temp_worktree / "subdir"
        subdir.mkdir()

        step = {
            "name": "Test with cwd",
            "command": "pwd",
            "cwd": "subdir"
        }

        # Should execute in the subdirectory
        executor.execute_step(step)

    def test_execute_step_failure(self, executor, capsys):
        """Test failed command execution shows error details"""
        step = {
            "name": "Failing command",
            "command": "exit 42"
        }

        # Should raise CalledProcessError
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            executor.execute_step(step)

        # Check error output (strip ANSI color codes for testing)
        captured = capsys.readouterr()
        # Remove ANSI escape sequences for easier testing
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', captured.out)

        assert "Setup step failed: Failing command" in clean_output
        assert "Exit code: 42" in clean_output or "Exit code:\x1b[0m 42" in captured.out
        assert "exit 42" in clean_output
        assert "This is a problem with your setup command" in clean_output

    def test_execute_step_stderr_output(self, executor, capsys):
        """Test that stderr is displayed on failure"""
        step = {
            "name": "Command with stderr",
            "command": "echo 'error message' >&2 && exit 1"
        }

        with pytest.raises(subprocess.CalledProcessError):
            executor.execute_step(step)

        captured = capsys.readouterr()
        assert "Standard error:" in captured.out
        assert "error message" in captured.out

    def test_execute_step_stdout_output(self, executor, capsys):
        """Test that stdout is displayed on failure"""
        step = {
            "name": "Command with stdout",
            "command": "echo 'some output' && exit 1"
        }

        with pytest.raises(subprocess.CalledProcessError):
            executor.execute_step(step)

        captured = capsys.readouterr()
        assert "Standard output:" in captured.out
        assert "some output" in captured.out

    def test_execute_step_no_command(self, executor, capsys):
        """Test step with no command"""
        step = {
            "name": "No command step"
        }

        # Should not raise, just warn
        executor.execute_step(step)

        captured = capsys.readouterr()
        assert "has no command to execute" in captured.out

    def test_execute_step_complex_command(self, executor, temp_worktree):
        """Test complex shell command with pipes and operators"""
        # Create a test file
        test_file = temp_worktree / "test.txt"
        test_file.write_text("line1\nline2\nline3\n")

        step = {
            "name": "Complex command",
            "command": "cat test.txt | grep line2 | wc -l"
        }

        # Should execute successfully
        executor.execute_step(step)

    def test_execute_step_environment_variables(self, executor, temp_worktree):
        """Test command with environment variables"""
        step = {
            "name": "Env var test",
            "command": "export TEST_VAR=hello && echo $TEST_VAR > output.txt"
        }

        executor.execute_step(step)

        # Check the file was created with correct content
        output_file = temp_worktree / "output.txt"
        assert output_file.exists()
        assert "hello" in output_file.read_text()

    def test_execute_step_multiple_commands(self, executor, temp_worktree):
        """Test multiple commands with && operator"""
        step = {
            "name": "Multiple commands",
            "command": "mkdir -p testdir && cd testdir && touch file.txt"
        }

        executor.execute_step(step)

        # Verify the directory and file were created
        assert (temp_worktree / "testdir" / "file.txt").exists()
