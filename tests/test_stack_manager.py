"""
Tests for CloudFormation stack management functionality.
"""

from unittest.mock import MagicMock, Mock, call, patch

from typing import Any, Dict, List, Optional, Union

import pytest
from botocore.exceptions import ClientError

from cloudformation.stack_manager import StackManager


class TestStackManager:
    """Test CloudFormation stack management."""

    def create_manager(self):
        """Create a test manager with mocked AWS clients."""
        with patch("boto3.Session"):
            manager = StackManager(region="us-east-1")

            # Mock AWS clients
            manager.cloudformation = Mock()
            manager.s3 = Mock()
            manager.ec2 = Mock()

            return manager

    def test_get_stack_status_exists(self) -> None:
        """Test getting stack status for existing stack."""
        manager = self.create_manager()

        manager.cloudformation.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE"}]
        }

        status = manager.get_stack_status("test-stack")
        assert status == "CREATE_COMPLETE"

        manager.cloudformation.describe_stacks.assert_called_once_with(
            StackName="test-stack"
        )

    def test_get_stack_status_not_exists(self) -> None:
        """Test getting stack status for non-existent stack."""
        manager = self.create_manager()

        manager.cloudformation.describe_stacks.side_effect = ClientError(
            {"Error": {"Message": "Stack does not exist"}}, "DescribeStacks"
        )

        status = manager.get_stack_status("test-stack")
        assert status is None

    def test_fix_rollback_state_rollback_complete(self) -> None:
        """Test fixing stack in ROLLBACK_COMPLETE state."""
        manager = self.create_manager()

        # Mock stack in ROLLBACK_COMPLETE state
        manager.cloudformation.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "ROLLBACK_COMPLETE"}]
        }

        # Mock successful deletion
        manager.cloudformation.delete_stack.return_value = {}

        with patch.object(manager, "delete_stack", return_value=True) as mock_delete:
            result = manager.fix_rollback_state("test-stack")
            assert result is True
            mock_delete.assert_called_once_with("test-stack", force=True)

    def test_fix_rollback_state_rollback_failed(self) -> None:
        """Test fixing stack in ROLLBACK_FAILED state."""
        manager = self.create_manager()

        # Mock stack in ROLLBACK_FAILED state
        manager.cloudformation.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "ROLLBACK_FAILED"}]
        }

        # Mock continue rollback
        manager.cloudformation.continue_update_rollback.return_value = {}

        # Mock waiter
        waiter_mock = Mock()
        manager.cloudformation.get_waiter.return_value = waiter_mock

        with patch.object(manager, "delete_stack", return_value=True) as mock_delete:
            result = manager.fix_rollback_state("test-stack")

            # Should continue rollback
            manager.cloudformation.continue_update_rollback.assert_called_once_with(
                StackName="test-stack"
            )

            # Should wait for rollback
            waiter_mock.wait.assert_called_once()

            # Should delete stack after rollback
            mock_delete.assert_called_once_with("test-stack")

            assert result is True

    def test_fix_rollback_state_with_skip_resources(self) -> None:
        """Test fixing stack with resources to skip."""
        manager = self.create_manager()

        # Mock stack in UPDATE_ROLLBACK_FAILED state
        manager.cloudformation.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "UPDATE_ROLLBACK_FAILED"}]
        }

        # Mock continue rollback
        manager.cloudformation.continue_update_rollback.return_value = {}

        # Mock waiter
        waiter_mock = Mock()
        manager.cloudformation.get_waiter.return_value = waiter_mock

        with patch.object(manager, "delete_stack", return_value=True):
            result = manager.fix_rollback_state(
                "test-stack", skip_resources=["Resource1", "Resource2"]
            )

            # Should continue rollback with skip resources
            manager.cloudformation.continue_update_rollback.assert_called_once_with(
                StackName="test-stack", ResourcesToSkip=["Resource1", "Resource2"]
            )

            assert result is True

    def test_handle_delete_blockers_s3_bucket(self) -> None:
        """Test handling S3 bucket blocking deletion."""
        manager = self.create_manager()

        # Mock stack resources with failed S3 bucket
        manager.cloudformation.describe_stack_resources.return_value = {
            "StackResources": [
                {
                    "ResourceType": "AWS::S3::Bucket",
                    "ResourceStatus": "DELETE_FAILED",
                    "PhysicalResourceId": "test-bucket",
                }
            ]
        }

        # Mock S3 list objects
        manager.s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": "file1.txt"}, {"Key": "file2.txt"}]}
        ]

        # Mock S3 delete
        manager.s3.delete_objects.return_value = {}

        manager._handle_delete_blockers("test-stack")

        # Should delete objects
        manager.s3.delete_objects.assert_called()

        # Verify delete was called with correct objects
        call_args = manager.s3.delete_objects.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert len(call_args[1]["Delete"]["Objects"]) == 2

    def test_handle_delete_blockers_s3_versioned(self) -> None:
        """Test handling versioned S3 bucket."""
        manager = self.create_manager()

        # Mock stack resources
        manager.cloudformation.describe_stack_resources.return_value = {
            "StackResources": [
                {
                    "ResourceType": "AWS::S3::Bucket",
                    "ResourceStatus": "DELETE_FAILED",
                    "PhysicalResourceId": "test-bucket",
                }
            ]
        }

        # Mock list objects (no regular objects)
        list_objects_paginator = Mock()
        list_objects_paginator.paginate.return_value = []

        # Mock list object versions
        list_versions_paginator = Mock()
        list_versions_paginator.paginate.return_value = [
            {
                "Versions": [
                    {"Key": "file1.txt", "VersionId": "v1"},
                    {"Key": "file2.txt", "VersionId": "v2"},
                ],
                "DeleteMarkers": [{"Key": "deleted.txt", "VersionId": "d1"}],
            }
        ]

        manager.s3.get_paginator.side_effect = lambda x: (
            list_objects_paginator
            if x == "list_objects_v2"
            else list_versions_paginator
        )

        manager.s3.delete_objects.return_value = {}

        manager._handle_delete_blockers("test-stack")

        # Should delete versioned objects
        delete_calls = manager.s3.delete_objects.call_args_list
        assert len(delete_calls) >= 1

        # Check that versions were included
        for call in delete_calls:
            if "Delete" in call[1] and call[1]["Delete"]["Objects"]:
                objects = call[1]["Delete"]["Objects"]
                # Should have VersionId for versioned objects
                versioned_objects = [obj for obj in objects if "VersionId" in obj]
                assert len(versioned_objects) > 0

    def test_handle_delete_blockers_eni(self) -> None:
        """Test handling ENI blocking deletion."""
        manager = self.create_manager()

        # Mock stack resources with ENI
        manager.cloudformation.describe_stack_resources.return_value = {
            "StackResources": [
                {
                    "ResourceType": "AWS::EC2::NetworkInterface",
                    "ResourceStatus": "DELETE_FAILED",
                    "PhysicalResourceId": "eni-12345",
                }
            ]
        }

        # Mock ENI description
        manager.ec2.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "NetworkInterfaceId": "eni-12345",
                    "Attachment": {"AttachmentId": "attach-12345"},
                }
            ]
        }

        # Mock detach and delete
        manager.ec2.detach_network_interface.return_value = {}
        manager.ec2.delete_network_interface.return_value = {}

        manager._handle_delete_blockers("test-stack")

        # Should detach ENI
        manager.ec2.detach_network_interface.assert_called_once_with(
            AttachmentId="attach-12345", Force=True
        )

        # Should delete ENI
        manager.ec2.delete_network_interface.assert_called_once_with(
            NetworkInterfaceId="eni-12345"
        )

    def test_delete_stack_force_with_delete_failed(self) -> None:
        """Test force deleting stack in DELETE_FAILED state."""
        manager = self.create_manager()

        # Mock stack in DELETE_FAILED state
        manager.get_stack_status = Mock(return_value="DELETE_FAILED")

        # Mock delete blockers handling
        manager._handle_delete_blockers = Mock()

        # Mock successful deletion
        manager.cloudformation.delete_stack.return_value = {}

        # Mock waiter
        with patch.object(manager, "_wait_for_deletion", return_value=True):
            result = manager.delete_stack("test-stack", force=True)

            # Should handle delete blockers
            manager._handle_delete_blockers.assert_called_once_with("test-stack")

            # Should delete stack
            manager.cloudformation.delete_stack.assert_called_once_with(
                StackName="test-stack"
            )

            assert result is True

    def test_diagnose_stack_failure(self) -> None:
        """Test diagnosing stack failure."""
        manager = self.create_manager()

        # Mock stack status
        manager.get_stack_status = Mock(return_value="CREATE_FAILED")

        # Mock stack events
        manager.cloudformation.describe_stack_events.return_value = {
            "StackEvents": [
                {
                    "LogicalResourceId": "MyBucket",
                    "ResourceType": "AWS::S3::Bucket",
                    "ResourceStatus": "CREATE_FAILED",
                    "ResourceStatusReason": "test-bucket already exists",
                    "Timestamp": "2023-01-01T00:00:00Z",
                },
                {
                    "LogicalResourceId": "MyFunction",
                    "ResourceType": "AWS::Lambda::Function",
                    "ResourceStatus": "CREATE_FAILED",
                    "ResourceStatusReason": "AccessDenied: User is not authorized",
                    "Timestamp": "2023-01-01T00:01:00Z",
                },
            ]
        }

        diagnosis = manager.diagnose_stack_failure("test-stack")

        assert diagnosis["stack_name"] == "test-stack"
        assert diagnosis["status"] == "CREATE_FAILED"
        assert len(diagnosis["failed_resources"]) == 2

        # Check S3 failure
        s3_failure = next(
            r
            for r in diagnosis["failed_resources"]
            if r["resource_type"] == "AWS::S3::Bucket"
        )
        assert "already exists" in s3_failure["reason"]

        # Check recommendations
        assert any(
            "S3 bucket name already exists" in rec
            for rec in diagnosis["recommendations"]
        )
        assert any(
            "Check IAM permissions" in rec for rec in diagnosis["recommendations"]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
