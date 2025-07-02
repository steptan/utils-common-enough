#!/usr/bin/env python3
"""
CLI tests for unified permissions script.
"""

import sys
import subprocess
from pathlib import Path

# Script path
SCRIPT_PATH = Path(__file__).parent.parent / "src" / "scripts" / "unified_user_permissions.py"


def run_command(args):
    """Run the unified permissions script with given arguments."""
    cmd = [sys.executable, str(SCRIPT_PATH)] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def test_help():
    """Test help command."""
    print("Testing help command...")
    result = run_command(["--help"])
    
    assert result.returncode == 0, f"Help command failed: {result.stderr}"
    assert "Unified IAM permission management" in result.stdout
    assert "update" in result.stdout
    assert "show" in result.stdout
    assert "list-users" in result.stdout
    
    print("✅ Help command test passed")


def test_command_help():
    """Test individual command help."""
    print("\nTesting command help...")
    
    commands = ["update", "show", "list-users", "update-all", "generate"]
    
    for cmd in commands:
        result = run_command([cmd, "--help"])
        assert result.returncode == 0, f"{cmd} help failed: {result.stderr}"
        assert "--help" in result.stdout or "Options:" in result.stdout
    
    print("✅ Command help test passed")


def test_generate_dry_run():
    """Test generate command."""
    print("\nTesting generate command...")
    
    # Generate command should work and output JSON
    result = run_command([
        "generate",
        "--user", "test-user",
        "--projects", "fraud-or-not"
    ])
    
    # Should succeed and output valid JSON
    assert result.returncode == 0, f"Generate failed: {result.stderr}"
    assert result.stdout, "No output from generate command"
    
    # Try to parse as JSON
    import json
    try:
        policy = json.loads(result.stdout)
        assert policy["Version"] == "2012-10-17"
        assert len(policy["Statement"]) > 0
    except json.JSONDecodeError:
        assert False, "Output is not valid JSON"
    
    print("✅ Generate test passed")


def test_invalid_command():
    """Test invalid command handling."""
    print("\nTesting invalid command...")
    
    result = run_command(["invalid-command"])
    
    assert result.returncode != 0
    assert "Error" in result.stderr or "Usage" in result.stdout
    
    print("✅ Invalid command test passed")


def test_missing_required_args():
    """Test handling of missing required arguments."""
    print("\nTesting missing required arguments...")
    
    # Update command without user
    result = run_command(["update"])
    assert result.returncode != 0
    assert "Missing option" in result.stderr or "required" in result.stderr.lower()
    
    # Show command without user
    result = run_command(["show"])
    assert result.returncode != 0
    assert "Missing option" in result.stderr or "required" in result.stderr.lower()
    
    print("✅ Missing arguments test passed")


def main():
    """Run all CLI tests."""
    print("Running unified permissions CLI tests...\n")
    
    tests = [
        test_help,
        test_command_help,
        test_generate_dry_run,
        test_invalid_command,
        test_missing_required_args
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
        print("✅ All CLI tests passed!")
        return 0
    else:
        print(f"❌ {failed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())