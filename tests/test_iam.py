"""
Tests for IAM management functionality.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from iam import CICDPermissionManager, PolicyGenerator
from config import ProjectConfig


class TestPolicyGenerator:
    """Test IAM policy generation."""
    
    def test_generate_cicd_policy_basic(self):
        """Test basic CI/CD policy generation."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            aws_region="us-east-1"
        )
        
        generator = PolicyGenerator(config)
        policy = generator.generate_cicd_policy("123456789012")
        
        # Verify policy structure
        assert policy["Version"] == "2012-10-17"
        assert "Statement" in policy
        assert len(policy["Statement"]) > 0
        
        # Check for key permissions
        statements = {s["Sid"]: s for s in policy["Statement"]}
        
        # CloudFormation permissions
        assert "CloudFormationAccess" in statements
        cf_statement = statements["CloudFormationAccess"]
        assert "cloudformation:CreateStack" in cf_statement["Action"]
        assert any("test-project" in r for r in cf_statement["Resource"])
        
        # S3 permissions
        assert "S3Access" in statements
        s3_statement = statements["S3Access"]
        assert "s3:CreateBucket" in s3_statement["Action"]
        assert any("test-project" in r for r in s3_statement["Resource"])
        
        # Lambda permissions
        assert "LambdaAccess" in statements
        lambda_statement = statements["LambdaAccess"]
        assert "lambda:CreateFunction" in lambda_statement["Action"]
    
    def test_generate_cicd_policy_with_waf(self):
        """Test CI/CD policy generation with WAF enabled."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project",
            enable_waf=True
        )
        
        generator = PolicyGenerator(config)
        policy = generator.generate_cicd_policy("123456789012")
        
        # Check for WAF permissions
        statements = {s["Sid"]: s for s in policy["Statement"]}
        assert "WAFAccess" in statements
        waf_statement = statements["WAFAccess"]
        assert "wafv2:CreateWebACL" in waf_statement["Action"]
    
    def test_generate_lambda_execution_policy(self):
        """Test Lambda execution role policy generation."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project"
        )
        
        generator = PolicyGenerator(config)
        policy = generator.generate_lambda_execution_policy()
        
        # Verify basic structure
        assert policy["Version"] == "2012-10-17"
        assert len(policy["Statement"]) >= 3  # Logs, DynamoDB, S3
        
        # Check permissions
        actions = []
        for statement in policy["Statement"]:
            actions.extend(statement["Action"])
        
        assert "logs:CreateLogGroup" in actions
        assert "dynamodb:GetItem" in actions
        assert "s3:GetObject" in actions
    
    def test_generate_github_actions_trust_policy(self):
        """Test GitHub Actions OIDC trust policy generation."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project"
        )
        
        generator = PolicyGenerator(config)
        policy = generator.generate_github_actions_trust_policy("myorg", "myrepo")
        
        # Verify structure
        assert policy["Version"] == "2012-10-17"
        assert len(policy["Statement"]) == 1
        
        statement = policy["Statement"][0]
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
        
        # Check conditions
        conditions = statement["Condition"]
        assert "token.actions.githubusercontent.com:aud" in conditions["StringEquals"]
        assert "repo:myorg/myrepo:*" in conditions["StringLike"]["token.actions.githubusercontent.com:sub"]


class TestCICDPermissionManager:
    """Test CI/CD permission management."""
    
    def create_manager(self):
        """Create a test manager with mocked AWS clients."""
        config = ProjectConfig(
            name="test-project",
            display_name="Test Project"
        )
        
        with patch('boto3.Session'):
            manager = CICDPermissionManager("test-project", config=config)
            
            # Mock AWS clients
            manager.iam = Mock()
            manager.sts = Mock()
            manager.sts.get_caller_identity.return_value = {"Account": "123456789012"}
            
            return manager
    
    def test_setup_iam_user_new(self):
        """Test setting up a new IAM user."""
        manager = self.create_manager()
        
        # Mock IAM responses
        manager.iam.get_user.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "GetUser"
        )
        manager.iam.create_access_key.return_value = {
            "AccessKey": {
                "AccessKeyId": "AKIATEST123",
                "SecretAccessKey": "secret123"
            }
        }
        
        # Test user creation
        credentials = manager._setup_iam_user("test-user", "arn:aws:iam::123456789012:policy/test")
        
        # Verify calls
        manager.iam.create_user.assert_called_once_with(UserName="test-user")
        manager.iam.attach_user_policy.assert_called_once()
        manager.iam.create_access_key.assert_called_once_with(UserName="test-user")
        
        # Verify credentials
        assert credentials.access_key_id == "AKIATEST123"
        assert credentials.secret_access_key == "secret123"
        assert credentials.user_name == "test-user"
    
    def test_setup_iam_user_existing(self):
        """Test setting up an existing IAM user."""
        manager = self.create_manager()
        
        # Mock existing user
        manager.iam.get_user.return_value = {"User": {"UserName": "test-user"}}
        manager.iam.create_access_key.return_value = {
            "AccessKey": {
                "AccessKeyId": "AKIATEST456",
                "SecretAccessKey": "secret456"
            }
        }
        
        # Test with existing user
        credentials = manager._setup_iam_user("test-user", "arn:aws:iam::123456789012:policy/test")
        
        # Should not create user
        manager.iam.create_user.assert_not_called()
        
        # Should still attach policy and create key
        manager.iam.attach_user_policy.assert_called_once()
        manager.iam.create_access_key.assert_called_once()
    
    def test_rotate_access_keys(self):
        """Test rotating access keys."""
        manager = self.create_manager()
        
        # Mock existing keys
        manager.iam.list_access_keys.return_value = {
            "AccessKeyMetadata": [
                {"AccessKeyId": "AKIAOLD123", "Status": "Active"}
            ]
        }
        
        manager.iam.create_access_key.return_value = {
            "AccessKey": {
                "AccessKeyId": "AKIANEW123",
                "SecretAccessKey": "newsecret123"
            }
        }
        
        manager.iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [
                {"PolicyArn": "arn:aws:iam::123456789012:policy/test"}
            ]
        }
        
        # Rotate keys
        credentials = manager.rotate_access_keys("test-user")
        
        # Verify old key deleted
        manager.iam.delete_access_key.assert_called_once_with(
            UserName="test-user",
            AccessKeyId="AKIAOLD123"
        )
        
        # Verify new key created
        assert credentials.access_key_id == "AKIANEW123"
        assert credentials.secret_access_key == "newsecret123"
    
    def test_validate_permissions_all_good(self):
        """Test permission validation when everything is set up."""
        manager = self.create_manager()
        
        # Mock successful checks
        manager.iam.get_user.return_value = {"User": {"UserName": "test-user"}}
        manager.iam.list_policies.return_value = {
            "Policies": [
                {"PolicyName": "test-project-cicd-policy", "Arn": "arn:aws:iam::123456789012:policy/test"}
            ]
        }
        manager.iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [
                {"PolicyArn": "arn:aws:iam::123456789012:policy/test"}
            ]
        }
        manager.iam.list_access_keys.return_value = {
            "AccessKeyMetadata": [
                {"AccessKeyId": "AKIA123", "Status": "Active"}
            ]
        }
        
        # Should pass validation
        assert manager.validate_permissions() is True
    
    def test_validate_permissions_missing_user(self):
        """Test permission validation with missing user."""
        manager = self.create_manager()
        
        # Mock missing user
        manager.iam.get_user.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "GetUser"
        )
        
        # Should fail validation
        assert manager.validate_permissions() is False
    
    def test_cleanup_cicd_resources(self):
        """Test cleaning up CI/CD resources."""
        manager = self.create_manager()
        
        # Mock existing resources
        manager.iam.list_access_keys.return_value = {
            "AccessKeyMetadata": [
                {"AccessKeyId": "AKIA123"}
            ]
        }
        manager.iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [
                {"PolicyArn": "arn:aws:iam::123456789012:policy/test", "PolicyName": "test-policy"}
            ]
        }
        manager.iam.list_policies.return_value = {
            "Policies": [
                {"PolicyName": "test-project-cicd-policy", "Arn": "arn:aws:iam::123456789012:policy/test"}
            ]
        }
        manager.iam.list_policy_versions.return_value = {
            "Versions": [{"VersionId": "v1", "IsDefaultVersion": True}]
        }
        
        # Test cleanup
        result = manager.cleanup_cicd_resources(force=True)
        
        # Verify deletions
        manager.iam.delete_access_key.assert_called_once()
        manager.iam.detach_user_policy.assert_called_once()
        manager.iam.delete_user.assert_called_once()
        manager.iam.delete_policy.assert_called_once()
        
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])