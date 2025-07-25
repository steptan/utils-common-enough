"""
Configuration management for project utilities.

Handles project-specific variables and settings for fraud-or-not, media-register, and people-cards.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml


@dataclass
class ProjectConfig:
    """Configuration for a specific project."""

    # Project identification
    name: str
    display_name: str
    aws_region: str = "us-west-1"
    aws_account_id: Optional[str] = None

    # Environment settings
    environments: list[str] = field(default_factory=lambda: ["dev", "staging", "prod"])
    default_environment: str = "dev"

    # Stack naming patterns
    stack_name_pattern: str = "{project}-{environment}"
    lambda_bucket_pattern: str = "{project}-lambda-{environment}-{account_id}"
    deployment_bucket_pattern: str = "{project}-deployments-{account_id}"

    # IAM patterns
    cicd_user_pattern: str = "{project}-cicd-user"
    cicd_policy_pattern: str = "{project}-cicd-policy"
    lambda_role_pattern: str = "{project}-{environment}-lambda-role"

    # S3 bucket patterns
    frontend_bucket_pattern: str = "{project}-frontend-{environment}"
    media_bucket_pattern: str = "{project}-media-{environment}"
    logs_bucket_pattern: str = "{project}-logs-{environment}"

    # Lambda configuration
    lambda_runtime: str = "nodejs20.x"
    lambda_timeout: int = 30
    lambda_memory: int = 512
    lambda_architecture: str = "arm64"
    lambda_handler: str = "index.handler"
    lambda_code_bucket: str = ""  # Set dynamically by CI/CD
    require_nat: bool = True  # Whether Lambda needs NAT Gateway

    # Build requirements
    node_version: str = "20.x"
    python_version: str = "3.11"

    # API Gateway configuration
    api_stage_name: str = "api"
    api_throttle_rate_limit: int = 10000
    api_throttle_burst_limit: int = 5000

    # DynamoDB configuration
    dynamodb_billing_mode: str = "PAY_PER_REQUEST"
    dynamodb_point_in_time_recovery: bool = True

    # CloudFront configuration
    cloudfront_price_class: str = "PriceClass_100"
    cloudfront_min_ttl: int = 0
    cloudfront_default_ttl: int = 86400
    cloudfront_max_ttl: int = 31536000

    # Build and deployment
    build_output_dir: str = "dist"
    lambda_output_dir: str = "lambda-dist"
    frontend_build_command: str = "npm run build"
    frontend_dist_dir: str = "out"

    # Testing
    test_command: str = "npm test"
    test_coverage_threshold: int = 80

    # Monitoring
    enable_monitoring: bool = True
    log_retention_days: int = 30
    alarm_email: Optional[str] = None

    # Security
    enable_waf: bool = False
    require_api_key: bool = False
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])

    # Project-specific overrides
    custom_config: Dict[str, Any] = field(default_factory=dict)

    # Additional patterns that can be loaded from config
    bucket_patterns: Dict[str, str] = field(default_factory=dict)
    table_patterns: Dict[str, str] = field(default_factory=dict)

    def format_name(self, pattern: str, **kwargs) -> str:
        """Format a naming pattern with project variables."""
        variables = {
            "project": self.name,
            "display_name": self.display_name,
            "account_id": self.aws_account_id or "unknown",
            **kwargs,
        }
        return pattern.format(**variables)

    def get_stack_name(self, environment: str) -> str:
        """Get the CloudFormation stack name for an environment."""
        return self.format_name(self.stack_name_pattern, environment=environment)
    
    def get_resource_name(self, resource_type: str, resource_name: str, environment: str) -> str:
        """Get resource name following new naming convention.
        
        Pattern: {project-code}-{env}-{resource-name}
        Uses 3-letter project codes and env codes
        """
        project_code = self.get_project_code()
        env_code = self.get_environment_code(environment)
        return f"{project_code}-{env_code}-{resource_name}"
    
    def get_project_code(self) -> str:
        """Get 3-letter project code."""
        project_codes = {
            "fraud-or-not": "fon",
            "people-cards": "pec", 
            "media-register": "mer"
        }
        return project_codes.get(self.name, self.name[:3].lower())
    
    def get_environment_code(self, environment: str) -> str:
        """Get 3-letter environment code."""
        env_codes = {
            "development": "dev",
            "staging": "stg",
            "production": "prd",
            "dev": "dev",
            "stg": "stg", 
            "prod": "prd"
        }
        return env_codes.get(environment, environment[:3].lower())
    
    def get_dynamodb_table_name(self, table_name: str, environment: str) -> str:
        """Get DynamoDB table name following naming convention."""
        return self.get_resource_name("table", table_name, environment)
    
    def get_s3_bucket_name(self, bucket_purpose: str, environment: str) -> str:
        """Get S3 bucket name following naming convention."""
        return self.get_resource_name("bucket", bucket_purpose, environment)
    
    def get_lambda_function_name(self, function_name: str, environment: str) -> str:
        """Get Lambda function name following naming convention."""
        return self.get_resource_name("function", function_name, environment)

    def get_lambda_bucket(self, environment: str) -> str:
        """Get the Lambda deployment bucket name."""
        return self.format_name(self.lambda_bucket_pattern, environment=environment)

    def get_frontend_bucket(self, environment: str) -> str:
        """Get the frontend bucket name."""
        return self.format_name(self.frontend_bucket_pattern, environment=environment)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        """Create config from dictionary."""
        return cls(**data)


class ConfigManager:
    """Manages configuration for all projects."""

    # Default configurations for each project
    DEFAULT_CONFIGS = {
        "fraud-or-not": {
            "name": "fraud-or-not",
            "display_name": "Fraud or Not",
            "aws_region": "us-west-1",
            "lambda_runtime": "nodejs20.x",
            "frontend_build_command": "npm run build",
            "frontend_dist_dir": "out",
            "custom_config": {
                "cognito_domain_prefix": "fraud-or-not-auth",
                "screenshot_processing": True,
            },
        },
        "media-register": {
            "name": "media-register",
            "display_name": "Media Register",
            "aws_region": "us-west-1",
            "lambda_runtime": "nodejs20.x",
            "frontend_build_command": "npm run build",
            "frontend_dist_dir": "out",
            "enable_waf": True,
            "custom_config": {
                "enable_usage_tracking": True,
                "media_types": ["image", "video", "audio", "document"],
            },
        },
        "people-cards": {
            "name": "people-cards",
            "display_name": "People Cards",
            "aws_region": "us-west-1",
            "lambda_runtime": "nodejs20.x",
            "frontend_build_command": "npm run build",
            "frontend_dist_dir": ".next/static",
            "custom_config": {
                "enable_social_features": True,
                "card_templates": ["professional", "creative", "minimal"],
            },
        },
    }

    def __init__(self, config_dir: Optional[Union[str, Path]] = None) -> None:
        """Initialize config manager."""
        self.config_dir = Path(config_dir) if config_dir else self._find_config_dir()
        self._cache: Dict[str, ProjectConfig] = {}
        self._load_configs()

    def _find_config_dir(self) -> Path:
        """Find the configuration directory."""
        # Look for utils project directory
        current = Path.cwd()

        # Check if we're in the utils directory or a subdirectory
        utils_dir = None
        for parent in [current] + list(current.parents):
            if parent.name == "utils" and (parent / "pyproject.toml").exists():
                utils_dir = parent
                break
            # Also check if utils is a sibling directory
            utils_sibling = parent / "utils"
            if utils_sibling.exists() and (utils_sibling / "pyproject.toml").exists():
                utils_dir = utils_sibling
                break

        if utils_dir:
            config_dir = utils_dir / "config"
            config_dir.mkdir(exist_ok=True)
            return config_dir

        # Fallback to current directory
        config_dir = Path.cwd() / "config"
        config_dir.mkdir(exist_ok=True)
        return config_dir

    def _load_configs(self) -> None:
        """Load all project configurations."""
        # Load from config files if they exist
        for project_name in self.DEFAULT_CONFIGS:
            config_file = self.config_dir / f"{project_name}.yaml"
            if config_file.exists():
                with open(config_file, "r") as f:
                    config_data = yaml.safe_load(f)
                    # Merge with defaults
                    merged_config = {
                        **self.DEFAULT_CONFIGS[project_name],
                        **config_data,
                    }
                    self._cache[project_name] = ProjectConfig.from_dict(merged_config)
            else:
                # Use default config
                self._cache[project_name] = ProjectConfig.from_dict(
                    self.DEFAULT_CONFIGS[project_name]
                )

    def get_project_config(self, project_name: str) -> ProjectConfig:
        """Get configuration for a specific project."""
        if project_name not in self._cache:
            if project_name in self.DEFAULT_CONFIGS:
                self._cache[project_name] = ProjectConfig.from_dict(
                    self.DEFAULT_CONFIGS[project_name]
                )
            else:
                raise ValueError(f"Unknown project: {project_name}")

        return self._cache[project_name]

    def save_project_config(self, project_name: str, config: ProjectConfig) -> None:
        """Save project configuration to file."""
        config_file = self.config_dir / f"{project_name}.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False)
        self._cache[project_name] = config

    def list_projects(self) -> list[str]:
        """List all available projects."""
        return list(self._cache.keys())

    def get_all_configs(self) -> Dict[str, ProjectConfig]:
        """Get all project configurations."""
        return self._cache.copy()


# Singleton instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: Optional[Union[str, Path]] = None) -> ConfigManager:
    """Get or create the config manager instance."""
    global _config_manager
    if _config_manager is None or config_dir is not None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager


def get_project_config(
    project_name: str, config_dir: Optional[Union[str, Path]] = None
) -> ProjectConfig:
    """Get configuration for a specific project."""
    manager = get_config_manager(config_dir)
    return manager.get_project_config(project_name)


def get_current_project_config() -> Optional[ProjectConfig]:
    """Try to determine and get the current project's configuration."""
    # Check environment variable
    project_name = os.environ.get("PROJECT_NAME")
    if project_name:
        return get_project_config(project_name)

    # Try to determine from current directory
    cwd = Path.cwd()
    for part in cwd.parts:
        if part in ["fraud-or-not", "media-register", "people-cards"]:
            return get_project_config(part)

    return None


def initialize_project_config(project_name: str, **kwargs) -> ProjectConfig:
    """Initialize a new project configuration."""
    manager = get_config_manager()

    # Start with defaults if available
    if project_name in ConfigManager.DEFAULT_CONFIGS:
        config_data = ConfigManager.DEFAULT_CONFIGS[project_name].copy()
        config_data.update(kwargs)
    else:
        config_data = {
            "name": project_name,
            "display_name": project_name.title(),
            **kwargs,
        }

    config = ProjectConfig.from_dict(config_data)
    manager.save_project_config(project_name, config)
    return config
