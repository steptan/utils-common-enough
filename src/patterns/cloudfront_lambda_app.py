"""CloudFront + Lambda application pattern."""

import json
import os
from typing import Any, Dict, Optional

from troposphere import Export, GetAtt, Join, Output, Ref, Sub, Template, cloudformation

from config import ProjectConfig
from constructs.compute import ComputeConstruct
from constructs.distribution import DistributionConstruct
from constructs.network import NetworkConstruct
from constructs.storage import StorageConstruct


class CloudFrontLambdaAppPattern:
    """
    Complete serverless application pattern with:
    - VPC with proper networking
    - Lambda function with API Gateway
    - DynamoDB table
    - CloudFront distribution
    - S3 buckets for static assets
    """

    def __init__(self, config: ProjectConfig, environment: str):
        """Initialize the pattern.

        Args:
            config: Project configuration
            environment: Deployment environment (dev, staging, prod)
        """
        self.config = config
        self.environment = environment
        self.template = Template()
        self.template.set_version("2010-09-09")
        self.template.set_description(
            f"{config.display_name} - {environment.upper()} Environment"
        )

        # Build the infrastructure
        self._build()

    def _build(self):
        """Build the complete infrastructure."""
        # Prepare configurations
        network_config = {
            "vpc": {
                "cidr": "10.0.0.0/16",
                "enable_dns": True,
                "enable_dns_hostnames": True,
                "max_azs": 2,
                "require_nat": False,  # No NAT needed - Lambda only accesses DynamoDB via VPC endpoints
            },
            "subnets": {
                "public": [
                    {"cidr": "10.0.1.0/24", "name": "public-1"},
                    {"cidr": "10.0.2.0/24", "name": "public-2"},
                ],
                "private": [
                    {"cidr": "10.0.10.0/24", "name": "private-1"},
                    {"cidr": "10.0.11.0/24", "name": "private-2"},
                ],
            },
            "cost_optimization": {
                "single_nat_gateway": True  # Use single NAT Gateway for cost savings
            },
            "vpc_endpoints": {"s3": True, "dynamodb": True},
        }

        storage_config = {
            "dynamodb": {
                "tables": [
                    {
                        "name": "main",
                        "partition_key": {"name": "id", "type": "S"},
                        "billing_mode": self.config.dynamodb_billing_mode,
                        "point_in_time_recovery": self.config.dynamodb_point_in_time_recovery,
                    }
                ]
            },
            "s3": {
                "buckets": [
                    {"name": "frontend", "versioning": True, "lifecycle_rules": []}
                ]
            },
        }

        compute_config = {
            "lambda": {
                "runtime": self.config.lambda_runtime,
                "memory_size": self.config.lambda_memory,
                "timeout": self.config.lambda_timeout,
                "handler": getattr(self.config, "lambda_handler", "index.handler"),
                "environment_variables": {
                    "ENVIRONMENT": self.environment,
                    "TABLE_NAME": f"{self.config.name}-{self.environment}-main",
                },
                "s3_bucket": os.environ.get("LAMBDA_S3_BUCKET", ""),
                "s3_key": os.environ.get("LAMBDA_S3_KEY", ""),
            },
            "api_gateway": {
                "stage_name": self.config.api_stage_name,
                "throttle_rate_limit": self.config.api_throttle_rate_limit,
                "throttle_burst_limit": self.config.api_throttle_burst_limit,
            },
        }

        distribution_config = {
            "cloudfront": {
                "price_class": self.config.cloudfront_price_class,
                "default_ttl": self.config.cloudfront_default_ttl,
                "max_ttl": self.config.cloudfront_max_ttl,
                "min_ttl": self.config.cloudfront_min_ttl,
                "enable_waf": self.config.enable_waf,
            }
        }

        # Create constructs
        network = NetworkConstruct(self.template, network_config, self.environment)
        storage = StorageConstruct(self.template, storage_config, self.environment)

        # Get VPC outputs for compute
        # Note: Lambda doesn't need VPC access since it only uses AWS services
        # This avoids NAT Gateway costs and reduces cold starts
        vpc_config = None

        # Get DynamoDB outputs for compute
        main_table = storage.resources.get("table_main")
        dynamodb_tables = {}
        if main_table:
            dynamodb_tables["main"] = Ref(main_table)

        compute = ComputeConstruct(
            self.template,
            compute_config,
            self.environment,
            vpc_config=vpc_config,
            dynamodb_tables=dynamodb_tables,
        )

        # Get API Gateway outputs
        api_gateway = compute.resources.get("api_gateway")
        api_domain_name = None
        api_stage = self.config.api_stage_name

        if api_gateway:
            # Construct the API Gateway domain name
            api_domain_name = Join(
                "",
                [
                    Ref(api_gateway),
                    ".execute-api.",
                    Ref("AWS::Region"),
                    ".amazonaws.com",
                ],
            )

        # Pass the frontend bucket from storage to distribution
        frontend_bucket = storage.resources.get("bucket_frontend")

        distribution = DistributionConstruct(
            self.template,
            distribution_config,
            self.environment,
            api_domain_name=api_domain_name,
            api_stage=api_stage,
            s3_bucket=frontend_bucket,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return json.loads(self.template.to_json())

    def to_yaml(self) -> str:
        """Convert template to YAML."""
        return self.template.to_yaml()

    def to_json(self) -> str:
        """Convert template to JSON."""
        return self.template.to_json()
