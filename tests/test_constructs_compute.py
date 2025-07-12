"""
Comprehensive tests for compute constructs module.
Tests Lambda, API Gateway, and compute resource creation.
"""

import pytest
from moto import mock_aws
from troposphere import Template, GetAtt, Ref, Sub
from unittest.mock import Mock, patch, MagicMock

from typing import Any, Dict, List, Optional, Union

from src.constructs.compute import ComputeConstruct


class TestComputeConstruct:
    """Test ComputeConstruct class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template = Template()
        self.environment = "test"
        self.config = {
            "lambda": {
                "runtime": "nodejs20.x",
                "handler": "index.handler",
                "memory_size": 512,
                "timeout": 30,
                "architecture": "arm64",
                "environment_variables": {
                    "TEST_VAR": "test_value"
                }
            },
            "api_gateway": {
                "stage_name": "api",
                "throttle_rate_limit": 10000,
                "throttle_burst_limit": 5000
            },
            "monitoring": {
                "log_retention_days": 7
            }
        }

    @mock_aws
    def test_init_creates_all_resources(self) -> None:
        """Test that initialization creates all required resources."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check that all resources were created
        assert construct.lambda_role is not None
        assert construct.lambda_function is not None
        assert construct.log_group is not None
        assert construct.api is not None
        assert construct.deployment is not None
        assert construct.lambda_permission is not None

        # Check resources dictionary
        assert "lambda_role" in construct.resources
        assert "lambda_function" in construct.resources
        assert "api" in construct.resources
        assert "deployment" in construct.resources

    def test_lambda_role_creation(self) -> None:
        """Test Lambda execution role creation."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check role properties
        role = construct.lambda_role
        assert role.AssumeRolePolicyDocument is not None
        assert "lambda.amazonaws.com" in str(role.AssumeRolePolicyDocument)
        assert len(role.ManagedPolicyArns) >= 1
        assert "AWSLambdaBasicExecutionRole" in str(role.ManagedPolicyArns[0])

    def test_lambda_role_with_dynamodb_tables(self) -> None:
        """Test Lambda role creation with DynamoDB access."""
        dynamodb_tables = {
            "users": "users-table",
            "sessions": "sessions-table"
        }
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment,
            dynamodb_tables=dynamodb_tables
        )

        # Check that DynamoDB policy was added
        role = construct.lambda_role
        assert hasattr(role, 'Policies')
        assert len(role.Policies) == 1
        
        policy = role.Policies[0]
        assert policy.PolicyName == "DynamoDBAccess"
        assert "dynamodb:GetItem" in str(policy.PolicyDocument)
        assert "dynamodb:PutItem" in str(policy.PolicyDocument)

    def test_lambda_function_creation(self) -> None:
        """Test Lambda function creation."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        func = construct.lambda_function
        assert func.Runtime == "nodejs20.x"
        assert func.Handler == "index.handler"
        assert func.MemorySize == 512
        assert func.Timeout == 30
        assert func.Architectures == ["arm64"]
        assert hasattr(func, 'Environment')
        assert "TEST_VAR" in func.Environment.Variables
        assert func.Environment.Variables["TEST_VAR"] == "test_value"

    def test_lambda_function_with_s3_code(self) -> None:
        """Test Lambda function creation with S3 code location."""
        self.config["lambda"]["s3_bucket"] = "my-lambda-bucket"
        self.config["lambda"]["s3_key"] = "lambda-code.zip"
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        func = construct.lambda_function
        assert hasattr(func.Code, 'S3Bucket')
        assert func.Code.S3Bucket == "my-lambda-bucket"
        assert func.Code.S3Key == "lambda-code.zip"

    def test_lambda_function_with_reserved_concurrent(self) -> None:
        """Test Lambda function with reserved concurrent executions."""
        self.config["lambda"]["reserved_concurrent_executions"] = 10
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        func = construct.lambda_function
        assert hasattr(func, 'ReservedConcurrentExecutions')
        assert func.ReservedConcurrentExecutions == 10

    def test_log_group_creation(self) -> None:
        """Test CloudWatch log group creation."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        log_group = construct.log_group
        assert log_group.RetentionInDays == 7
        assert isinstance(log_group.LogGroupName, Sub)

    def test_api_gateway_creation(self) -> None:
        """Test API Gateway REST API creation."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check API properties
        api = construct.api
        assert api.EndpointConfiguration.Types == ["REGIONAL"]
        assert hasattr(api, 'Tags')

        # Check proxy resource and methods
        assert construct.proxy_resource is not None
        assert construct.proxy_method is not None
        assert construct.root_method is not None

    def test_api_gateway_with_throttling(self) -> None:
        """Test API Gateway with throttling configuration."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should create separate stage due to throttling config
        assert hasattr(construct, 'stage')
        stage = construct.stage
        assert stage.StageName == "api"
        assert len(stage.MethodSettings) == 1
        assert stage.MethodSettings[0].ThrottlingRateLimit == 10000
        assert stage.MethodSettings[0].ThrottlingBurstLimit == 5000

    def test_api_gateway_without_throttling(self) -> None:
        """Test API Gateway without throttling configuration."""
        # Remove throttling config
        del self.config["api_gateway"]["throttle_rate_limit"]
        del self.config["api_gateway"]["throttle_burst_limit"]
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should not create separate stage
        assert not hasattr(construct, 'stage')
        # Deployment should have inline stage
        assert construct.deployment.StageName == "api"

    def test_lambda_permission_creation(self) -> None:
        """Test Lambda permission for API Gateway."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        permission = construct.lambda_permission
        assert permission.Action == "lambda:InvokeFunction"
        assert permission.Principal == "apigateway.amazonaws.com"
        assert isinstance(permission.FunctionName, Ref)

    def test_outputs_creation(self) -> None:
        """Test CloudFormation outputs creation."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Get outputs from template
        outputs = self.template.outputs
        
        # Check that all expected outputs exist
        assert "LambdaFunctionArn" in outputs
        assert "LambdaFunctionName" in outputs
        assert "APIGatewayRestApiId" in outputs
        assert "APIGatewayUrl" in outputs

        # Check output properties
        for output_name, output in outputs.items():
            assert hasattr(output, 'Export')
            assert hasattr(output, 'Description')

    def test_get_api_endpoint(self) -> None:
        """Test get_api_endpoint method."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        endpoint = construct.get_api_endpoint()
        assert isinstance(endpoint, Sub)
        assert "execute-api" in str(endpoint)
        assert "/api" in str(endpoint)

    def test_get_lambda_function_arn(self) -> None:
        """Test get_lambda_function_arn method."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        arn = construct.get_lambda_function_arn()
        assert isinstance(arn, GetAtt)

    def test_get_api_gateway_id(self) -> None:
        """Test get_api_gateway_id method."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        api_id = construct.get_api_gateway_id()
        assert isinstance(api_id, Ref)

    def test_environment_variables_with_dynamodb(self) -> None:
        """Test environment variables include DynamoDB table names."""
        dynamodb_tables = {
            "users": "my-users-table",
            "sessions": "my-sessions-table"
        }
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment,
            dynamodb_tables=dynamodb_tables
        )

        func = construct.lambda_function
        env_vars = func.Environment.Variables
        
        # Check standard env vars
        assert env_vars["ENVIRONMENT"] == self.environment
        assert isinstance(env_vars["REGION"], Ref)
        assert isinstance(env_vars["STACK_NAME"], Ref)
        
        # Check DynamoDB table env vars
        assert env_vars["USERS_TABLE"] == "my-users-table"
        assert env_vars["SESSIONS_TABLE"] == "my-sessions-table"

    def test_vpc_config_always_none(self) -> None:
        """Test that VPC config is always None for cost optimization."""
        vpc_config = {"subnet_ids": ["subnet-123"], "security_group_ids": ["sg-123"]}
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment,
            vpc_config=vpc_config
        )

        # VPC config should be ignored
        assert construct.vpc_config is None
        func = construct.lambda_function
        assert not hasattr(func, 'VpcConfig')

    def test_lambda_dependencies(self) -> None:
        """Test Lambda function dependencies."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        func = construct.lambda_function
        assert func.DependsOn == "LambdaLogGroup"

    def test_api_deployment_dependencies(self) -> None:
        """Test API deployment dependencies."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        deployment = construct.deployment
        assert "ProxyMethod" in deployment.DependsOn
        assert "RootMethod" in deployment.DependsOn

    def test_construct_with_minimal_config(self) -> None:
        """Test construct with minimal configuration."""
        minimal_config = {}
        
        construct = ComputeConstruct(
            self.template,
            minimal_config,
            self.environment
        )

        # Should use defaults
        func = construct.lambda_function
        assert func.Runtime == "nodejs20.x"
        assert func.Handler == "index.handler"
        assert func.MemorySize == 512
        assert func.Timeout == 30
        assert func.Architectures == ["arm64"]

    def test_construct_with_different_stage_name(self) -> None:
        """Test construct with custom stage name."""
        self.config["api_gateway"]["stage_name"] = "v1"
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check stage name in various places
        if hasattr(construct, 'stage'):
            assert construct.stage.StageName == "v1"
        else:
            assert construct.deployment.StageName == "v1"

    def test_lambda_code_placeholder(self) -> None:
        """Test Lambda function with placeholder code."""
        # No S3 config
        if "s3_bucket" in self.config["lambda"]:
            del self.config["lambda"]["s3_bucket"]
        if "s3_key" in self.config["lambda"]:
            del self.config["lambda"]["s3_key"]
        
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        func = construct.lambda_function
        assert hasattr(func.Code, 'ZipFile')
        assert "Hello from Lambda" in func.Code.ZipFile

    def test_tags_on_resources(self) -> None:
        """Test that all resources have appropriate tags."""
        construct = ComputeConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check Lambda role tags
        assert hasattr(construct.lambda_role, 'Tags')
        
        # Check Lambda function tags
        assert hasattr(construct.lambda_function, 'Tags')
        
        # Check API Gateway tags
        assert hasattr(construct.api, 'Tags')
        
        # Check stage tags if exists
        if hasattr(construct, 'stage'):
            assert hasattr(construct.stage, 'Tags')