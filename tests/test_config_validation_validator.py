"""
Comprehensive tests for configuration validator module.
Tests YAML configuration validation, merging, and schema validation.
"""

import json
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import jsonschema

from typing import Any, Dict, List, Optional, Union

from src.config_validation.validator import (
    ConfigurationValidator,
    CloudFormationYAMLLoader,
    cfn_tag_constructor
)


class TestCloudFormationYAMLLoader:
    """Test CloudFormation YAML loader functionality."""

    def test_cfn_tag_constructor_scalar(self) -> None:
        """Test CloudFormation tag constructor with scalar node."""
        loader = CloudFormationYAMLLoader("")
        node = yaml.ScalarNode(tag='tag:yaml.org,2002:str', value='test-value')
        
        result = cfn_tag_constructor(loader, "Ref", node)
        assert result == 'test-value'

    def test_cfn_tag_constructor_sequence(self) -> None:
        """Test CloudFormation tag constructor with sequence node."""
        loader = CloudFormationYAMLLoader("")
        node = yaml.SequenceNode(
            tag='tag:yaml.org,2002:seq',
            value=[
                yaml.ScalarNode(tag='tag:yaml.org,2002:str', value='item1'),
                yaml.ScalarNode(tag='tag:yaml.org,2002:str', value='item2')
            ]
        )
        
        with patch.object(loader, 'construct_sequence', return_value=['item1', 'item2']):
            result = cfn_tag_constructor(loader, "GetAZs", node)
            assert result == ['item1', 'item2']

    def test_cfn_tag_constructor_mapping(self) -> None:
        """Test CloudFormation tag constructor with mapping node."""
        loader = CloudFormationYAMLLoader("")
        node = yaml.MappingNode(
            tag='tag:yaml.org,2002:map',
            value=[]
        )
        
        with patch.object(loader, 'construct_mapping', return_value={'key': 'value'}):
            result = cfn_tag_constructor(loader, "Sub", node)
            assert result == {'key': 'value'}

    def test_cfn_tag_constructor_invalid_node(self) -> None:
        """Test CloudFormation tag constructor with invalid node type."""
        loader = CloudFormationYAMLLoader("")
        # Create a mock node that's not scalar, sequence, or mapping
        node = Mock()
        node.start_mark = Mock()
        
        # Remove isinstance behavior to simulate unknown node type
        with patch('builtins.isinstance', side_effect=[False, False, False]):
            with pytest.raises(yaml.constructor.ConstructorError):
                cfn_tag_constructor(loader, "Invalid", node)

    def test_cloudformation_tags_registered(self) -> None:
        """Test that all CloudFormation intrinsic functions are registered."""
        yaml_content = """
        Resources:
          TestResource:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Sub "${AWS::StackName}-bucket"
              Tags:
                - Key: Name
                  Value: !Ref BucketName
        """
        
        # Should parse without errors
        data = yaml.load(yaml_content, Loader=CloudFormationYAMLLoader)
        assert data is not None
        assert 'Resources' in data


class TestConfigurationValidator:
    """Test ConfigurationValidator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_name = "test-project"
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(parents=True)
        
        # Create validation directory
        (self.config_dir / "validation").mkdir()
        
        # Create environments directory
        (self.config_dir / "environments").mkdir()
        
        # Create base configuration
        self.base_config = {
            "project": {
                "name": self.project_name,
                "version": "1.0.0"
            },
            "storage": {
                "dynamodb": {
                    "tables": [
                        {
                            "name": "users",
                            "partition_key": {"name": "id", "type": "S"}
                        }
                    ]
                }
            }
        }
        
        with open(self.config_dir / "base.yaml", "w") as f:
            yaml.dump(self.base_config, f)
        
        # Create schema
        self.schema = {
            "type": "object",
            "properties": {
                "project": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"}
                    },
                    "required": ["name", "version"]
                }
            }
        }
        
        with open(self.config_dir / "validation" / "schema.yaml", "w") as f:
            yaml.dump(self.schema, f)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self) -> None:
        """Test validator initialization."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        assert validator.project_name == self.project_name
        assert validator.config_dir == self.config_dir

    def test_init_find_config_dir(self) -> None:
        """Test validator finds config directory automatically."""
        # Create config in current directory
        cwd_config = Path.cwd() / "config"
        cwd_config.mkdir(exist_ok=True)
        
        try:
            validator = ConfigurationValidator(self.project_name)
            assert validator.config_dir == cwd_config
        finally:
            cwd_config.rmdir()

    def test_find_config_dir_not_found(self) -> None:
        """Test error when config directory not found."""
        with pytest.raises(FileNotFoundError) as exc_info:
            ConfigurationValidator("nonexistent-project")
        
        assert "Could not find config directory" in str(exc_info.value)

    def test_load_schema(self) -> None:
        """Test schema loading."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        schema = validator.load_schema()
        
        assert schema == self.schema

    def test_load_schema_not_found(self) -> None:
        """Test schema loading when file not found."""
        (self.config_dir / "validation" / "schema.yaml").unlink()
        
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        schema = validator.load_schema()
        
        assert schema == {}

    def test_load_config(self) -> None:
        """Test configuration loading."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        config = validator.load_config(self.config_dir / "base.yaml")
        
        assert config == self.base_config

    def test_load_config_not_found(self) -> None:
        """Test error when configuration file not found."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            validator.load_config(self.config_dir / "missing.yaml")
        
        assert "Configuration file not found" in str(exc_info.value)

    def test_load_config_with_cloudformation_tags(self) -> None:
        """Test loading configuration with CloudFormation intrinsic functions."""
        cf_config = {
            "resources": {
                "bucket": {
                    "name": {"Fn::Sub": "${AWS::StackName}-bucket"},
                    "arn": {"Fn::GetAtt": ["Bucket", "Arn"]}
                }
            }
        }
        
        config_file = self.config_dir / "cf_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(cf_config, f)
        
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        config = validator.load_config(config_file)
        
        assert config == cf_config

    def test_merge_config_simple(self) -> None:
        """Test simple configuration merging."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        
        result = validator.merge_config(base, override)
        
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_config_nested(self) -> None:
        """Test nested configuration merging."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        base = {
            "level1": {
                "level2": {
                    "a": 1,
                    "b": 2
                }
            }
        }
        override = {
            "level1": {
                "level2": {
                    "b": 3,
                    "c": 4
                }
            }
        }
        
        result = validator.merge_config(base, override)
        
        assert result == {
            "level1": {
                "level2": {
                    "a": 1,
                    "b": 3,
                    "c": 4
                }
            }
        }

    def test_merge_config_dynamodb_tables(self) -> None:
        """Test special handling for DynamoDB tables merging."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        base = {
            "storage": {
                "dynamodb": {
                    "tables": [
                        {
                            "name": "users",
                            "partition_key": {"name": "id", "type": "S"},
                            "billing_mode": "PAY_PER_REQUEST"
                        },
                        {
                            "name": "sessions",
                            "partition_key": {"name": "sessionId", "type": "S"}
                        }
                    ]
                }
            }
        }
        
        override = {
            "storage": {
                "dynamodb": {
                    "tables": [
                        {
                            "name": "users",
                            "billing_mode": "PROVISIONED",
                            "read_capacity": 5
                        },
                        {
                            "name": "orders",
                            "partition_key": {"name": "orderId", "type": "S"}
                        }
                    ]
                }
            }
        }
        
        result = validator.merge_config(base, override)
        
        # Check that users table was updated
        users_table = next(t for t in result["storage"]["dynamodb"]["tables"] if t["name"] == "users")
        assert users_table["billing_mode"] == "PROVISIONED"
        assert users_table["read_capacity"] == 5
        assert users_table["partition_key"] == {"name": "id", "type": "S"}  # Kept from base
        
        # Check that sessions table was kept
        assert any(t["name"] == "sessions" for t in result["storage"]["dynamodb"]["tables"])
        
        # Check that orders table was added
        assert any(t["name"] == "orders" for t in result["storage"]["dynamodb"]["tables"])
        
        # Check total table count
        assert len(result["storage"]["dynamodb"]["tables"]) == 3

    def test_validate_config_valid(self) -> None:
        """Test configuration validation with valid config."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        config = {
            "project": {
                "name": "test",
                "version": "1.0.0"
            }
        }
        
        is_valid, errors = validator.validate_config(config, self.schema)
        
        assert is_valid is True
        assert errors == []

    def test_validate_config_invalid(self) -> None:
        """Test configuration validation with invalid config."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        config = {
            "project": {
                "name": "test"
                # Missing required 'version'
            }
        }
        
        is_valid, errors = validator.validate_config(config, self.schema)
        
        assert is_valid is False
        assert len(errors) > 0
        assert "Configuration validation failed" in errors[0]

    def test_validate_config_no_schema(self) -> None:
        """Test configuration validation without schema."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        is_valid, errors = validator.validate_config({}, {})
        
        assert is_valid is True
        assert errors == []

    def test_validate_config_schema_error(self) -> None:
        """Test configuration validation with invalid schema."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        
        invalid_schema = {"type": "invalid_type"}
        
        is_valid, errors = validator.validate_config({}, invalid_schema)
        
        assert is_valid is False
        assert "Schema validation failed" in errors[0]

    def test_validate_environment(self) -> None:
        """Test environment validation."""
        # Create dev environment config
        dev_config = {
            "project": {
                "version": "1.0.1"  # Override version
            }
        }
        
        with open(self.config_dir / "environments" / "dev.yaml", "w") as f:
            yaml.dump(dev_config, f)
        
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        is_valid, result = validator.validate_environment("dev")
        
        assert is_valid is True
        assert result["environment"] == "dev"
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["merged_config"]["project"]["name"] == self.project_name
        assert result["merged_config"]["project"]["version"] == "1.0.1"

    def test_validate_environment_no_env_config(self) -> None:
        """Test environment validation without environment-specific config."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        is_valid, result = validator.validate_environment("prod")
        
        assert is_valid is True
        assert result["environment"] == "prod"
        assert len(result["warnings"]) > 0
        assert "No environment-specific configuration found" in result["warnings"][0]
        assert result["merged_config"] == self.base_config

    def test_validate_environment_error(self) -> None:
        """Test environment validation with error."""
        # Remove base config to cause error
        (self.config_dir / "base.yaml").unlink()
        
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        is_valid, result = validator.validate_environment("dev")
        
        assert is_valid is False
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "Error during validation" in result["errors"][0]

    def test_validate_all_environments(self) -> None:
        """Test validation of all environments."""
        # Create multiple environment configs
        for env in ["dev", "staging", "prod"]:
            env_config = {
                "project": {
                    "environment": env
                }
            }
            
            with open(self.config_dir / "environments" / f"{env}.yaml", "w") as f:
                yaml.dump(env_config, f)
        
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        results = validator.validate_all_environments()
        
        assert results["all_valid"] is True
        assert len(results["environments"]) == 3
        assert "dev" in results["environments"]
        assert "staging" in results["environments"]
        assert "prod" in results["environments"]

    def test_validate_all_environments_no_dir(self) -> None:
        """Test validation when environments directory doesn't exist."""
        (self.config_dir / "environments").rmdir()
        
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        results = validator.validate_all_environments()
        
        assert results["all_valid"] is False
        assert "error" in results
        assert "Environments directory not found" in results["error"]

    def test_validate_all_environments_empty(self) -> None:
        """Test validation when no environment configurations exist."""
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        results = validator.validate_all_environments()
        
        assert results["all_valid"] is True
        assert len(results["environments"]) == 0

    def test_validate_all_environments_with_invalid(self) -> None:
        """Test validation with one invalid environment."""
        # Create valid dev config
        dev_config = {"project": {"version": "1.0.0"}}
        with open(self.config_dir / "environments" / "dev.yaml", "w") as f:
            yaml.dump(dev_config, f)
        
        # Create invalid prod config (missing required fields after merge)
        # First, corrupt the base config
        with open(self.config_dir / "base.yaml", "w") as f:
            yaml.dump({"project": {}}, f)  # Missing required fields
        
        validator = ConfigurationValidator(self.project_name, self.config_dir)
        results = validator.validate_all_environments()
        
        assert results["all_valid"] is False
        assert results["environments"]["dev"]["valid"] is False