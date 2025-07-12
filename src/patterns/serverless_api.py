"""
Serverless API pattern using Lambda + API Gateway + DynamoDB.

This L3 pattern creates a complete serverless API infrastructure with:
- Lambda functions in VPC
- API Gateway REST API
- DynamoDB tables
- Proper networking and security
- Cost-optimized options
"""

import json
from typing import Any, Dict, List, Optional

from troposphere import Export, GetAtt, Output, Ref, Sub, Template
from typing import Union

from constructs import (
    ComputeConstruct,
    CostOptimizedNetworkConstruct,
    NetworkConstruct,
    StorageConstruct,
)


class ServerlessAPIPattern:
    """
    L3 Pattern for a complete serverless API.

    Creates a production-ready serverless API with Lambda, API Gateway,
    and DynamoDB, properly configured with networking and security.
    """

    def __init__(
        self, template: Template, config: Dict[str, Any], environment: str = "dev"
    ):
        """
        Initialize serverless API pattern.

        Args:
            template: CloudFormation template to add resources to
            config: Pattern configuration
            environment: Deployment environment
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.resources: Dict[str, Any] = {}

        # Extract configuration sections
        self.network_config = config.get("network", {})
        self.compute_config = config.get("compute", {})
        self.storage_config = config.get("storage", {})
        self.pattern_config = config.get("pattern", {})

        # Build the pattern
        self._create_infrastructure()

    def _create_infrastructure(self) -> None:
        """Create all infrastructure components."""
        # 1. Create network infrastructure
        self._create_network()

        # 2. Create storage infrastructure
        self._create_storage()

        # 3. Create compute infrastructure with VPC and storage integration
        self._create_compute()

        # 4. Create pattern-specific outputs
        self._create_pattern_outputs()

    def _create_network(self) -> None:
        """Create network infrastructure based on configuration."""
        # Use cost-optimized network for non-production environments
        use_cost_optimized = (
            self.pattern_config.get("cost_optimized", True)
            and self.environment != "prod"
        )

        if use_cost_optimized:
            self.network = CostOptimizedNetworkConstruct(
                template=self.template,
                config=self.network_config,
                environment=self.environment,
            )
        else:
            self.network = NetworkConstruct(
                template=self.template,
                config=self.network_config,
                environment=self.environment,
            )

        self.resources["network"] = self.network

    def _create_storage(self) -> None:
        """Create storage infrastructure."""
        # Set default DynamoDB configuration if not provided
        if "dynamodb" not in self.storage_config:
            self.storage_config["dynamodb"] = {}

        if "tables" not in self.storage_config["dynamodb"]:
            # Default table configuration
            self.storage_config["dynamodb"]["tables"] = [
                {
                    "name": "main",
                    "partition_key": {"name": "id", "type": "S"},
                    "sort_key": {"name": "sk", "type": "S"},
                    "global_secondary_indexes": [
                        {
                            "name": "GSI1",
                            "partition_key": {"name": "gsi1pk", "type": "S"},
                            "sort_key": {"name": "gsi1sk", "type": "S"},
                            "projection_type": "ALL",
                        }
                    ],
                    "billing_mode": "PAY_PER_REQUEST",
                    "point_in_time_recovery": True,
                    "encryption": True,
                }
            ]

        # Create storage resources
        self.storage = StorageConstruct(
            template=self.template,
            config=self.storage_config,
            environment=self.environment,
        )

        self.resources["storage"] = self.storage

    def _create_compute(self) -> None:
        """Create compute infrastructure with VPC and storage integration."""
        # Prepare VPC configuration for Lambda
        vpc_config: Optional[Dict[str, Any]] = None
        if self.pattern_config.get("lambda_in_vpc", True):
            vpc_config = {
                "subnet_ids": self.network.get_lambda_subnet_ids(),
                "security_group_ids": [self.network.get_lambda_security_group_id()],
            }

        # Get DynamoDB table references
        dynamodb_tables = self.storage.get_table_names()

        # Set default Lambda configuration if not provided
        if "lambda" not in self.compute_config:
            self.compute_config["lambda"] = {}

        # Apply pattern defaults
        lambda_defaults = {
            "runtime": "nodejs20.x",
            "memory_size": 512,
            "timeout": 30,
            "architecture": "arm64",
            "environment_variables": {},
        }

        for key, value in lambda_defaults.items():
            if key not in self.compute_config["lambda"]:
                self.compute_config["lambda"][key] = value

        # Add API configuration defaults
        if "api_gateway" not in self.compute_config:
            self.compute_config["api_gateway"] = {}

        api_defaults = {
            "stage_name": "api",
            "throttle_rate_limit": 10000,
            "throttle_burst_limit": 5000,
        }

        for key, value in api_defaults.items():
            if key not in self.compute_config["api_gateway"]:
                self.compute_config["api_gateway"][key] = value

        # Create compute resources
        self.compute = ComputeConstruct(
            template=self.template,
            config=self.compute_config,
            environment=self.environment,
            vpc_config=vpc_config,
            dynamodb_tables=dynamodb_tables,
        )

        self.resources["compute"] = self.compute

    def _create_pattern_outputs(self) -> None:
        """Create pattern-specific outputs."""
        # API endpoint output
        self.template.add_output(
            Output(
                "APIEndpoint",
                Value=self.compute.get_api_endpoint(),
                Description="API Gateway endpoint URL",
                Export=Export(Sub(f"${{AWS::StackName}}-api-endpoint")),
            )
        )

        # Lambda function ARN
        self.template.add_output(
            Output(
                "LambdaFunctionArn",
                Value=self.compute.get_lambda_function_arn(),
                Description="Lambda function ARN",
                Export=Export(Sub(f"${{AWS::StackName}}-lambda-arn")),
            )
        )

        # Main DynamoDB table name
        table_names = self.storage.get_table_names()
        if "main" in table_names:
            self.template.add_output(
                Output(
                    "MainTableName",
                    Value=table_names["main"],
                    Description="Main DynamoDB table name",
                    Export=Export(Sub(f"${{AWS::StackName}}-main-table")),
                )
            )

        # Pattern summary output
        pattern_summary = {
            "type": "serverless-api",
            "environment": self.environment,
            "lambda_in_vpc": self.pattern_config.get("lambda_in_vpc", True),
            "cost_optimized": self.pattern_config.get("cost_optimized", True)
            and self.environment != "prod",
        }

        self.template.add_output(
            Output(
                "PatternSummary",
                Value=Sub(json.dumps(pattern_summary)),
                Description="Pattern configuration summary",
            )
        )

    def get_api_endpoint(self) -> Sub:
        """Get the API Gateway endpoint URL."""
        return self.compute.get_api_endpoint()

    def get_lambda_function_arn(self) -> GetAtt:
        """Get the Lambda function ARN."""
        return self.compute.get_lambda_function_arn()

    def get_table_names(self) -> Dict[str, Any]:
        """Get DynamoDB table names."""
        return self.storage.get_table_names()  # type: ignore[no-any-return]

    def get_resources(self) -> Dict[str, Any]:
        """Get all pattern resources."""
        return self.resources

    @staticmethod
    def get_default_config(environment: str = "dev") -> Dict[str, Any]:
        """
        Get default configuration for the pattern.

        Args:
            environment: Deployment environment

        Returns:
            Default configuration dictionary
        """
        return {
            "pattern": {"lambda_in_vpc": True, "cost_optimized": environment != "prod"},
            "network": {
                "vpc": {
                    "cidr": "10.0.0.0/16",
                    "max_azs": 2 if environment != "prod" else 3,
                    "enable_dns": True,
                    "enable_dns_hostnames": True,
                    "require_nat": environment == "prod",
                },
                "subnets": {
                    "public": [
                        {"cidr": "10.0.1.0/24", "name": "public-1"},
                        {"cidr": "10.0.2.0/24", "name": "public-2"},
                        {"cidr": "10.0.3.0/24", "name": "public-3"},
                    ],
                    "private": [
                        {"cidr": "10.0.11.0/24", "name": "private-1"},
                        {"cidr": "10.0.12.0/24", "name": "private-2"},
                        {"cidr": "10.0.13.0/24", "name": "private-3"},
                    ],
                },
                "vpc_endpoints": {"dynamodb": True, "s3": True},
                "cost_optimization": {"single_nat_gateway": environment != "prod"},
            },
            "compute": {
                "lambda": {
                    "runtime": "nodejs20.x",
                    "memory_size": 512 if environment != "prod" else 1024,
                    "timeout": 30,
                    "architecture": "arm64",
                    "reserved_concurrent_executions": (
                        None if environment != "prod" else 100
                    ),
                    "environment_variables": {
                        "LOG_LEVEL": "debug" if environment == "dev" else "info"
                    },
                },
                "api_gateway": {
                    "stage_name": "api",
                    "throttle_rate_limit": 10000,
                    "throttle_burst_limit": 5000,
                },
                "monitoring": {"log_retention_days": 7 if environment == "dev" else 30},
            },
            "storage": {
                "dynamodb": {
                    "tables": [
                        {
                            "name": "main",
                            "partition_key": {"name": "id", "type": "S"},
                            "sort_key": {"name": "sk", "type": "S"},
                            "global_secondary_indexes": [
                                {
                                    "name": "GSI1",
                                    "partition_key": {"name": "gsi1pk", "type": "S"},
                                    "sort_key": {"name": "gsi1sk", "type": "S"},
                                    "projection_type": "ALL",
                                }
                            ],
                            "billing_mode": "PAY_PER_REQUEST",
                            "point_in_time_recovery": environment == "prod",
                            "encryption": True,
                            "stream_view_type": (
                                "NEW_AND_OLD_IMAGES" if environment == "prod" else None
                            ),
                        }
                    ]
                }
            },
        }

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """
        Validate pattern configuration.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required sections
        required_sections = ["pattern", "network", "compute", "storage"]
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required configuration section: {section}")

        # Validate pattern configuration
        if "pattern" in config:
            pattern = config["pattern"]
            if not isinstance(pattern.get("lambda_in_vpc", True), bool):
                errors.append("pattern.lambda_in_vpc must be a boolean")
            if not isinstance(pattern.get("cost_optimized", True), bool):
                errors.append("pattern.cost_optimized must be a boolean")

        # Validate network configuration
        if "network" in config:
            network = config["network"]
            if "vpc" in network:
                vpc = network["vpc"]
                if "cidr" in vpc:
                    # Basic CIDR validation
                    cidr = vpc["cidr"]
                    if not isinstance(cidr, str) or "/" not in cidr:
                        errors.append("network.vpc.cidr must be a valid CIDR block")

        # Validate compute configuration
        if "compute" in config:
            compute = config["compute"]
            if "lambda" in compute:
                lambda_config = compute["lambda"]
                valid_runtimes = [
                    "nodejs18.x",
                    "nodejs20.x",
                    "python3.11",
                    "python3.12",
                ]
                if lambda_config.get("runtime") not in valid_runtimes:
                    errors.append(
                        f"compute.lambda.runtime must be one of: {valid_runtimes}"
                    )

                if "memory_size" in lambda_config:
                    memory = lambda_config["memory_size"]
                    if not isinstance(memory, int) or memory < 128 or memory > 10240:
                        errors.append(
                            "compute.lambda.memory_size must be between 128 and 10240"
                        )

        return errors
