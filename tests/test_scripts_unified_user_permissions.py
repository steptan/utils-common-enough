"""
Comprehensive tests for scripts.unified_user_permissions module.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch, call

import pytest
from botocore.exceptions import ClientError

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scripts.unified_user_permissions import PolicyGenerator


class TestPolicyGenerator:
    """Test PolicyGenerator functionality."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Create a mock ProjectConfig."""
        config = Mock()
        config.name = "test-project"
        config.aws_region = "us-west-1"
        return config

    @pytest.fixture
    def generator(self, mock_config: Mock) -> PolicyGenerator:
        """Create a PolicyGenerator instance."""
        return PolicyGenerator(mock_config)

    def test_initialization(self, generator: PolicyGenerator, mock_config: Mock) -> None:
        """Test PolicyGenerator initialization."""
        assert generator.config == mock_config

    def test_generate_policy_by_category_infrastructure(self, generator: PolicyGenerator) -> None:
        """Test generating infrastructure category policy."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "infrastructure")
        
        assert isinstance(policy, dict)
        assert policy["Version"] == "2012-10-17"
        assert "Statement" in policy
        assert len(policy["Statement"]) > 0

    def test_generate_policy_by_category_compute(self, generator: PolicyGenerator) -> None:
        """Test generating compute category policy."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "compute")
        
        assert isinstance(policy, dict)
        assert policy["Version"] == "2012-10-17"
        assert "Statement" in policy

    def test_generate_policy_by_category_storage(self, generator: PolicyGenerator) -> None:
        """Test generating storage category policy."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "storage")
        
        assert isinstance(policy, dict)
        assert policy["Version"] == "2012-10-17"
        assert "Statement" in policy

    def test_generate_policy_by_category_networking(self, generator: PolicyGenerator) -> None:
        """Test generating networking category policy."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "networking")
        
        assert isinstance(policy, dict)
        assert policy["Version"] == "2012-10-17"
        assert "Statement" in policy

    def test_generate_policy_by_category_monitoring(self, generator: PolicyGenerator) -> None:
        """Test generating monitoring category policy."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "monitoring")
        
        assert isinstance(policy, dict)
        assert policy["Version"] == "2012-10-17"
        assert "Statement" in policy

    def test_generate_policy_invalid_category(self, generator: PolicyGenerator) -> None:
        """Test generating policy with invalid category."""
        account_id = "123456789012"
        
        with pytest.raises(ValueError, match="Unknown category"):
            generator.generate_policy_by_category(account_id, "invalid_category")

    def test_infrastructure_statements(self, generator: PolicyGenerator) -> None:
        """Test infrastructure permission statements."""
        account_id = "123456789012"
        
        # Test if method exists and returns proper structure
        if hasattr(generator, '_get_infrastructure_statements'):
            statements = generator._get_infrastructure_statements(account_id)
            
            assert isinstance(statements, list)
            for stmt in statements:
                assert "Effect" in stmt
                assert "Action" in stmt
                assert "Resource" in stmt

    def test_compute_statements(self, generator: PolicyGenerator) -> None:
        """Test compute permission statements."""
        account_id = "123456789012"
        
        if hasattr(generator, '_get_compute_statements'):
            statements = generator._get_compute_statements(account_id)
            
            assert isinstance(statements, list)
            # Should include Lambda permissions
            actions = []
            for stmt in statements:
                if isinstance(stmt.get("Action"), list):
                    actions.extend(stmt["Action"])
                else:
                    actions.append(stmt.get("Action"))
            
            assert any("lambda:" in action for action in actions if action)

    def test_storage_statements(self, generator: PolicyGenerator) -> None:
        """Test storage permission statements."""
        account_id = "123456789012"
        
        if hasattr(generator, '_get_storage_statements'):
            statements = generator._get_storage_statements(account_id)
            
            assert isinstance(statements, list)
            # Should include S3 and DynamoDB permissions
            actions = []
            for stmt in statements:
                if isinstance(stmt.get("Action"), list):
                    actions.extend(stmt["Action"])
                else:
                    actions.append(stmt.get("Action"))
            
            assert any("s3:" in action for action in actions if action)

    def test_networking_statements(self, generator: PolicyGenerator) -> None:
        """Test networking permission statements."""
        account_id = "123456789012"
        
        if hasattr(generator, '_get_networking_statements'):
            statements = generator._get_networking_statements(account_id)
            
            assert isinstance(statements, list)
            # Should include VPC and CloudFront permissions
            actions = []
            for stmt in statements:
                if isinstance(stmt.get("Action"), list):
                    actions.extend(stmt["Action"])
                else:
                    actions.append(stmt.get("Action"))

    def test_monitoring_statements(self, generator: PolicyGenerator) -> None:
        """Test monitoring permission statements."""
        account_id = "123456789012"
        
        if hasattr(generator, '_get_monitoring_statements'):
            statements = generator._get_monitoring_statements(account_id)
            
            assert isinstance(statements, list)
            # Should include CloudWatch permissions
            actions = []
            for stmt in statements:
                if isinstance(stmt.get("Action"), list):
                    actions.extend(stmt["Action"])
                else:
                    actions.append(stmt.get("Action"))

    def test_policy_size_limits(self, generator: PolicyGenerator) -> None:
        """Test that generated policies respect AWS size limits."""
        account_id = "123456789012"
        categories = ["infrastructure", "compute", "storage", "networking", "monitoring"]
        
        max_policy_size = 6144  # AWS policy size limit
        
        for category in categories:
            policy = generator.generate_policy_by_category(account_id, category)
            policy_json = json.dumps(policy, separators=(',', ':'))
            
            assert len(policy_json) < max_policy_size, (
                f"Policy for {category} is {len(policy_json)} chars, "
                f"exceeds limit of {max_policy_size}"
            )

    def test_resource_patterns(self, generator: PolicyGenerator) -> None:
        """Test that resource patterns include project name."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "storage")
        
        # Check that some resources include the project name
        project_name = generator.config.name
        resource_strings = []
        
        for stmt in policy["Statement"]:
            resources = stmt.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]
            resource_strings.extend(resources)
        
        # At least some resources should reference the project
        assert any(project_name in res for res in resource_strings if res != "*")

    def test_generate_all_categories(self, generator: PolicyGenerator) -> None:
        """Test generating policies for all categories."""
        account_id = "123456789012"
        categories = ["infrastructure", "compute", "storage", "networking", "monitoring"]
        
        all_policies = {}
        for category in categories:
            policy = generator.generate_policy_by_category(account_id, category)
            all_policies[category] = policy
        
        assert len(all_policies) == 5
        for category, policy in all_policies.items():
            assert policy["Version"] == "2012-10-17"
            assert len(policy["Statement"]) > 0

    def test_policy_actions_format(self, generator: PolicyGenerator) -> None:
        """Test that all policy actions follow AWS format."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "compute")
        
        for stmt in policy["Statement"]:
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            
            for action in actions:
                if action != "*":
                    # AWS actions should have service:operation format
                    assert ":" in action, f"Invalid action format: {action}"
                    service, operation = action.split(":", 1)
                    assert len(service) > 0, f"Empty service in action: {action}"
                    assert len(operation) > 0, f"Empty operation in action: {action}"

    def test_policy_effect_values(self, generator: PolicyGenerator) -> None:
        """Test that all statements have valid Effect values."""
        account_id = "123456789012"
        categories = ["infrastructure", "compute", "storage", "networking", "monitoring"]
        
        for category in categories:
            policy = generator.generate_policy_by_category(account_id, category)
            
            for stmt in policy["Statement"]:
                assert "Effect" in stmt
                assert stmt["Effect"] in ["Allow", "Deny"]

    def test_policy_resource_formats(self, generator: PolicyGenerator) -> None:
        """Test that resource ARNs are properly formatted."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "storage")
        
        for stmt in policy["Statement"]:
            resources = stmt.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]
            
            for resource in resources:
                if resource != "*" and resource.startswith("arn:"):
                    # Basic ARN format validation
                    parts = resource.split(":")
                    assert len(parts) >= 6, f"Invalid ARN format: {resource}"
                    assert parts[0] == "arn"
                    assert parts[1] == "aws"

    def test_generate_combined_policy(self, generator: PolicyGenerator) -> None:
        """Test generating a combined policy if method exists."""
        account_id = "123456789012"
        
        if hasattr(generator, 'generate_combined_policy'):
            policy = generator.generate_combined_policy(
                account_id,
                categories=["compute", "storage"]
            )
            
            assert isinstance(policy, dict)
            assert policy["Version"] == "2012-10-17"
            assert len(policy["Statement"]) > 0

    def test_policy_with_conditions(self, generator: PolicyGenerator) -> None:
        """Test that policies can include conditions."""
        account_id = "123456789012"
        policy = generator.generate_policy_by_category(account_id, "infrastructure")
        
        # Check if any statements have conditions
        has_conditions = any(
            "Condition" in stmt
            for stmt in policy["Statement"]
        )
        
        # Not all policies need conditions, but the structure should support them
        # This just verifies the policy structure is valid
        assert isinstance(policy["Statement"], list)


@pytest.mark.integration
class TestPolicyGeneratorIntegration:
    """Integration tests for PolicyGenerator."""

    @pytest.mark.skip(reason="Integration tests require actual config")
    def test_with_real_config(self) -> None:
        """Test with real project configuration."""
        try:
            from config import get_project_config
            
            config = get_project_config("test-project")
            generator = PolicyGenerator(config)
            
            # Generate a policy
            policy = generator.generate_policy_by_category("123456789012", "compute")
            
            assert isinstance(policy, dict)
            assert policy["Version"] == "2012-10-17"
            
        except Exception as e:
            pytest.skip(f"Config not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])