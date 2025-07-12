"""
Comprehensive tests for iam.unified_permissions module.
"""

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch, call

import pytest
from botocore.exceptions import ClientError

from iam.unified_permissions import UnifiedPolicyGenerator, PolicyCategory


class TestUnifiedPolicyGenerator:
    """Test UnifiedPolicyGenerator functionality."""

    @pytest.fixture
    def generator(self) -> UnifiedPolicyGenerator:
        """Create a UnifiedPolicyGenerator instance."""
        return UnifiedPolicyGenerator(project_name="test-project")

    def test_initialization(self, generator: UnifiedPolicyGenerator) -> None:
        """Test UnifiedPolicyGenerator initialization."""
        assert generator.project_name == "test-project"
        assert generator.account_id == "*"  # Default when no session
        assert len(generator.regions) > 0
        assert "us-east-1" in generator.regions

    def test_initialization_with_session(self) -> None:
        """Test initialization with AWS session."""
        mock_session = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts
        
        generator = UnifiedPolicyGenerator(
            project_name="test-project",
            session=mock_session
        )
        
        assert generator.account_id == "123456789012"
        mock_session.client.assert_called_with("sts")

    def test_policy_category_enum(self) -> None:
        """Test PolicyCategory enum values."""
        assert PolicyCategory.INFRASTRUCTURE.value == "Infrastructure"
        assert PolicyCategory.COMPUTE.value == "Compute"
        assert PolicyCategory.STORAGE.value == "Storage"
        assert PolicyCategory.NETWORKING.value == "Networking"
        assert PolicyCategory.MONITORING.value == "Monitoring"

    def test_generate_all_policies(self, generator: UnifiedPolicyGenerator) -> None:
        """Test generating all categorized policies."""
        policies = generator.generate_all_policies()
        
        # Should generate one policy per category
        assert len(policies) == len(PolicyCategory)
        
        # Check each category is present
        policy_names = [p["PolicyName"] for p in policies]
        assert any("Infrastructure" in name for name in policy_names)
        assert any("Compute" in name for name in policy_names)
        assert any("Storage" in name for name in policy_names)
        assert any("Networking" in name for name in policy_names)
        assert any("Monitoring" in name for name in policy_names)
        
        # Verify policy structure
        for policy in policies:
            assert "PolicyName" in policy
            assert "PolicyDocument" in policy
            assert "Version" in policy["PolicyDocument"]
            assert "Statement" in policy["PolicyDocument"]
            assert len(policy["PolicyDocument"]["Statement"]) > 0

    def test_generate_infrastructure_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test infrastructure policy generation."""
        policy = generator._generate_infrastructure_policy()
        
        assert "test-project-Infrastructure" in policy["PolicyName"]
        
        doc = policy["PolicyDocument"]
        assert doc["Version"] == "2012-10-17"
        
        # Check for expected infrastructure permissions
        statements = doc["Statement"]
        actions = []
        for stmt in statements:
            actions.extend(stmt.get("Action", []))
        
        # Should include CloudFormation permissions
        assert any("cloudformation:*" in a for a in actions)
        # Should include IAM permissions
        assert any("iam:" in a for a in actions)
        # Should include SSM permissions
        assert any("ssm:" in a for a in actions)

    def test_generate_compute_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test compute policy generation."""
        policy = generator._generate_compute_policy()
        
        assert "test-project-Compute" in policy["PolicyName"]
        
        doc = policy["PolicyDocument"]
        statements = doc["Statement"]
        actions = []
        for stmt in statements:
            actions.extend(stmt.get("Action", []))
        
        # Should include Lambda permissions
        assert any("lambda:" in a for a in actions)
        # Should include API Gateway permissions
        assert any("apigateway:" in a for a in actions)
        # Should include Cognito permissions
        assert any("cognito" in a for a in actions)

    def test_generate_storage_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test storage policy generation."""
        policy = generator._generate_storage_policy()
        
        assert "test-project-Storage" in policy["PolicyName"]
        
        doc = policy["PolicyDocument"]
        statements = doc["Statement"]
        
        # Check for S3 permissions
        s3_statement = next((s for s in statements if any("s3:" in a for a in s.get("Action", []))), None)
        assert s3_statement is not None
        assert s3_statement["Effect"] == "Allow"
        
        # Check for DynamoDB permissions
        dynamodb_actions = []
        for stmt in statements:
            dynamodb_actions.extend([a for a in stmt.get("Action", []) if "dynamodb:" in a])
        assert len(dynamodb_actions) > 0

    def test_generate_networking_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test networking policy generation."""
        policy = generator._generate_networking_policy()
        
        assert "test-project-Networking" in policy["PolicyName"]
        
        doc = policy["PolicyDocument"]
        statements = doc["Statement"]
        actions = []
        for stmt in statements:
            actions.extend(stmt.get("Action", []))
        
        # Should include VPC permissions
        assert any("ec2:" in a for a in actions)
        # Should include CloudFront permissions
        assert any("cloudfront:" in a for a in actions)
        # Should include Route53 permissions
        assert any("route53:" in a for a in actions)

    def test_generate_monitoring_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test monitoring policy generation."""
        policy = generator._generate_monitoring_policy()
        
        assert "test-project-Monitoring" in policy["PolicyName"]
        
        doc = policy["PolicyDocument"]
        statements = doc["Statement"]
        actions = []
        for stmt in statements:
            actions.extend(stmt.get("Action", []))
        
        # Should include CloudWatch permissions
        assert any("cloudwatch:" in a for a in actions)
        assert any("logs:" in a for a in actions)
        # Should include Cost Explorer permissions
        assert any("ce:" in a for a in actions)
        # Should include tagging permissions
        assert any("tag:" in a for a in actions)

    def test_resource_patterns(self, generator: UnifiedPolicyGenerator) -> None:
        """Test resource ARN patterns include project name."""
        policies = generator.generate_all_policies()
        
        for policy in policies:
            statements = policy["PolicyDocument"]["Statement"]
            for stmt in statements:
                resources = stmt.get("Resource", [])
                if isinstance(resources, list) and len(resources) > 0:
                    # Check that project-specific resources include project name
                    project_resources = [r for r in resources if r != "*" and "arn:aws" in r]
                    if project_resources:
                        assert any("test-project" in r for r in project_resources)

    def test_policy_size_limits(self, generator: UnifiedPolicyGenerator) -> None:
        """Test that generated policies respect AWS size limits."""
        policies = generator.generate_all_policies()
        
        max_policy_size = 6144  # AWS policy size limit in characters
        
        for policy in policies:
            policy_json = json.dumps(policy["PolicyDocument"], separators=(',', ':'))
            policy_size = len(policy_json)
            
            # Each policy should be under the limit
            assert policy_size < max_policy_size, (
                f"Policy {policy['PolicyName']} is {policy_size} chars, "
                f"exceeds limit of {max_policy_size}"
            )

    def test_create_or_update_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test create_or_update_policy method."""
        mock_iam = Mock()
        generator.iam = mock_iam
        
        policy_doc = {
            "PolicyName": "test-policy",
            "PolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]
            }
        }
        
        # Test create new policy
        mock_iam.get_policy.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "GetPolicy"
        )
        mock_iam.create_policy.return_value = {
            "Policy": {"Arn": "arn:aws:iam::123456789012:policy/test-policy"}
        }
        
        result = generator.create_or_update_policy(policy_doc)
        
        assert result == "arn:aws:iam::123456789012:policy/test-policy"
        mock_iam.create_policy.assert_called_once()

    def test_update_existing_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test updating an existing policy."""
        mock_iam = Mock()
        generator.iam = mock_iam
        
        policy_arn = "arn:aws:iam::123456789012:policy/test-policy"
        policy_doc = {
            "PolicyName": "test-policy",
            "PolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]
            }
        }
        
        # Mock existing policy
        mock_iam.get_policy.return_value = {"Policy": {"Arn": policy_arn}}
        mock_iam.list_policy_versions.return_value = {
            "Versions": [
                {"VersionId": "v2", "IsDefaultVersion": True},
                {"VersionId": "v1", "IsDefaultVersion": False},
            ]
        }
        
        result = generator.create_or_update_policy(policy_doc)
        
        assert result == policy_arn
        mock_iam.create_policy_version.assert_called_once()

    def test_update_policy_version_limit(self, generator: UnifiedPolicyGenerator) -> None:
        """Test handling policy version limit."""
        mock_iam = Mock()
        generator.iam = mock_iam
        
        policy_arn = "arn:aws:iam::123456789012:policy/test-policy"
        policy_doc = {
            "PolicyName": "test-policy",
            "PolicyDocument": {"Version": "2012-10-17", "Statement": []}
        }
        
        # Mock 5 existing versions (AWS limit)
        mock_iam.get_policy.return_value = {"Policy": {"Arn": policy_arn}}
        mock_iam.list_policy_versions.return_value = {
            "Versions": [
                {"VersionId": f"v{i}", "IsDefaultVersion": i == 5}
                for i in range(1, 6)
            ]
        }
        
        result = generator.create_or_update_policy(policy_doc)
        
        # Should delete oldest non-default version
        mock_iam.delete_policy_version.assert_called_once_with(
            PolicyArn=policy_arn,
            VersionId="v1"
        )
        mock_iam.create_policy_version.assert_called_once()

    def test_apply_policies_to_user(self, generator: UnifiedPolicyGenerator) -> None:
        """Test applying policies to a user."""
        mock_iam = Mock()
        generator.iam = mock_iam
        
        # Mock policy creation
        policy_arns = [
            f"arn:aws:iam::123456789012:policy/test-project-{cat.value}"
            for cat in PolicyCategory
        ]
        generator.create_or_update_policy = Mock(side_effect=policy_arns)
        
        # Mock existing attached policies
        mock_iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [
                {"PolicyArn": "arn:aws:iam::123456789012:policy/old-policy"}
            ]
        }
        
        generator.apply_policies_to_user("test-user")
        
        # Should attach all new policies
        assert mock_iam.attach_user_policy.call_count == len(PolicyCategory)
        
        # Should detach old policy
        mock_iam.detach_user_policy.assert_called_once_with(
            UserName="test-user",
            PolicyArn="arn:aws:iam::123456789012:policy/old-policy"
        )

    def test_apply_policies_to_role(self, generator: UnifiedPolicyGenerator) -> None:
        """Test applying policies to a role."""
        mock_iam = Mock()
        generator.iam = mock_iam
        
        # Mock policy creation
        policy_arns = [
            f"arn:aws:iam::123456789012:policy/test-project-{cat.value}"
            for cat in PolicyCategory
        ]
        generator.create_or_update_policy = Mock(side_effect=policy_arns)
        
        # Mock existing attached policies
        mock_iam.list_attached_role_policies.return_value = {
            "AttachedPolicies": []
        }
        
        generator.apply_policies_to_role("test-role")
        
        # Should attach all new policies
        assert mock_iam.attach_role_policy.call_count == len(PolicyCategory)

    def test_validate_policy_document(self, generator: UnifiedPolicyGenerator) -> None:
        """Test policy document validation."""
        # Valid policy
        valid_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::bucket/*"
                }
            ]
        }
        
        # Should not raise exception
        generator._validate_policy_document(valid_policy)
        
        # Invalid policy - missing Version
        invalid_policy = {
            "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]
        }
        
        with pytest.raises(ValueError, match="Version"):
            generator._validate_policy_document(invalid_policy)

    def test_get_policy_summary(self, generator: UnifiedPolicyGenerator) -> None:
        """Test getting policy summary."""
        policies = generator.generate_all_policies()
        summary = generator.get_policy_summary()
        
        assert "project" in summary
        assert summary["project"] == "test-project"
        assert "categories" in summary
        assert len(summary["categories"]) == len(PolicyCategory)
        
        for category in summary["categories"]:
            assert "name" in category
            assert "policy_name" in category
            assert "statement_count" in category
            assert "size_bytes" in category

    def test_generate_minimal_policy(self, generator: UnifiedPolicyGenerator) -> None:
        """Test generating minimal policies for testing."""
        generator.minimal = True
        policies = generator.generate_all_policies()
        
        # Minimal policies should be smaller
        for policy in policies:
            policy_json = json.dumps(policy["PolicyDocument"])
            assert len(policy_json) < 2000  # Should be much smaller than full policies

    def test_policy_actions_are_valid(self, generator: UnifiedPolicyGenerator) -> None:
        """Test that all policy actions follow AWS naming conventions."""
        policies = generator.generate_all_policies()
        
        for policy in policies:
            statements = policy["PolicyDocument"]["Statement"]
            for stmt in statements:
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                
                for action in actions:
                    # AWS actions follow service:Action pattern
                    if action != "*":
                        assert ":" in action, f"Invalid action format: {action}"
                        service, operation = action.split(":", 1)
                        assert len(service) > 0, f"Empty service in action: {action}"
                        assert len(operation) > 0, f"Empty operation in action: {action}"

    def test_wildcard_usage(self, generator: UnifiedPolicyGenerator) -> None:
        """Test appropriate use of wildcards in policies."""
        policies = generator.generate_all_policies()
        
        for policy in policies:
            statements = policy["PolicyDocument"]["Statement"]
            for stmt in statements:
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                
                # Count wildcard usage
                wildcard_actions = [a for a in actions if a.endswith("*")]
                
                # Wildcards should be used judiciously
                if wildcard_actions:
                    # If using wildcards, resources should be constrained
                    resources = stmt.get("Resource", [])
                    if isinstance(resources, str):
                        resources = [resources]
                    
                    # At least some resources should be project-specific
                    if resources != ["*"]:
                        assert any("test-project" in r for r in resources if r != "*")


@pytest.mark.integration
class TestUnifiedPolicyGeneratorIntegration:
    """Integration tests for UnifiedPolicyGenerator."""

    @pytest.mark.skip(reason="Integration tests require AWS credentials")
    def test_with_real_aws(self) -> None:
        """Test with real AWS connection."""
        try:
            import boto3
            session = boto3.Session()
            generator = UnifiedPolicyGenerator(
                project_name="test-project",
                session=session
            )
            
            # Just verify we can generate policies
            policies = generator.generate_all_policies()
            assert len(policies) == len(PolicyCategory)
            
        except Exception as e:
            pytest.skip(f"AWS credentials not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])