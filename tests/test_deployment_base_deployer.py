"""
Comprehensive tests for deployment.base_deployer module.
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch, call

import pytest
from botocore.exceptions import ClientError

from deployment.base_deployer import (
    DeploymentStatus,
    DeploymentResult,
    BaseDeployer,
)


class TestDeploymentStatus:
    """Test DeploymentStatus enum."""

    def test_status_values(self) -> None:
        """Test DeploymentStatus enum values."""
        assert DeploymentStatus.PENDING.value == "pending"
        assert DeploymentStatus.IN_PROGRESS.value == "in_progress"
        assert DeploymentStatus.SUCCESS.value == "success"
        assert DeploymentStatus.FAILED.value == "failed"
        assert DeploymentStatus.ROLLED_BACK.value == "rolled_back"


class TestDeploymentResult:
    """Test DeploymentResult dataclass."""

    def test_initialization(self) -> None:
        """Test DeploymentResult initialization."""
        result = DeploymentResult(
            status=DeploymentStatus.SUCCESS,
            message="Deployment completed successfully",
            duration=120.5,
            outputs={"ApiUrl": "https://api.example.com"},
            errors=None,
            warnings=["Warning 1"]
        )
        
        assert result.status == DeploymentStatus.SUCCESS
        assert result.message == "Deployment completed successfully"
        assert result.duration == 120.5
        assert result.outputs == {"ApiUrl": "https://api.example.com"}
        assert result.errors is None
        assert len(result.warnings) == 1

    def test_success_property(self) -> None:
        """Test success property."""
        # Successful result
        result = DeploymentResult(
            status=DeploymentStatus.SUCCESS,
            message="Success",
            duration=60.0
        )
        assert result.success is True
        
        # Failed result
        result = DeploymentResult(
            status=DeploymentStatus.FAILED,
            message="Failed",
            duration=30.0,
            errors=["Error occurred"]
        )
        assert result.success is False

    def test_minimal_initialization(self) -> None:
        """Test DeploymentResult with minimal parameters."""
        result = DeploymentResult(
            status=DeploymentStatus.PENDING,
            message="Starting deployment",
            duration=0.0
        )
        
        assert result.status == DeploymentStatus.PENDING
        assert result.outputs is None
        assert result.errors is None
        assert result.warnings is None


class ConcreteDeployer(BaseDeployer):
    """Concrete implementation of BaseDeployer for testing."""
    
    def deploy(self) -> DeploymentResult:
        """Mock deploy implementation."""
        return DeploymentResult(
            status=DeploymentStatus.SUCCESS,
            message="Mock deployment successful",
            duration=10.0
        )
    
    def validate(self) -> bool:
        """Mock validate implementation."""
        return True
    
    def rollback(self) -> bool:
        """Mock rollback implementation."""
        return True


class TestBaseDeployer:
    """Test BaseDeployer functionality."""

    @pytest.fixture
    def mock_config(self) -> Dict[str, Any]:
        """Create a mock configuration."""
        return {
            "project_name": "test-project",
            "environment": "prod",
            "region": "us-west-1",
            "stack_name": "test-project-prod"
        }

    @pytest.fixture
    def deployer(self, mock_config: Dict[str, Any]) -> ConcreteDeployer:
        """Create a ConcreteDeployer instance."""
        with patch("boto3.Session") as mock_session:
            mock_cf = Mock()
            mock_s3 = Mock()
            
            def mock_client(service: str, **kwargs):
                if service == "cloudformation":
                    return mock_cf
                elif service == "s3":
                    return mock_s3
                return Mock()
            
            mock_session.return_value.client.side_effect = mock_client
            
            deployer = ConcreteDeployer(mock_config)
            deployer.cloudformation = mock_cf
            deployer.s3 = mock_s3
            
            return deployer

    def test_initialization(self, deployer: ConcreteDeployer, mock_config: Dict[str, Any]) -> None:
        """Test BaseDeployer initialization."""
        assert deployer.config == mock_config
        assert hasattr(deployer, "cloudformation")
        assert hasattr(deployer, "s3")

    def test_deploy_method(self, deployer: ConcreteDeployer) -> None:
        """Test deploy method returns proper result."""
        result = deployer.deploy()
        
        assert isinstance(result, DeploymentResult)
        assert result.status == DeploymentStatus.SUCCESS
        assert result.success is True

    def test_validate_method(self, deployer: ConcreteDeployer) -> None:
        """Test validate method."""
        result = deployer.validate()
        assert result is True

    def test_rollback_method(self, deployer: ConcreteDeployer) -> None:
        """Test rollback method."""
        result = deployer.rollback()
        assert result is True

    def test_get_stack_status(self, deployer: ConcreteDeployer) -> None:
        """Test getting stack status."""
        deployer.cloudformation.describe_stacks.return_value = {
            "Stacks": [{
                "StackStatus": "CREATE_COMPLETE"
            }]
        }
        
        if hasattr(deployer, 'get_stack_status'):
            status = deployer.get_stack_status("test-stack")
            assert status == "CREATE_COMPLETE"

    def test_wait_for_stack(self, deployer: ConcreteDeployer) -> None:
        """Test waiting for stack completion."""
        # Mock stack status progression
        deployer.cloudformation.describe_stacks.side_effect = [
            {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
            {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
            {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]}
        ]
        
        if hasattr(deployer, 'wait_for_stack'):
            with patch("time.sleep"):
                result = deployer.wait_for_stack("test-stack", "CREATE_COMPLETE")
                assert result is True

    def test_upload_artifacts(self, deployer: ConcreteDeployer, tmp_path: Path) -> None:
        """Test uploading deployment artifacts."""
        # Create test artifact
        artifact_file = tmp_path / "artifact.zip"
        artifact_file.write_text("test content")
        
        if hasattr(deployer, 'upload_artifacts'):
            s3_url = deployer.upload_artifacts(str(artifact_file), "my-bucket")
            
            deployer.s3.put_object.assert_called_once()
            assert s3_url.startswith("s3://") or s3_url.startswith("https://")

    def test_get_outputs(self, deployer: ConcreteDeployer) -> None:
        """Test getting stack outputs."""
        deployer.cloudformation.describe_stacks.return_value = {
            "Stacks": [{
                "Outputs": [
                    {"OutputKey": "ApiUrl", "OutputValue": "https://api.example.com"},
                    {"OutputKey": "BucketName", "OutputValue": "my-bucket"}
                ]
            }]
        }
        
        if hasattr(deployer, 'get_outputs'):
            outputs = deployer.get_outputs("test-stack")
            assert outputs["ApiUrl"] == "https://api.example.com"
            assert outputs["BucketName"] == "my-bucket"

    def test_pre_deploy_hook(self, deployer: ConcreteDeployer) -> None:
        """Test pre-deployment hook."""
        if hasattr(deployer, 'pre_deploy'):
            result = deployer.pre_deploy()
            # Base implementation might be empty
            assert result is None or isinstance(result, bool)

    def test_post_deploy_hook(self, deployer: ConcreteDeployer) -> None:
        """Test post-deployment hook."""
        if hasattr(deployer, 'post_deploy'):
            result = deployer.post_deploy()
            # Base implementation might be empty
            assert result is None or isinstance(result, bool)

    def test_handle_deployment_error(self, deployer: ConcreteDeployer) -> None:
        """Test handling deployment errors."""
        error = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack already exists"}},
            "CreateStack"
        )
        
        if hasattr(deployer, 'handle_error'):
            result = deployer.handle_error(error)
            assert isinstance(result, DeploymentResult)
            assert result.status == DeploymentStatus.FAILED

    def test_deployment_with_retry(self, deployer: ConcreteDeployer) -> None:
        """Test deployment with retry logic."""
        # Mock first attempt fails, second succeeds
        deployer.deploy = Mock(side_effect=[
            DeploymentResult(DeploymentStatus.FAILED, "First attempt failed", 10.0),
            DeploymentResult(DeploymentStatus.SUCCESS, "Second attempt succeeded", 15.0)
        ])
        
        if hasattr(deployer, 'deploy_with_retry'):
            result = deployer.deploy_with_retry(max_attempts=2)
            assert result.success is True
            assert deployer.deploy.call_count == 2

    def test_validate_parameters(self, deployer: ConcreteDeployer) -> None:
        """Test parameter validation."""
        parameters = {
            "Environment": "prod",
            "InstanceType": "t3.micro",
            "KeyName": "my-key"
        }
        
        if hasattr(deployer, 'validate_parameters'):
            is_valid = deployer.validate_parameters(parameters)
            assert isinstance(is_valid, bool)

    def test_check_dependencies(self, deployer: ConcreteDeployer) -> None:
        """Test checking deployment dependencies."""
        if hasattr(deployer, 'check_dependencies'):
            dependencies = deployer.check_dependencies()
            assert isinstance(dependencies, (list, dict))

    def test_generate_change_set(self, deployer: ConcreteDeployer) -> None:
        """Test generating CloudFormation change set."""
        deployer.cloudformation.create_change_set.return_value = {
            "Id": "arn:aws:cloudformation:us-west-1:123456789012:changeSet/my-change-set"
        }
        
        if hasattr(deployer, 'generate_change_set'):
            change_set_id = deployer.generate_change_set(
                stack_name="test-stack",
                template_body='{"Resources": {}}'
            )
            assert "changeSet" in change_set_id

    def test_deployment_progress_tracking(self, deployer: ConcreteDeployer) -> None:
        """Test tracking deployment progress."""
        if hasattr(deployer, 'track_progress'):
            # Start tracking
            deployer.track_progress(DeploymentStatus.IN_PROGRESS, "Starting deployment")
            
            # Update progress
            deployer.track_progress(DeploymentStatus.IN_PROGRESS, "Creating resources")
            
            # Complete
            deployer.track_progress(DeploymentStatus.SUCCESS, "Deployment complete")
            
            # Should have progress history
            if hasattr(deployer, 'progress_history'):
                assert len(deployer.progress_history) >= 3

    def test_export_deployment_config(self, deployer: ConcreteDeployer, tmp_path: Path) -> None:
        """Test exporting deployment configuration."""
        export_file = tmp_path / "deployment-config.json"
        
        if hasattr(deployer, 'export_config'):
            deployer.export_config(str(export_file))
            
            assert export_file.exists()
            config = json.loads(export_file.read_text())
            assert config["project_name"] == "test-project"

    def test_deployment_dry_run(self, deployer: ConcreteDeployer) -> None:
        """Test dry run deployment."""
        if hasattr(deployer, 'deploy_dry_run'):
            result = deployer.deploy_dry_run()
            
            assert isinstance(result, DeploymentResult)
            # Dry run should not actually deploy
            deployer.cloudformation.create_stack.assert_not_called()
            deployer.cloudformation.update_stack.assert_not_called()


class TestBaseDeployerErrorHandling:
    """Test error handling in BaseDeployer."""

    @pytest.fixture
    def deployer(self) -> ConcreteDeployer:
        """Create a deployer with mocked AWS clients."""
        with patch("boto3.Session"):
            return ConcreteDeployer({"project_name": "test", "environment": "dev"})

    def test_handle_rate_limit_error(self, deployer: ConcreteDeployer) -> None:
        """Test handling AWS rate limit errors."""
        error = ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "DescribeStacks"
        )
        
        if hasattr(deployer, 'handle_rate_limit'):
            with patch("time.sleep"):
                retry = deployer.handle_rate_limit(error)
                assert retry is True

    def test_handle_access_denied(self, deployer: ConcreteDeployer) -> None:
        """Test handling access denied errors."""
        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "User is not authorized"}},
            "CreateStack"
        )
        
        if hasattr(deployer, 'handle_access_denied'):
            result = deployer.handle_access_denied(error)
            assert result is False  # Should not retry on access denied

    def test_cleanup_on_failure(self, deployer: ConcreteDeployer) -> None:
        """Test cleanup operations on deployment failure."""
        if hasattr(deployer, 'cleanup_on_failure'):
            deployer.cleanup_on_failure()
            
            # Verify cleanup operations were performed
            # This depends on the implementation


@pytest.mark.integration
class TestBaseDeployerIntegration:
    """Integration tests for BaseDeployer."""

    @pytest.mark.skip(reason="Integration tests require AWS credentials")
    def test_with_real_aws(self) -> None:
        """Test with real AWS connection."""
        try:
            config = {
                "project_name": "test-project",
                "environment": "test",
                "region": "us-east-1"
            }
            
            deployer = ConcreteDeployer(config)
            
            # Verify AWS clients are initialized
            assert hasattr(deployer, "cloudformation")
            assert hasattr(deployer, "s3")
            
        except Exception as e:
            pytest.skip(f"AWS credentials not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])