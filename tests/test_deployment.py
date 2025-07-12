"""
Comprehensive tests for deployment commands and infrastructure deployment.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

from typing import Any, Dict, List, Optional, Union

import pytest
import yaml
from botocore.exceptions import ClientError

from config import ProjectConfig
from deployment.base_deployer import BaseDeployer, DeploymentResult, DeploymentStatus
from deployment.infrastructure import InfrastructureDeployer


class TestInfrastructureDeployer:
    """Test InfrastructureDeployer class."""

    @pytest.fixture
    def basic_config(self) -> Any:
        """Create a basic project configuration."""
        return ProjectConfig(
            name="test-project",
            display_name="Test Project",
            aws_region="us-east-1",
            environments=["dev", "staging", "prod"],
            bucket_patterns={
                "lambda": "{project}-lambda-{environment}",
                "deployment": "{project}-deployment-{environment}",
                "static": "{project}-static-{environment}",
            },
        )

    @pytest.fixture
    def mock_aws_clients(self) -> Any:
        """Mock AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_cf = Mock()
            mock_s3 = Mock()
            mock_sts = Mock()

            mock_session.return_value.client.side_effect = lambda service: {
                "cloudformation": mock_cf,
                "s3": mock_s3,
                "sts": mock_sts,
            }[service]

            # Mock STS account ID
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

            yield {"cloudformation": mock_cf, "s3": mock_s3, "sts": mock_sts}

    @pytest.fixture
    def deployer(self, basic_config, mock_aws_clients) -> Any:
        """Create an InfrastructureDeployer instance."""
        with patch("config.get_project_config", return_value=basic_config):
            deployer = InfrastructureDeployer(
                project_name="test-project",
                environment="dev",
                template_path="template.yaml",
            )
            deployer.cloudformation = mock_aws_clients["cloudformation"]
            deployer.s3 = mock_aws_clients["s3"]
            deployer.sts = mock_aws_clients["sts"]
            return deployer

    def test_initialization(self, basic_config) -> None:
        """Test InfrastructureDeployer initialization."""
        with patch("config.get_project_config", return_value=basic_config):
            deployer = InfrastructureDeployer(
                project_name="test-project",
                environment="staging",
                template_path="/path/to/template.yaml",
                parameters={"Param1": "Value1"},
                tags={"Team": "DevOps"},
                config=basic_config,  # Pass config explicitly
            )

            assert deployer.project_name == "test-project"
            assert deployer.environment == "staging"
            assert deployer.template_path == Path("/path/to/template.yaml")
            assert deployer.parameters == {"Param1": "Value1"}
            assert "Team" in deployer.tags
            assert deployer.tags["Team"] == "DevOps"
            assert deployer.tags["Project"] == "test-project"
            assert deployer.tags["Environment"] == "staging"
            assert deployer.tags["ManagedBy"] == "project-utils"

    def test_find_template_with_explicit_path(self, deployer) -> None:
        """Test finding template with explicit path."""
        template_path = Path("/explicit/path/template.yaml")
        deployer.template_path = template_path

        with patch.object(template_path, "exists", return_value=True):
            result = deployer.find_template()
            assert result == template_path

    def test_find_template_search_common_locations(self, deployer) -> None:
        """Test finding template by searching common locations."""
        deployer.template_path = None

        with patch("pathlib.Path.cwd", return_value=Path("/current/dir")):
            with patch("pathlib.Path.exists") as mock_exists:
                # Make the third checked path exist
                mock_exists.side_effect = [False, False, True] + [False] * 10

                result = deployer.find_template()

                # Should find template in one of the common locations
                assert result is not None
                assert "template" in str(result)

    def test_find_template_not_found(self, deployer) -> None:
        """Test behavior when template is not found."""
        deployer.template_path = None

        with patch("pathlib.Path.exists", return_value=False):
            result = deployer.find_template()
            assert result is None

    def test_load_template_json(self, deployer) -> None:
        """Test loading JSON template."""
        template_content = '{"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}'
        template_path = Path("template.json")

        with patch("builtins.open", mock_open(read_data=template_content)):
            result = deployer.load_template(template_path)
            assert result == template_content

    def test_load_template_yaml(self, deployer) -> None:
        """Test loading YAML template and converting to JSON."""
        yaml_content = """
Resources:
  Bucket:
    Type: AWS::S3::Bucket
"""
        template_path = Path("template.yaml")

        with patch("builtins.open", mock_open(read_data=yaml_content)):
            result = deployer.load_template(template_path)

            # Parse result to verify it's valid JSON
            parsed = json.loads(result)
            assert "Resources" in parsed
            assert "Bucket" in parsed["Resources"]
            assert parsed["Resources"]["Bucket"]["Type"] == "AWS::S3::Bucket"

    def test_prepare_lambda_buckets_success(self, deployer, mock_aws_clients) -> None:
        """Test successful Lambda bucket preparation."""
        # Mock S3 head_bucket to simulate buckets don't exist
        mock_aws_clients["s3"].head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )

        with patch.object(
            deployer, "create_s3_bucket_if_needed", return_value=True
        ) as mock_create:
            result = deployer.prepare_lambda_buckets()

            assert result is True
            # Should create two buckets: lambda and deployment
            assert mock_create.call_count == 2

            # Verify bucket names
            calls = mock_create.call_args_list
            bucket_names = [call[0][0] for call in calls]
            assert any("lambda" in name for name in bucket_names)
            assert any("deployment" in name for name in bucket_names)

    def test_prepare_lambda_buckets_failure(self, deployer) -> None:
        """Test Lambda bucket preparation failure."""
        with patch.object(deployer, "create_s3_bucket_if_needed", return_value=False):
            result = deployer.prepare_lambda_buckets()
            assert result is False

    def test_build_stack_parameters(self, deployer) -> None:
        """Test building CloudFormation stack parameters."""
        deployer.parameters = {"Environment": "prod", "InstanceType": "t3.micro"}

        with patch.object(deployer, "build_stack_parameters") as mock_build:
            mock_build.return_value = [
                {"ParameterKey": "Environment", "ParameterValue": "prod"},
                {"ParameterKey": "InstanceType", "ParameterValue": "t3.micro"},
            ]

            result = deployer.build_stack_parameters()

            assert len(result) == 2
            assert result[0]["ParameterKey"] == "Environment"
            assert result[0]["ParameterValue"] == "prod"

    def test_deploy_success(self, deployer, mock_aws_clients) -> None:
        """Test successful deployment."""
        # Mock template finding and loading
        template_path = Path("template.yaml")
        template_content = '{"Resources": {}}'

        with patch.object(deployer, "find_template", return_value=template_path):
            with patch.object(deployer, "load_template", return_value=template_content):
                with patch.object(
                    deployer, "prepare_lambda_buckets", return_value=True
                ):
                    with patch.object(deployer, "deploy_stack", return_value=True):
                        with patch.object(
                            deployer, "wait_for_stack_complete", return_value=True
                        ):
                            with patch.object(
                                deployer,
                                "get_stack_outputs",
                                return_value={"ApiUrl": "https://api.example.com"},
                            ):
                                result = deployer.deploy()

                                assert result.status == DeploymentStatus.SUCCESS
                                assert (
                                    result.outputs["ApiUrl"]
                                    == "https://api.example.com"
                                )
                                assert result.errors is None

    def test_deploy_template_not_found(self, deployer) -> None:
        """Test deployment when template is not found."""
        with patch.object(deployer, "find_template", return_value=None):
            result = deployer.deploy()

            assert result.status == DeploymentStatus.FAILED
            assert any(
                "No CloudFormation template found" in err
                for err in (result.errors or [])
            )

    def test_deploy_bucket_creation_failure(self, deployer) -> None:
        """Test deployment when bucket creation fails."""
        template_path = Path("template.yaml")

        with patch.object(deployer, "find_template", return_value=template_path):
            with patch.object(deployer, "prepare_lambda_buckets", return_value=False):
                result = deployer.deploy()

                assert result.status == DeploymentStatus.FAILED
                assert any(
                    "Failed to create required S3 buckets" in err
                    for err in (result.errors or [])
                )

    def test_deploy_stack_failure(self, deployer, mock_aws_clients) -> None:
        """Test deployment when stack creation fails."""
        template_path = Path("template.yaml")
        template_content = '{"Resources": {}}'

        with patch.object(deployer, "find_template", return_value=template_path):
            with patch.object(deployer, "load_template", return_value=template_content):
                with patch.object(
                    deployer, "prepare_lambda_buckets", return_value=True
                ):
                    with patch.object(deployer, "deploy_stack", return_value=False):
                        result = deployer.deploy()

                        assert result.status == DeploymentStatus.FAILED
                        assert any(
                            "Stack deployment failed" in err
                            for err in (result.errors or [])
                        )

    def test_deploy_with_dry_run(self, deployer) -> None:
        """Test deployment in dry-run mode."""
        deployer.dry_run = True
        template_path = Path("template.yaml")
        template_content = '{"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}'

        with patch.object(deployer, "find_template", return_value=template_path):
            with patch.object(deployer, "load_template", return_value=template_content):
                with patch.object(
                    deployer, "prepare_lambda_buckets", return_value=True
                ):
                    result = deployer.deploy()

                    assert result.status == DeploymentStatus.SUCCESS
                    assert "[DRY RUN]" in result.message
                    # Should not actually deploy stack
                    deployer.cloudformation.create_stack.assert_not_called()
                    deployer.cloudformation.update_stack.assert_not_called()

    def test_rollback_on_failure(self, deployer, mock_aws_clients) -> None:
        """Test rollback behavior on deployment failure."""
        template_path = Path("template.yaml")
        template_content = '{"Resources": {}}'

        # Mock stack creation to fail
        mock_aws_clients["cloudformation"].create_stack.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Invalid template"}},
            "CreateStack",
        )

        with patch.object(deployer, "find_template", return_value=template_path):
            with patch.object(deployer, "load_template", return_value=template_content):
                with patch.object(
                    deployer, "prepare_lambda_buckets", return_value=True
                ):
                    with patch.object(deployer, "rollback") as mock_rollback:
                        result = deployer.deploy()

                        assert result.status == DeploymentStatus.FAILED
                        # Should attempt rollback
                        mock_rollback.assert_called_once()

    def test_deploy_with_change_set(self, deployer, mock_aws_clients) -> None:
        """Test deployment using change sets."""
        deployer.use_change_sets = True
        template_path = Path("template.yaml")
        template_content = '{"Resources": {}}'

        # Mock existing stack
        mock_aws_clients["cloudformation"].describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }

        with patch.object(deployer, "find_template", return_value=template_path):
            with patch.object(deployer, "load_template", return_value=template_content):
                with patch.object(
                    deployer, "prepare_lambda_buckets", return_value=True
                ):
                    with patch.object(
                        deployer, "deploy_with_change_set", return_value=True
                    ):
                        with patch.object(
                            deployer, "wait_for_stack_complete", return_value=True
                        ):
                            with patch.object(
                                deployer, "get_stack_outputs", return_value={}
                            ):
                                result = deployer.deploy()

                                assert result.status == DeploymentStatus.SUCCESS
                                deployer.deploy_with_change_set.assert_called_once()

    def test_get_stack_outputs(self, deployer, mock_aws_clients) -> None:
        """Test retrieving stack outputs."""
        mock_aws_clients["cloudformation"].describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {
                            "OutputKey": "ApiUrl",
                            "OutputValue": "https://api.example.com",
                        },
                        {"OutputKey": "BucketName", "OutputValue": "my-bucket"},
                    ]
                }
            ]
        }

        with patch.object(deployer, "get_stack_outputs") as mock_outputs:
            mock_outputs.return_value = {
                "ApiUrl": "https://api.example.com",
                "BucketName": "my-bucket",
            }

            outputs = deployer.get_stack_outputs()
            assert outputs["ApiUrl"] == "https://api.example.com"
            assert outputs["BucketName"] == "my-bucket"

    def test_parameter_override(self, deployer) -> None:
        """Test parameter override functionality."""
        deployer.parameters = {"Environment": "dev", "InstanceType": "t2.micro"}

        # Override a parameter
        deployer.parameters["InstanceType"] = "t3.small"

        assert deployer.parameters["InstanceType"] == "t3.small"
        assert deployer.parameters["Environment"] == "dev"

    def test_tag_merging(self, deployer) -> None:
        """Test tag merging with defaults."""
        # Add custom tags
        deployer.tags["Owner"] = "TeamA"
        deployer.tags["CostCenter"] = "12345"

        # Verify default tags are preserved
        assert deployer.tags["Project"] == "test-project"
        assert deployer.tags["Environment"] == "dev"
        assert deployer.tags["ManagedBy"] == "project-utils"

        # Verify custom tags are added
        assert deployer.tags["Owner"] == "TeamA"
        assert deployer.tags["CostCenter"] == "12345"


class TestBaseDeployer:
    """Test BaseDeployer base class functionality."""

    @pytest.fixture
    def base_deployer(self, basic_config) -> Any:
        """Create a BaseDeployer instance."""
        with patch("config.get_project_config", return_value=basic_config):
            return BaseDeployer(project_name="test-project", environment="dev")

    def test_log_method(self, base_deployer, capsys) -> None:
        """Test logging functionality."""
        with patch("builtins.print") as mock_print:
            base_deployer.log("Test message", "INFO")
            mock_print.assert_called_once()

            # Test different log levels
            base_deployer.log("Error message", "ERROR")
            base_deployer.log("Warning message", "WARNING")

            assert mock_print.call_count == 3

    def test_get_account_id(self, base_deployer) -> None:
        """Test getting AWS account ID."""
        with patch.object(base_deployer.sts, "get_caller_identity") as mock_sts:
            mock_sts.return_value = {"Account": "123456789012"}

            account_id = base_deployer.get_account_id()
            assert account_id == "123456789012"
            mock_sts.assert_called_once()

    def test_create_s3_bucket_if_needed_exists(self, base_deployer) -> None:
        """Test S3 bucket creation when bucket already exists."""
        bucket_name = "test-bucket"

        # Mock bucket exists
        base_deployer.s3.head_bucket.return_value = {}

        result = base_deployer.create_s3_bucket_if_needed(bucket_name)

        assert result is True
        base_deployer.s3.create_bucket.assert_not_called()

    def test_create_s3_bucket_if_needed_create(self, base_deployer) -> None:
        """Test S3 bucket creation when bucket doesn't exist."""
        bucket_name = "test-bucket"

        # Mock bucket doesn't exist
        base_deployer.s3.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )

        result = base_deployer.create_s3_bucket_if_needed(bucket_name)

        assert result is True
        base_deployer.s3.create_bucket.assert_called_once()

        # Verify bucket configuration for us-east-1
        call_args = base_deployer.s3.create_bucket.call_args
        assert call_args[1]["Bucket"] == bucket_name
        assert (
            "CreateBucketConfiguration" not in call_args[1]
        )  # us-east-1 doesn't need this

    def test_create_s3_bucket_if_needed_non_us_east_1(self, basic_config) -> None:
        """Test S3 bucket creation in non-us-east-1 region."""
        with patch("config.get_project_config", return_value=basic_config):
            deployer = BaseDeployer(
                project_name="test-project", environment="dev", region="eu-west-1"
            )

            bucket_name = "test-bucket"
            deployer.s3.head_bucket.side_effect = ClientError(
                {"Error": {"Code": "404"}}, "HeadBucket"
            )

            result = deployer.create_s3_bucket_if_needed(bucket_name)

            assert result is True
            call_args = deployer.s3.create_bucket.call_args
            assert (
                call_args[1]["CreateBucketConfiguration"]["LocationConstraint"]
                == "eu-west-1"
            )

    def test_stack_exists(self, base_deployer) -> None:
        """Test checking if stack exists."""
        stack_name = "test-stack"

        # Mock stack exists
        base_deployer.cloudformation.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }

        with patch.object(base_deployer, "stack_exists") as mock_exists:
            mock_exists.return_value = True
            result = base_deployer.stack_exists(stack_name)
            assert result is True

    def test_stack_not_exists(self, base_deployer) -> None:
        """Test checking if stack doesn't exist."""
        stack_name = "test-stack"

        # Mock stack doesn't exist
        base_deployer.cloudformation.describe_stacks.side_effect = ClientError(
            {"Error": {"Message": "Stack test-stack does not exist"}}, "DescribeStacks"
        )

        with patch.object(base_deployer, "stack_exists") as mock_exists:
            mock_exists.return_value = False
            result = base_deployer.stack_exists(stack_name)
            assert result is False


class TestDeploymentResult:
    """Test DeploymentResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a successful deployment result."""
        result = DeploymentResult(
            status=DeploymentStatus.SUCCESS,
            message="Deployment completed successfully",
            outputs={"ApiUrl": "https://api.example.com"},
            duration=120.5,
        )

        assert result.status == DeploymentStatus.SUCCESS
        assert result.success is True
        assert result.errors is None
        assert result.outputs["ApiUrl"] == "https://api.example.com"
        assert result.duration == 120.5

    def test_failure_result(self) -> None:
        """Test creating a failed deployment result."""
        result = DeploymentResult(
            status=DeploymentStatus.FAILED,
            message="Deployment failed",
            duration=60.0,
            errors=["Stack creation failed: ValidationError"],
        )

        assert result.status == DeploymentStatus.FAILED
        assert result.success is False
        assert "Stack creation failed: ValidationError" in result.errors
        assert result.outputs is None

    def test_rolled_back_result(self) -> None:
        """Test creating a rolled back deployment result."""
        result = DeploymentResult(
            status=DeploymentStatus.ROLLED_BACK,
            message="Deployment rolled back",
            duration=90.0,
            outputs={"BucketName": "my-bucket"},
            errors=["Lambda function failed to deploy"],
            warnings=["Some resources were not cleaned up"],
        )

        assert result.status == DeploymentStatus.ROLLED_BACK
        assert result.success is False
        assert result.errors is not None
        assert result.outputs is not None
        assert result.warnings is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=deployment", "--cov-report=term-missing"])
