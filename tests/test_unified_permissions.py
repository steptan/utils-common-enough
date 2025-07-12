#!/usr/bin/env python3
"""
Tests for unified user permissions management script.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from typing import Any, Dict, List, Optional, Union

import pytest
from click.testing import CliRunner

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ProjectConfig
from iam.unified_permissions import UnifiedPolicyGenerator
from scripts.unified_user_permissions import (
    PolicyGenerator,
    UnifiedPermissionManager,
    cli,
)


class TestPolicyGenerator:
    """Test the PolicyGenerator class."""

    def test_generate_policy_by_category_structure(self) -> None:
        """Test that generated category policies have correct structure."""
        config = ProjectConfig(
            name="test-project", display_name="Test Project", aws_region="us-east-1"
        )

        generator = UnifiedPolicyGenerator(config)
        categories = [
            "infrastructure",
            "compute",
            "storage",
            "networking",
            "monitoring",
        ]

        for category in categories:
            policy = generator.generate_policy_by_category("123456789012", category)

            # Check basic structure
            assert policy["Version"] == "2012-10-17"
            assert isinstance(policy["Statement"], list)
            assert len(policy["Statement"]) > 0  # Should have statements

            # Check each statement has required fields
            for statement in policy["Statement"]:
                assert "Sid" in statement
                assert "Effect" in statement
                assert "Action" in statement
                assert "Resource" in statement

    def test_generate_category_permissions(self) -> None:
        """Test that category policies include expected permissions."""
        config = ProjectConfig(
            name="test-project", display_name="Test Project", aws_region="us-east-1"
        )

        generator = UnifiedPolicyGenerator(config)

        # Test infrastructure category
        policy = generator.generate_policy_by_category("123456789012", "infrastructure")
        sids = {s["Sid"] for s in policy["Statement"]}
        assert "CloudFormationAccess" in sids
        assert "IAMAccess" in sids
        assert "SSMParameterAccess" in sids

        # Test compute category
        policy = generator.generate_policy_by_category("123456789012", "compute")
        sids = {s["Sid"] for s in policy["Statement"]}
        assert "LambdaFullAccess" in sids
        assert "APIGatewayFullAccess" in sids

        # Test storage category
        policy = generator.generate_policy_by_category("123456789012", "storage")
        sids = {s["Sid"] for s in policy["Statement"]}
        assert "S3FullAccess" in sids
        assert "DynamoDBFullAccess" in sids

    def test_generate_networking_policy_with_waf(self) -> None:
        """Test WAF permissions are included in networking category when enabled."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            aws_region="us-east-1",
            enable_waf=True,
        )

        generator = UnifiedPolicyGenerator(config)
        policy = generator.generate_policy_by_category("123456789012", "networking")

        # Check WAF statement exists
        waf_statement = next(
            (s for s in policy["Statement"] if s["Sid"] == "WAFAccess"), None
        )
        assert waf_statement is not None
        assert "wafv2:*" in waf_statement["Action"]

    def test_policy_resource_scoping(self) -> None:
        """Test that resources are properly scoped to project."""
        config = ProjectConfig(
            name="my-app", display_name="My App", aws_region="us-west-2"
        )

        generator = UnifiedPolicyGenerator(config)

        # Check infrastructure resources
        policy = generator.generate_policy_by_category("123456789012", "infrastructure")
        cf_statement = next(
            s for s in policy["Statement"] if s["Sid"] == "CloudFormationAccess"
        )
        assert any("my-app-*" in r for r in cf_statement["Resource"])

        # Check storage resources
        policy = generator.generate_policy_by_category("123456789012", "storage")
        s3_statement = next(
            s for s in policy["Statement"] if s["Sid"] == "S3FullAccess"
        )
        assert any("arn:aws:s3:::my-app-*" in r for r in s3_statement["Resource"])

        # Check compute resources
        policy = generator.generate_policy_by_category("123456789012", "compute")
        lambda_statement = next(
            s for s in policy["Statement"] if s["Sid"] == "LambdaFullAccess"
        )
        assert any("function:my-app-*" in r for r in lambda_statement["Resource"])


class TestUnifiedPermissionManager:
    """Test the UnifiedPermissionManager class."""

    @pytest.fixture
    def mock_aws_clients(self) -> Any:
        """Create mocked AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_iam = Mock()
            mock_sts = Mock()

            mock_session.return_value.client.side_effect = lambda service, **kwargs: {
                "iam": mock_iam,
                "sts": mock_sts,
            }[service]

            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

            yield mock_iam, mock_sts

    def test_get_user_projects_cicd_user(self, mock_aws_clients) -> None:
        """Test project detection for legacy project-cicd user."""
        mock_iam, mock_sts = mock_aws_clients

        manager = UnifiedPermissionManager()
        projects = manager.get_user_projects("project-cicd")

        assert projects == ["fraud-or-not", "media-register", "people-cards"]

    def test_get_user_projects_specific_user(self, mock_aws_clients) -> None:
        """Test project detection for project-specific user."""
        mock_iam, mock_sts = mock_aws_clients

        manager = UnifiedPermissionManager()
        projects = manager.get_user_projects("fraud-or-not-cicd")

        assert projects == ["fraud-or-not"]

    def test_get_user_projects_from_policies(self, mock_aws_clients) -> None:
        """Test project detection from existing policies."""
        mock_iam, mock_sts = mock_aws_clients

        mock_iam.list_user_policies.return_value = {
            "PolicyNames": ["media-register-policy", "fraud-or-not-permissions"]
        }

        manager = UnifiedPermissionManager()
        projects = manager.get_user_projects("custom-user")

        assert set(projects) == {"media-register", "fraud-or-not"}

    def test_update_user_permissions(self, mock_aws_clients) -> None:
        """Test updating user permissions."""
        mock_iam, mock_sts = mock_aws_clients

        with patch(
            "scripts.unified_user_permissions.get_project_config"
        ) as mock_config:
            mock_config.return_value = ProjectConfig(
                name="test-project", display_name="Test Project", aws_region="us-east-1"
            )

            manager = UnifiedPermissionManager()

            # Test successful update
            manager.update_user_permissions("test-user", ["test-project"])

            # Verify IAM calls
            mock_iam.put_user_policy.assert_called_once()
            call_args = mock_iam.put_user_policy.call_args
            assert call_args[1]["UserName"] == "test-user"
            assert "policy" in call_args[1]["PolicyName"]

            # Check policy document
            policy_doc = json.loads(call_args[1]["PolicyDocument"])
            assert policy_doc["Version"] == "2012-10-17"
            assert len(policy_doc["Statement"]) > 0

    def test_cleanup_old_policies(self, mock_aws_clients) -> None:
        """Test cleanup of old project-specific policies."""
        mock_iam, mock_sts = mock_aws_clients

        mock_iam.list_user_policies.return_value = {
            "PolicyNames": [
                "test-user-infrastructure-policy",
                "fraud-or-not-cicd-policy",
                "media-register-permissions",
                "custom-policy",
            ]
        }

        manager = UnifiedPermissionManager()
        manager._cleanup_old_policies("test-user", keep_pattern="test-user-*-policy")

        # Should delete project-specific policies but not others
        assert mock_iam.delete_user_policy.call_count == 2
        deleted_policies = [
            call[1]["PolicyName"] for call in mock_iam.delete_user_policy.call_args_list
        ]
        assert "fraud-or-not-cicd-policy" in deleted_policies
        assert "media-register-permissions" in deleted_policies
        assert "custom-policy" not in deleted_policies


class TestCLICommands:
    """Test CLI commands."""

    @pytest.fixture
    def runner(self) -> Any:
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_manager(self) -> Any:
        """Mock the UnifiedPermissionManager."""
        with patch("scripts.unified_user_permissions.UnifiedPermissionManager") as mock:
            yield mock

    def test_update_command(self, runner, mock_manager) -> None:
        """Test the update command."""
        mock_instance = mock_manager.return_value

        result = runner.invoke(
            cli,
            [
                "update",
                "--user",
                "test-user",
                "--projects",
                "fraud-or-not",
                "--projects",
                "media-register",
            ],
        )

        assert result.exit_code == 0
        mock_instance.update_user_permissions.assert_called_once_with(
            "test-user", ["fraud-or-not", "media-register"]
        )

    def test_show_command(self, runner, mock_manager) -> None:
        """Test the show command."""
        mock_instance = mock_manager.return_value

        result = runner.invoke(cli, ["show", "--user", "test-user"])

        assert result.exit_code == 0
        mock_instance.show_user_permissions.assert_called_once_with("test-user")

    def test_list_users_command(self, runner, mock_manager) -> None:
        """Test the list-users command."""
        mock_instance = mock_manager.return_value

        result = runner.invoke(cli, ["list-users"])

        assert result.exit_code == 0
        mock_instance.list_all_users_with_permissions.assert_called_once()

    def test_update_all_command(self, runner, mock_manager) -> None:
        """Test the update-all command."""
        mock_instance = mock_manager.return_value

        # Mock the paginator and user detection
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Users": [
                    {"UserName": "fraud-or-not-cicd"},
                    {"UserName": "media-register-cicd"},
                ]
            }
        ]
        mock_instance.iam.get_paginator.return_value = mock_paginator
        mock_instance.get_user_projects.side_effect = lambda u: [u.replace("-cicd", "")]

        # Run with --yes to skip confirmation
        result = runner.invoke(cli, ["update-all"], input="y\n")

        assert result.exit_code == 0
        assert mock_instance.update_user_permissions.call_count == 2

    def test_generate_command(self, runner, mock_manager) -> None:
        """Test the generate command."""
        mock_instance = mock_manager.return_value
        mock_instance.account_id = "123456789012"
        mock_instance.get_user_projects.return_value = ["fraud-or-not"]

        with patch(
            "scripts.unified_user_permissions.get_project_config"
        ) as mock_config:
            mock_config.return_value = ProjectConfig(
                name="fraud-or-not", display_name="Fraud or Not", aws_region="us-east-1"
            )

            with runner.isolated_filesystem():
                result = runner.invoke(
                    cli,
                    [
                        "generate",
                        "--user",
                        "test-user",
                        "--projects",
                        "fraud-or-not",
                        "--category",
                        "infrastructure",
                        "--output",
                        "policy.json",
                    ],
                )

                assert result.exit_code == 0
                assert Path("policy.json").exists()

                with open("policy.json") as f:
                    policy = json.load(f)
                    assert policy["Version"] == "2012-10-17"


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def mock_aws_clients(self) -> Any:
        """Create mocked AWS clients with error scenarios."""
        with patch("boto3.Session") as mock_session:
            mock_iam = Mock()
            mock_sts = Mock()

            mock_session.return_value.client.side_effect = lambda service, **kwargs: {
                "iam": mock_iam,
                "sts": mock_sts,
            }[service]

            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

            yield mock_iam, mock_sts

    def test_update_nonexistent_user(self, mock_aws_clients) -> None:
        """Test updating permissions for non-existent user."""
        mock_iam, mock_sts = mock_aws_clients

        from botocore.exceptions import ClientError

        mock_iam.put_user_policy.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "PutUserPolicy"
        )
        mock_iam.exceptions.NoSuchEntityException = ClientError

        with patch("scripts.unified_user_permissions.get_project_config"):
            manager = UnifiedPermissionManager()

            with pytest.raises(SystemExit):
                manager.update_user_permissions("nonexistent-user", ["test-project"])

    def test_show_permissions_nonexistent_user(self, mock_aws_clients) -> None:
        """Test showing permissions for non-existent user."""
        mock_iam, mock_sts = mock_aws_clients

        from botocore.exceptions import ClientError

        mock_iam.list_user_policies.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "ListUserPolicies"
        )
        mock_iam.exceptions.NoSuchEntityException = ClientError

        manager = UnifiedPermissionManager()

        with pytest.raises(SystemExit):
            manager.show_user_permissions("nonexistent-user")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
