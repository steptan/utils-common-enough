"""
Tests for configuration management.
"""

import pytest
from pathlib import Path
import tempfile
import yaml
from unittest.mock import Mock, patch

from config import ProjectConfig, ConfigManager, get_project_config


class TestProjectConfig:
    """Test ProjectConfig dataclass."""
    
    def test_default_initialization(self):
        """Test creating config with minimal parameters."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project"
        )
        
        assert config.name == "test-project"
        assert config.display_name == "Test Project"
        assert config.aws_region == "us-east-1"
        assert config.environments == ["dev", "staging", "prod"]
        assert config.lambda_runtime == "nodejs20.x"
    
    def test_format_name(self):
        """Test pattern formatting."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            aws_account_id="123456789"
        )
        
        # Test basic pattern
        result = config.format_name("{project}-{environment}", environment="dev")
        assert result == "test-project-dev"
        
        # Test with account ID
        result = config.format_name("{project}-{account_id}", environment="dev")
        assert result == "test-project-123456789"
    
    def test_get_stack_name(self):
        """Test stack name generation."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            stack_name_pattern="{project}-stack-{environment}"
        )
        
        assert config.get_stack_name("dev") == "test-project-stack-dev"
        assert config.get_stack_name("prod") == "test-project-stack-prod"
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            custom_config={
                "feature_flag": True,
                "api_version": "v2"
            }
        )
        
        assert config.custom_config["feature_flag"] is True
        assert config.custom_config["api_version"] == "v2"
    
    def test_bucket_patterns_override(self):
        """Test bucket pattern overrides."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            bucket_patterns={
                "lambda": "custom-lambda-{environment}",
                "static": "custom-static-{environment}"
            }
        )
        
        assert config.bucket_patterns["lambda"] == "custom-lambda-{environment}"
        assert config.bucket_patterns["static"] == "custom-static-{environment}"
    
    def test_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        original = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            aws_region="us-west-2",
            custom_config={"key": "value"}
        )
        
        # Convert to dict and back
        data = original.to_dict()
        restored = ProjectConfig.from_dict(data)
        
        assert restored.name == original.name
        assert restored.display_name == original.display_name
        assert restored.aws_region == original.aws_region
        assert restored.custom_config == original.custom_config


class TestConfigManager:
    """Test ConfigManager class."""
    
    def test_default_configs_exist(self):
        """Test that default configs are defined."""
        assert "fraud-or-not" in ConfigManager.DEFAULT_CONFIGS
        assert "media-register" in ConfigManager.DEFAULT_CONFIGS
        assert "people-cards" in ConfigManager.DEFAULT_CONFIGS
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            # Should load from defaults
            config = manager.get_project_config("fraud-or-not")
            assert config.name == "fraud-or-not"
            assert config.display_name == "Fraud or Not"
            assert config.aws_region == "us-east-1"
    
    def test_load_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test YAML config for an existing project (fraud-or-not)
            config_file = Path(tmpdir) / "fraud-or-not.yaml"
            config_data = {
                "aws_region": "eu-west-1",
                "custom_config": {
                    "feature": "enabled"
                }
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f)
            
            # Load config
            manager = ConfigManager(config_dir=tmpdir)
            config = manager.get_project_config("fraud-or-not")
            
            # Should merge with defaults
            assert config.name == "fraud-or-not"
            assert config.display_name == "Fraud or Not"  # From defaults
            assert config.aws_region == "eu-west-1"  # From YAML file
            assert config.custom_config["feature"] == "enabled"
    
    def test_save_project_config(self):
        """Test saving configuration to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            # Create and save config
            config = ProjectConfig(
                name="new-project",
                display_name="New Project",
                aws_region="ap-southeast-1"
            )
            manager.save_project_config("new-project", config)
            
            # Verify file was created
            config_file = Path(tmpdir) / "new-project.yaml"
            assert config_file.exists()
            
            # Load and verify
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f)
            
            assert data["name"] == "new-project"
            assert data["aws_region"] == "ap-southeast-1"
    
    def test_list_projects(self):
        """Test listing available projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            # Should have default projects
            projects = manager.list_projects()
            assert "fraud-or-not" in projects
            assert "media-register" in projects
            assert "people-cards" in projects
    
    def test_unknown_project_error(self):
        """Test error handling for unknown project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            with pytest.raises(ValueError, match="Unknown project"):
                manager.get_project_config("non-existent-project")


class TestHelperFunctions:
    """Test module-level helper functions."""
    
    @patch('config._config_manager', None)
    def test_get_project_config(self):
        """Test get_project_config helper."""
        config = get_project_config("fraud-or-not")
        assert config.name == "fraud-or-not"
        assert config.display_name == "Fraud or Not"
    
    @patch.dict('os.environ', {'PROJECT_NAME': 'media-register'})
    def test_get_current_project_from_env(self):
        """Test getting current project from environment."""
        from config import get_current_project_config
        
        config = get_current_project_config()
        assert config is not None
        assert config.name == "media-register"
    
    def test_get_current_project_from_path(self):
        """Test getting current project from directory path."""
        from config import get_current_project_config
        
        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_cwd.return_value = Path("/home/user/projects/fraud-or-not/src")
            
            config = get_current_project_config()
            assert config is not None
            assert config.name == "fraud-or-not"
    
    def test_initialize_project_config(self):
        """Test initializing a new project configuration."""
        from config import initialize_project_config
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('config.get_config_manager') as mock_get_manager:
                mock_manager = Mock()
                mock_get_manager.return_value = mock_manager
                
                config = initialize_project_config(
                    "new-project",
                    display_name="New Project",
                    aws_region="us-west-2"
                )
                
                assert config.name == "new-project"
                assert config.display_name == "New Project"
                assert config.aws_region == "us-west-2"
                
                # Verify save was called
                mock_manager.save_project_config.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])