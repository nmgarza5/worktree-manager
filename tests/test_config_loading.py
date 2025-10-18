"""Tests for configuration file loading (YAML and JSON)"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add parent directory to path to import worktree module
sys.path.insert(0, str(Path(__file__).parent.parent))

from worktree import WorktreeManager

# Try to import yaml, skip tests if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class TestConfigLoading:
    """Test YAML and JSON configuration file loading"""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary git repository"""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        # Create a minimal git repo
        (repo_path / ".git").mkdir()
        return repo_path

    @pytest.fixture
    def manager(self, temp_repo):
        """Create a WorktreeManager instance"""
        return WorktreeManager(temp_repo, "test-repo")

    @pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
    def test_load_yaml_config(self, manager, temp_repo):
        """Test loading YAML configuration"""
        config_file = temp_repo / "test-repo-setup.yaml"
        config_data = {
            "docker_compose": {
                "compose_dir": "docker",
                "services": {
                    "db": {
                        "internal": 5432,
                        "description": "Database"
                    }
                }
            },
            "setup_steps": [
                {
                    "name": "Create venv",
                    "command": "python3 -m venv .venv"
                },
                {
                    "name": "Install deps",
                    "command": "pip install -r requirements.txt"
                }
            ]
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        config = manager._load_setup_config()

        assert config is not None
        assert "docker_compose" in config
        assert "setup_steps" in config
        assert len(config["setup_steps"]) == 2
        assert config["setup_steps"][0]["name"] == "Create venv"
        assert config["setup_steps"][0]["command"] == "python3 -m venv .venv"

    def test_load_json_config(self, manager, temp_repo):
        """Test loading JSON configuration (backward compatibility)"""
        config_file = temp_repo / "test-repo-setup.json"
        config_data = {
            "setup_steps": [
                {
                    "name": "Test step",
                    "command": "echo 'test'"
                }
            ]
        }

        with open(config_file, 'w') as f:
            json.dump(config_data, f)

        config = manager._load_setup_config()

        assert config is not None
        assert "setup_steps" in config
        assert config["setup_steps"][0]["name"] == "Test step"

    @pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
    def test_yaml_priority_over_json(self, manager, temp_repo):
        """Test that YAML files are preferred over JSON"""
        yaml_config = temp_repo / "test-repo-setup.yaml"
        json_config = temp_repo / "test-repo-setup.json"

        # Create both files
        with open(yaml_config, 'w') as f:
            yaml.dump({"source": "yaml"}, f)

        with open(json_config, 'w') as f:
            json.dump({"source": "json"}, f)

        config = manager._load_setup_config()

        # Should load YAML first
        assert config["source"] == "yaml"

    def test_config_not_found(self, manager):
        """Test when no configuration file exists"""
        config = manager._load_setup_config()
        assert config is None

    @pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
    def test_invalid_yaml(self, manager, temp_repo, capsys):
        """Test handling of invalid YAML"""
        config_file = temp_repo / "test-repo-setup.yaml"
        config_file.write_text("invalid: yaml: content:\n  - bad indentation")

        config = manager._load_setup_config()

        # Should skip invalid file and return None
        assert config is None

        # Should print warning
        captured = capsys.readouterr()
        assert "Warning: Invalid YAML" in captured.out

    def test_invalid_json(self, manager, temp_repo, capsys):
        """Test handling of invalid JSON"""
        config_file = temp_repo / "test-repo-setup.json"
        config_file.write_text("{invalid json content")

        config = manager._load_setup_config()

        # Should skip invalid file and return None
        assert config is None

        # Should print warning
        captured = capsys.readouterr()
        assert "Warning: Invalid JSON" in captured.out

    @pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
    def test_config_search_order(self, manager, temp_repo):
        """Test configuration file search order"""
        # Create a generic config file (lower priority)
        generic_config = temp_repo / ".worktree-setup.yaml"
        with open(generic_config, 'w') as f:
            yaml.dump({"priority": "generic"}, f)

        config = manager._load_setup_config()
        assert config["priority"] == "generic"

        # Create a repo-specific config (higher priority)
        specific_config = temp_repo / "test-repo-setup.yaml"
        with open(specific_config, 'w') as f:
            yaml.dump({"priority": "specific"}, f)

        config = manager._load_setup_config()
        assert config["priority"] == "specific"

    @pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
    def test_setup_step_with_cwd(self, manager, temp_repo):
        """Test setup step with working directory"""
        config_file = temp_repo / "test-repo-setup.yaml"
        config_data = {
            "setup_steps": [
                {
                    "name": "Install in backend",
                    "command": "pip install -r requirements.txt",
                    "cwd": "backend"
                }
            ]
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        config = manager._load_setup_config()

        assert config["setup_steps"][0]["cwd"] == "backend"

    @pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
    def test_docker_compose_config(self, manager, temp_repo):
        """Test Docker Compose configuration structure"""
        config_file = temp_repo / "test-repo-setup.yaml"
        config_data = {
            "docker_compose": {
                "compose_dir": "deployment/docker_compose",
                "services": {
                    "relational_db": {
                        "internal": 5432,
                        "description": "PostgreSQL database",
                        "isolate_data": True
                    },
                    "cache": {
                        "internal": 6379,
                        "description": "Redis cache"
                    }
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        config = manager._load_setup_config()

        assert "docker_compose" in config
        assert config["docker_compose"]["compose_dir"] == "deployment/docker_compose"
        assert "relational_db" in config["docker_compose"]["services"]
        assert config["docker_compose"]["services"]["relational_db"]["internal"] == 5432
        assert config["docker_compose"]["services"]["relational_db"]["isolate_data"] is True
