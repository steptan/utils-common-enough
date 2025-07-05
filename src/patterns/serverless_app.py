"""Serverless application pattern without VPC for cost optimization."""

from typing import Dict, Any, Optional
from troposphere import Template, Ref, GetAtt, Output, Export, Sub, Join
from troposphere import cloudformation
import json
import os

from config import ProjectConfig
from constructs.compute import ComputeConstruct
from constructs.storage import StorageConstruct
from constructs.distribution import DistributionConstruct


class ServerlessAppPattern:
    """
    Cost-optimized serverless application pattern with:
    - Lambda functions without VPC (no NAT Gateway costs)
    - API Gateway
    - DynamoDB table
    - CloudFront distribution
    - S3 buckets for static assets

    Security is maintained through:
    - IAM roles with least privilege
    - API Gateway throttling
    - WAF integration
    - CloudFront security headers
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
            f"{config.display_name} - {environment.upper()} Environment (No VPC)"
        )

        # Build the infrastructure
        self._build()

    def _build(self):
        """Build the complete infrastructure."""
        # Storage configuration
        storage_config = {
            "tables": {
                "main": {
                    "hash_key": "id",
                    "range_key": None,
                    "billing_mode": self.config.dynamodb_billing_mode,
                    "point_in_time_recovery": self.config.dynamodb_point_in_time_recovery,
                }
            },
            "buckets": {
                "frontend": {"versioning": True, "lifecycle_rules": []},
                "lambda": {"versioning": True, "lifecycle_rules": []},
            },
        }

        # Compute configuration
        compute_config = {
            "lambda": {
                "runtime": self.config.lambda_runtime,
                "memory_size": self.config.lambda_memory,
                "timeout": self.config.lambda_timeout,
                "handler": "index.handler",
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
            "monitoring": {"log_retention_days": self.config.log_retention_days},
        }

        # Distribution configuration
        distribution_config = {
            "cloudfront": {
                "price_class": self.config.cloudfront_price_class,
                "default_ttl": self.config.cloudfront_default_ttl,
                "max_ttl": self.config.cloudfront_max_ttl,
                "min_ttl": self.config.cloudfront_min_ttl,
                "enable_waf": self.config.enable_waf,
            }
        }

        # Create constructs (no network construct needed)
        storage = StorageConstruct(self.template, storage_config, self.environment)

        # Get DynamoDB outputs for compute
        dynamodb_tables = {"main": Ref(storage.resources.get("main_table"))}

        # Create compute without VPC
        compute = ComputeConstruct(
            self.template,
            compute_config,
            self.environment,
            vpc_config=None,  # No VPC for cost optimization
            dynamodb_tables=dynamodb_tables,
        )

        # Get API Gateway outputs
        api_gateway = compute.resources.get("api_gateway")
        api_domain_name = None
        api_stage = self.config.api_stage_name

        if api_gateway:
            # API Gateway domain name format
            api_domain_name = Join(
                "",
                [
                    Ref(api_gateway),
                    ".execute-api.",
                    Ref("AWS::Region"),
                    ".amazonaws.com",
                ],
            )

        # Get S3 bucket outputs
        s3_buckets = {
            "frontend_bucket": storage.resources.get("frontend_bucket"),
            "frontend_bucket_domain": storage.resources.get(
                "frontend_bucket_domain_name"
            ),
        }

        # Create distribution
        distribution = DistributionConstruct(
            self.template,
            distribution_config,
            self.environment,
            s3_bucket=s3_buckets.get("frontend_bucket"),
            api_domain_name=api_domain_name,
            api_stage=api_stage,
        )

        # Add stack outputs
        self._create_outputs(storage, compute, distribution)

    def _create_outputs(self, storage, compute, distribution):
        """Create stack outputs for cross-stack references."""
        # S3 Bucket outputs
        self.template.add_output(
            Output(
                "FrontendBucketName",
                Description="Frontend S3 bucket name",
                Value=Ref(storage.resources.get("frontend_bucket")),
                Export=Export(Sub(f"${{AWS::StackName}}-frontend-bucket")),
            )
        )

        self.template.add_output(
            Output(
                "LambdaBucketName",
                Description="Lambda deployment S3 bucket name",
                Value=Ref(storage.resources.get("lambda_bucket")),
                Export=Export(Sub(f"${{AWS::StackName}}-lambda-bucket")),
            )
        )

        # DynamoDB outputs
        self.template.add_output(
            Output(
                "MainTableName",
                Description="Main DynamoDB table name",
                Value=Ref(storage.resources.get("main_table")),
                Export=Export(Sub(f"${{AWS::StackName}}-main-table")),
            )
        )

    def generate_template(self) -> str:
        """Generate the CloudFormation template."""
        return self.template.to_json()

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return json.loads(self.template.to_json())

    def to_yaml(self) -> str:
        """Convert template to YAML."""
        return self.template.to_yaml()

    def to_json(self) -> str:
        """Convert template to JSON."""
        return self.template.to_json()
