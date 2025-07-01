"""CloudFront + Lambda application pattern."""

from typing import Dict, Any, Optional
from troposphere import Template, Ref, GetAtt, Output, Export, Sub
from troposphere import cloudformation
import json

from config import ProjectConfig
from constructs.network import VPCConstruct
from constructs.compute import LambdaConstruct
from constructs.storage import DynamoDBConstruct
from constructs.distribution import CloudFrontConstruct


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
        # Add parameters
        self._add_parameters()
        
        # Create VPC
        vpc = VPCConstruct(
            name_prefix=f"{self.config.name}-{self.environment}",
            cidr_block="10.0.0.0/16",
            availability_zones=2,
            nat_gateways=1 if self.environment == "prod" else 0,
            enable_flow_logs=self.environment == "prod"
        )
        vpc_resources = vpc.create()
        for resource in vpc_resources:
            self.template.add_resource(resource)
        
        # Create DynamoDB table
        dynamodb = DynamoDBConstruct(
            name_prefix=f"{self.config.name}-{self.environment}",
            hash_key="id",
            billing_mode=self.config.dynamodb_billing_mode,
            point_in_time_recovery=self.config.dynamodb_point_in_time_recovery,
            vpc_id=vpc_resources[0].ref() if vpc_resources else None
        )
        dynamodb_resources = dynamodb.create()
        for resource in dynamodb_resources:
            self.template.add_resource(resource)
        
        # Create Lambda function
        lambda_env = {
            "ENVIRONMENT": self.environment,
            "TABLE_NAME": Ref(dynamodb_resources[0])  # Reference to DynamoDB table
        }
        
        # Get Lambda S3 configuration from environment
        import os
        lambda_s3_bucket = os.environ.get("LAMBDA_S3_BUCKET", "")
        lambda_s3_key = os.environ.get("LAMBDA_S3_KEY", "")
        
        lambda_construct = LambdaConstruct(
            name_prefix=f"{self.config.name}-{self.environment}",
            runtime=self.config.lambda_runtime,
            handler="index.handler",
            memory_size=self.config.lambda_memory,
            timeout=self.config.lambda_timeout,
            environment_variables=lambda_env,
            vpc_id=vpc_resources[0].ref() if vpc_resources else None,
            subnet_ids=[subnet.ref() for subnet in vpc_resources[1:3]] if len(vpc_resources) > 2 else None,
            s3_bucket=lambda_s3_bucket if lambda_s3_bucket else None,
            s3_key=lambda_s3_key if lambda_s3_key else None,
            code_zip_path="lambda-deployment.zip" if not lambda_s3_bucket else None
        )
        lambda_resources = lambda_construct.create()
        for resource in lambda_resources:
            self.template.add_resource(resource)
        
        # Create CloudFront distribution
        cloudfront = CloudFrontConstruct(
            name_prefix=f"{self.config.name}-{self.environment}",
            s3_bucket_name=self.config.get_frontend_bucket(self.environment),
            api_gateway_domain_name=None,  # We'll use Lambda Function URL
            price_class=self.config.cloudfront_price_class,
            default_ttl=self.config.cloudfront_default_ttl,
            max_ttl=self.config.cloudfront_max_ttl,
            allowed_origins=self.config.allowed_origins,
            enable_waf=self.config.enable_waf
        )
        cloudfront_resources = cloudfront.create()
        for resource in cloudfront_resources:
            self.template.add_resource(resource)
        
        # Add outputs
        self._add_outputs(vpc_resources, lambda_resources, dynamodb_resources, cloudfront_resources)
    
    def _add_parameters(self):
        """Add CloudFormation parameters."""
        # Add any parameters your stack needs
        pass
    
    def _add_outputs(self, vpc_resources, lambda_resources, dynamodb_resources, cloudfront_resources):
        """Add CloudFormation outputs."""
        # VPC outputs
        if vpc_resources:
            self.template.add_output(Output(
                "VPCId",
                Description="VPC ID",
                Value=Ref(vpc_resources[0]),
                Export=Export(Sub(f"${{{cloudformation.AWS_STACK_NAME}}}-VPCId"))
            ))
        
        # Lambda outputs
        if lambda_resources:
            self.template.add_output(Output(
                "LambdaFunctionName",
                Description="Lambda function name",
                Value=Ref(lambda_resources[0]),
                Export=Export(Sub(f"${{{cloudformation.AWS_STACK_NAME}}}-LambdaFunctionName"))
            ))
            
            self.template.add_output(Output(
                "LambdaFunctionArn",
                Description="Lambda function ARN",
                Value=GetAtt(lambda_resources[0], "Arn"),
                Export=Export(Sub(f"${{{cloudformation.AWS_STACK_NAME}}}-LambdaFunctionArn"))
            ))
        
        # DynamoDB outputs
        if dynamodb_resources:
            self.template.add_output(Output(
                "DynamoDBTableName",
                Description="DynamoDB table name",
                Value=Ref(dynamodb_resources[0]),
                Export=Export(Sub(f"${{{cloudformation.AWS_STACK_NAME}}}-DynamoDBTableName"))
            ))
        
        # CloudFront outputs
        if cloudfront_resources:
            self.template.add_output(Output(
                "CloudFrontDistributionId",
                Description="CloudFront distribution ID",
                Value=Ref(cloudfront_resources[0]),
                Export=Export(Sub(f"${{{cloudformation.AWS_STACK_NAME}}}-CloudFrontDistributionId"))
            ))
            
            self.template.add_output(Output(
                "CloudFrontDomainName",
                Description="CloudFront distribution domain name",
                Value=GetAtt(cloudfront_resources[0], "DomainName"),
                Export=Export(Sub(f"${{{cloudformation.AWS_STACK_NAME}}}-CloudFrontDomainName"))
            ))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return json.loads(self.template.to_json())
    
    def to_yaml(self) -> str:
        """Convert template to YAML."""
        return self.template.to_yaml()
    
    def to_json(self) -> str:
        """Convert template to JSON."""
        return self.template.to_json()