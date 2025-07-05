#!/usr/bin/env python3
"""
Integration tests for unified permissions script.
Can be run directly without pytest.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scripts.unified_user_permissions import PolicyGenerator, UnifiedPermissionManager
from config import ProjectConfig


def test_policy_generation():
    """Test that policy generation works correctly."""
    print("Testing policy generation...")

    config = ProjectConfig(
        name="test-project", display_name="Test Project", aws_region="us-east-1"
    )

    generator = PolicyGenerator(config)

    # Test categorized policies
    categories = {
        "infrastructure": ["CloudFormationAccess", "IAMAccess", "SSMParameterAccess"],
        "compute": ["LambdaFullAccess", "APIGatewayFullAccess"],
        "storage": ["S3FullAccess", "DynamoDBFullAccess"],
        "networking": ["VPCManagement", "CloudFrontAccess"],
        "monitoring": ["CloudWatchFullAccess"],
    }

    for category, expected_sids in categories.items():
        policy = generator.generate_policy_by_category("123456789012", category)
        assert policy["Version"] == "2012-10-17", "Policy version should be 2012-10-17"

        sids = [s["Sid"] for s in policy["Statement"]]
        for expected_sid in expected_sids:
            assert expected_sid in sids, f"Missing {expected_sid} in {category} policy"

    print("✅ Policy generation test passed")


def test_project_detection():
    """Test project detection logic."""
    print("\nTesting project detection...")

    # Note: This test doesn't require AWS credentials
    manager = UnifiedPermissionManager.__new__(UnifiedPermissionManager)

    # Test legacy user
    projects = manager.get_user_projects("project-cicd")
    assert projects == [
        "fraud-or-not",
        "media-register",
        "people-cards",
    ], "Legacy user should have all projects"

    # Test project-specific user
    projects = manager.get_user_projects("fraud-or-not-cicd")
    assert projects == ["fraud-or-not"], "Project-specific user should have one project"

    print("✅ Project detection test passed")


def test_policy_size():
    """Test that generated policies are within AWS limits."""
    print("\nTesting policy size limits...")

    config = ProjectConfig(
        name="test-project",
        display_name="Test Project",
        aws_region="us-east-1",
        enable_waf=True,  # Enable all features
    )

    generator = PolicyGenerator(config)

    # Test categorized policies (new approach)
    print("\nCategorized policy sizes:")
    categories = ["infrastructure", "compute", "storage", "networking", "monitoring"]
    total_size = 0

    for category in categories:
        cat_policy = generator.generate_policy_by_category("123456789012", category)
        cat_size = len(json.dumps(cat_policy))
        total_size += cat_size
        print(f"  {category}: {cat_size} chars")

        # All category policies should fit in inline policy limit
        assert cat_size < 2048, f"{category} policy exceeds inline limit"

    print(f"\nTotal across categories: {total_size} chars")
    print(f"✅ All categorized policies within limits!")


def main():
    """Run all tests."""
    print("Running unified permissions integration tests...\n")

    tests = [test_policy_generation, test_project_detection, test_policy_size]

    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} error: {e}")
            failed += 1

    print(f"\n{'='*50}")
    if failed == 0:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {failed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
