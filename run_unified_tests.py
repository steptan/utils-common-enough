#!/usr/bin/env python3
"""
Simple test runner for unified permissions tests.
"""

import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import tests
from tests.test_unified_permissions import (
    TestPolicyGenerator,
    TestUnifiedPermissionManager,
    TestCLICommands,
    TestErrorHandling
)

if __name__ == "__main__":
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    for test_class in [TestPolicyGenerator, TestUnifiedPermissionManager, TestCLICommands, TestErrorHandling]:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)