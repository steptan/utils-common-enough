"""
Deployment configuration for Media Register application.
"""

import os
from typing import Any, Dict, Optional


class DeploymentConfig:
    """Manages deployment configuration for different environments."""

    def __init__(self, environment: str, overrides: Optional[Dict[str, Any]] = None):
        self.environment = environment
        self.overrides = overrides or {}
        self._load_config()

    def _load_config(self):
        """Load configuration based on environment."""
        # Base configuration
        self.base_config = {
            "app_name": "media-register",
            "aws_region": os.environ.get("AWS_REGION", "us-east-1"),
            "aws_account": os.environ.get("AWS_ACCOUNT_ID", ""),
            # Domain configuration
            "domain_name": "media-register.com",
            "certificate_arn": os.environ.get("CERTIFICATE_ARN", ""),
            # VPC configuration - disabled for cost optimization
            # Lambda functions run without VPC to save ~$45/month
            "enable_vpc": False,
            "vpc_cidr": None,  # Not used
            "enable_nat_gateway": False,  # Not used
            "max_azs": 0,  # Not used
            # Lambda configuration
            "lambda_memory": 512,
            "lambda_timeout": 30,
            "lambda_runtime": "nodejs20.x",
            # DynamoDB configuration
            "dynamodb_billing_mode": "PAY_PER_REQUEST",
            "enable_point_in_time_recovery": False,
            # S3 configuration
            "enable_s3_versioning": True,
            "s3_lifecycle_days": 90,
            # CloudFront configuration
            "cloudfront_price_class": "PriceClass_100",
            "cloudfront_min_ttl": 0,
            "cloudfront_default_ttl": 86400,
            "cloudfront_max_ttl": 31536000,
            # API Gateway configuration
            "api_throttle_rate_limit": 100,
            "api_throttle_burst_limit": 200,
            # Monitoring
            "enable_detailed_monitoring": False,
            "log_retention_days": 7,
            # Security
            "enable_waf": False,
            "enable_shield": False,
        }

        # Environment-specific overrides
        env_configs = {
            "dev": {
                "domain_name": "dev.media-register.com",
                "enable_vpc": False,  # Cost optimization
                "enable_nat_gateway": False,
                "lambda_memory": 256,
                "enable_detailed_monitoring": False,
                "log_retention_days": 3,
                "api_throttle_rate_limit": 10,
                "api_throttle_burst_limit": 20,
            },
            "staging": {
                "domain_name": "staging.media-register.com",
                "enable_vpc": False,  # Cost optimization
                "enable_nat_gateway": False,
                "lambda_memory": 512,
                "enable_point_in_time_recovery": True,
                "enable_detailed_monitoring": True,
                "log_retention_days": 14,
                "api_throttle_rate_limit": 50,
                "api_throttle_burst_limit": 100,
            },
            "prod": {
                "domain_name": "media-register.com",
                "enable_vpc": False,  # Cost optimization
                "enable_nat_gateway": False,
                "max_azs": 0,
                "lambda_memory": 1024,
                "lambda_timeout": 60,
                "dynamodb_billing_mode": "PROVISIONED",
                "dynamodb_read_capacity": 5,
                "dynamodb_write_capacity": 5,
                "enable_point_in_time_recovery": True,
                "enable_detailed_monitoring": True,
                "log_retention_days": 30,
                "cloudfront_price_class": "PriceClass_All",
                "api_throttle_rate_limit": 1000,
                "api_throttle_burst_limit": 2000,
                "enable_waf": True,
                "enable_shield": False,  # Enable for DDoS protection if needed
            },
        }

        # Apply environment-specific config
        if self.environment in env_configs:
            self.base_config.update(env_configs[self.environment])

        # Apply any overrides
        self.base_config.update(self.overrides)

        # Set derived values
        self.base_config["stack_name"] = (
            f"{self.base_config['app_name']}-{self.environment}"
        )
        self.base_config["environment"] = self.environment

        # API and website URLs
        if self.environment == "prod":
            self.base_config["api_domain"] = f"api.{self.base_config['domain_name']}"
            self.base_config["website_domain"] = self.base_config["domain_name"]
        else:
            self.base_config["api_domain"] = f"api.{self.base_config['domain_name']}"
            self.base_config["website_domain"] = self.base_config["domain_name"]

    @property
    def config(self) -> Dict[str, Any]:
        """Get the complete configuration."""
        return self.base_config

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.base_config.get(key, default)

    def get_tags(self) -> Dict[str, str]:
        """Get resource tags."""
        return {
            "Application": self.base_config["app_name"],
            "Environment": self.environment,
            "ManagedBy": "CloudFormation",
            "Project": "MediaRegister",
            "CostCenter": f"media-register-{self.environment}",
        }

    def get_lambda_environment(self) -> Dict[str, str]:
        """Get Lambda environment variables."""
        return {
            "ENVIRONMENT": self.environment,
            "AWS_REGION": self.base_config["aws_region"],
            "DYNAMODB_TABLE": f"{self.base_config['stack_name']}-media",
            "UPLOAD_BUCKET": f"{self.base_config['stack_name']}-uploads",
            "WEBSITE_URL": f"https://{self.base_config['website_domain']}",
            "API_URL": f"https://{self.base_config['api_domain']}",
            "LOG_LEVEL": "DEBUG" if self.environment == "dev" else "INFO",
        }

    def validate(self) -> bool:
        """Validate configuration."""
        required_fields = ["app_name", "aws_region", "environment"]

        for field in required_fields:
            if not self.base_config.get(field):
                print(f"❌ Missing required configuration: {field}")
                return False

        # Validate certificate ARN for production
        if self.environment == "prod" and not self.base_config.get("certificate_arn"):
            print("⚠️ Warning: No certificate ARN provided for production")
            print("   CloudFront will use the default certificate")

        return True
