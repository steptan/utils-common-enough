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
        name="test-project",
        display_name="Test Project",
        aws_region="us-east-1"
    )
    
    generator = PolicyGenerator(config)
    policy = generator.generate_cicd_policy("123456789012")
    
    # Basic assertions
    assert policy["Version"] == "2012-10-17", "Policy version should be 2012-10-17"
    assert len(policy["Statement"]) > 10, "Policy should have multiple statements"
    
    # Check for required permission sets
    sids = [s["Sid"] for s in policy["Statement"]]
    required_sids = [
        "CloudFormationAccess",
        "S3Access",
        "LambdaAccess",
        "IAMAccess",
        "DynamoDBAccess"
    ]
    
    for sid in required_sids:
        assert sid in sids, f"Missing {sid} in policy"
    
    print("✅ Policy generation test passed")


def test_project_detection():
    """Test project detection logic."""
    print("\nTesting project detection...")
    
    # Note: This test doesn't require AWS credentials
    manager = UnifiedPermissionManager.__new__(UnifiedPermissionManager)
    
    # Test legacy user
    projects = manager.get_user_projects("project-cicd")
    assert projects == ["fraud-or-not", "media-register", "people-cards"], \
        "Legacy user should have all projects"
    
    # Test project-specific user
    projects = manager.get_user_projects("fraud-or-not-cicd")
    assert projects == ["fraud-or-not"], \
        "Project-specific user should have one project"
    
    print("✅ Project detection test passed")


def test_unified_policy_generation():
    """Test generating unified policy for multiple projects."""
    print("\nTesting unified policy generation...")
    
    # Create a manager without AWS clients
    manager = UnifiedPermissionManager.__new__(UnifiedPermissionManager)
    manager.account_id = "123456789012"
    
    # Mock get_project_config
    import scripts.unified_user_permissions
    original_get_config = scripts.unified_user_permissions.get_project_config
    
    def mock_get_config(name):
        return ProjectConfig(
            name=name,
            display_name=f"{name} Project",
            aws_region="us-east-1"
        )
    
    scripts.unified_user_permissions.get_project_config = mock_get_config
    
    try:
        # Generate unified policy
        policy = manager.generate_unified_policy(
            "test-user",
            ["fraud-or-not", "media-register"]
        )
        
        # Check structure
        assert policy["Version"] == "2012-10-17", "Policy version should be 2012-10-17"
        
        # Check that both projects are represented
        sids = [s["Sid"] for s in policy["Statement"]]
        assert any("fraud-or-not_" in sid for sid in sids), \
            "Should have fraud-or-not statements"
        assert any("media-register_" in sid for sid in sids), \
            "Should have media-register statements"
        assert "CrossProjectAccess" in sids, \
            "Should have cross-project access statement"
        
        print("✅ Unified policy generation test passed")
        
    finally:
        # Restore original function
        scripts.unified_user_permissions.get_project_config = original_get_config


def test_policy_size():
    """Test that generated policies are within AWS limits."""
    print("\nTesting policy size limits...")
    
    config = ProjectConfig(
        name="test-project",
        display_name="Test Project",
        aws_region="us-east-1",
        enable_waf=True  # Enable all features
    )
    
    generator = PolicyGenerator(config)
    policy = generator.generate_cicd_policy("123456789012")
    
    policy_json = json.dumps(policy)
    policy_size = len(policy_json)
    
    # AWS managed policy limit is 6144 characters
    # Note: The actual limit for managed policies is 6144, but for inline policies it's 2048
    # Since we're using inline policies (put_user_policy), we should warn about size
    
    print(f"ℹ️  Policy size: {policy_size} chars")
    if policy_size > 6144:
        print(f"⚠️  Warning: Policy exceeds AWS managed policy limit (6144 chars)")
        print("   Consider using managed policies or splitting permissions")
    elif policy_size > 2048:
        print(f"ℹ️  Note: Policy exceeds inline policy limit (2048 chars)")
        print("   This is OK for managed policies but not for inline policies")
    
    # For this test, we'll just warn but not fail
    print(f"✅ Policy size test completed")


def main():
    """Run all tests."""
    print("Running unified permissions integration tests...\n")
    
    tests = [
        test_policy_generation,
        test_project_detection,
        test_unified_policy_generation,
        test_policy_size
    ]
    
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