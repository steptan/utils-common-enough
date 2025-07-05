"""
Configuration Management for Media Register Application

Provides YAML-based configuration loading with environment inheritance
and JSON schema validation.
"""

import os
import yaml
import json
from typing import Dict, Any, Optional
from pathlib import Path
from jsonschema import validate, ValidationError
from dataclasses import dataclass


@dataclass
class ConfigurationError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""

    message: str
    details: Optional[str] = None


class ConfigManager:
    """
    Manages application configuration with environment inheritance.

    Features:
    - Loads base configuration from base.yaml
    - Applies environment-specific overrides
    - Validates configuration against JSON schema
    - Provides type-safe access to configuration values
    """

    def __init__(self, config_dir: str = "config", environment: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory containing configuration files
            environment: Environment name (dev, staging, prod). If None, uses ENVIRONMENT env var
        """
        self.config_dir = Path(config_dir)
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")

        # Validate config directory exists
        if not self.config_dir.exists():
            raise ConfigurationError(
                f"Configuration directory not found: {self.config_dir}"
            )

        # Load and validate configuration
        self._config = self._load_configuration()
        self._validate_configuration()

    def _load_configuration(self) -> Dict[str, Any]:
        """Load base configuration and apply environment overrides."""

        # Load base configuration
        base_config_path = self.config_dir / "base.yaml"
        if not base_config_path.exists():
            raise ConfigurationError(
                f"Base configuration file not found: {base_config_path}"
            )

        try:
            with open(base_config_path, "r") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse base configuration: {e}")

        # Load environment-specific overrides
        env_config_path = self.config_dir / "environments" / f"{self.environment}.yaml"
        if env_config_path.exists():
            try:
                with open(env_config_path, "r") as f:
                    env_config = yaml.safe_load(f)
                    config = self._deep_merge(config, env_config)
            except yaml.YAMLError as e:
                raise ConfigurationError(
                    f"Failed to parse environment configuration: {e}"
                )

        # Ensure environment is set in config
        config["environment"] = self.environment

        return config

    def _deep_merge(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _validate_configuration(self) -> None:
        """Validate configuration against JSON schema."""
        schema_path = self.config_dir / "validation" / "schema.yaml"

        if not schema_path.exists():
            # Skip validation if schema doesn't exist
            return

        try:
            with open(schema_path, "r") as f:
                schema = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse configuration schema: {e}")

        try:
            validate(instance=self._config, schema=schema)
        except ValidationError as e:
            raise ConfigurationError(
                f"Configuration validation failed: {e.message}",
                details=f"Path: {' -> '.join(str(p) for p in e.absolute_path)}",
            )

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to configuration value (e.g., 'app.name')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_required(self, key_path: str) -> Any:
        """
        Get required configuration value using dot notation.

        Args:
            key_path: Dot-separated path to configuration value

        Returns:
            Configuration value

        Raises:
            ConfigurationError: If key not found
        """
        value = self.get(key_path)
        if value is None:
            raise ConfigurationError(
                f"Required configuration key not found: {key_path}"
            )
        return value

    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation (runtime only).

        Args:
            key_path: Dot-separated path to configuration value
            value: Value to set
        """
        keys = key_path.split(".")
        target = self._config

        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        # Set the value
        target[keys[-1]] = value

    @property
    def environment_name(self) -> str:
        """Get the current environment name."""
        return self.environment

    @property
    def config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary (read-only)."""
        return self._config.copy()

    def export_env_vars(self, prefix: str = "MEDIA_REGISTER_") -> Dict[str, str]:
        """
        Export flat configuration as environment variables.

        Args:
            prefix: Prefix for environment variable names

        Returns:
            Dictionary of environment variables
        """
        env_vars = {}

        def flatten_dict(d: Dict[str, Any], parent_key: str = "") -> None:
            for key, value in d.items():
                env_key = f"{parent_key}_{key}".upper() if parent_key else key.upper()

                if isinstance(value, dict):
                    flatten_dict(value, env_key)
                else:
                    env_vars[f"{prefix}{env_key}"] = str(value)

        flatten_dict(self._config)
        return env_vars

    def to_json(self) -> str:
        """Export configuration as JSON string."""
        return json.dumps(self._config, indent=2, sort_keys=True)

    def to_yaml(self) -> str:
        """Export configuration as YAML string."""
        return yaml.dump(self._config, default_flow_style=False, sort_keys=True)

    def save_to_file(self, file_path: str, format: str = "yaml") -> None:
        """
        Save current configuration to file.

        Args:
            file_path: Path to save file
            format: File format ('yaml' or 'json')
        """
        path = Path(file_path)

        if format.lower() == "json":
            content = self.to_json()
        elif format.lower() == "yaml":
            content = self.to_yaml()
        else:
            raise ConfigurationError(f"Unsupported format: {format}")

        with open(path, "w") as f:
            f.write(content)


# Convenience functions for common configuration access patterns
def load_config(
    environment: Optional[str] = None, config_dir: str = "config"
) -> ConfigManager:
    """Load configuration for the specified environment."""
    return ConfigManager(config_dir=config_dir, environment=environment)


def get_aws_config(config: ConfigManager) -> Dict[str, Any]:
    """Extract AWS-specific configuration."""
    return {
        "region": config.get("aws.region", "us-east-1"),
        "account_id": config.get("aws.account_id"),
        "profile": config.get("aws.profile", "default"),
    }


def get_database_config(config: ConfigManager) -> Dict[str, Any]:
    """Extract database configuration."""
    return {
        "dynamodb": config.get("storage.dynamodb", {}),
        "table_prefix": f"media-register-{config.environment_name}",
    }


def get_storage_config(config: ConfigManager) -> Dict[str, Any]:
    """Extract storage configuration."""
    return {
        "s3": config.get("storage.s3", {}),
        "bucket_prefix": f"media-register-{config.environment_name}",
    }


def get_lambda_config(config: ConfigManager) -> Dict[str, Any]:
    """Extract Lambda configuration."""
    lambda_config = config.get("compute.lambda", {})
    return {
        "runtime": lambda_config.get("runtime", "python3.11"),
        "timeout": lambda_config.get("timeout", 30),
        "memory_size": lambda_config.get("memory_size", 512),
        "reserved_concurrency": lambda_config.get("reserved_concurrency"),
        "environment_variables": lambda_config.get("environment_variables", {}),
    }


# Example usage
if __name__ == "__main__":
    # Load configuration for development
    config = load_config("dev")

    # Access configuration values
    print(f"Application: {config.get('app.name')}")
    print(f"Environment: {config.environment_name}")
    print(f"VPC CIDR: {config.get('network.vpc.cidr')}")

    # Export as environment variables
    env_vars = config.export_env_vars()
    for key, value in env_vars.items():
        print(f"{key}={value}")

    # Validate and display configuration
    print(config.to_yaml())
