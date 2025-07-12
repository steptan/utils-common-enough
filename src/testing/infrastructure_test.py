#!/usr/bin/env python3
"""
Infrastructure test script - consolidated from test_deploy.py

Simple test script to validate infrastructure setup without heavy dependencies
"""

import json
import os
from pathlib import Path
from typing import Callable, List, Tuple


class InfrastructureValidator:
    """Validate infrastructure setup"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()

    def test_file_structure(self) -> bool:
        """Test that all required files exist"""
        required_files = [
            "config/base.yaml",
            "config/environments/dev.yaml",
            "config/environments/prod.yaml",
            "config/validation/schema.yaml",
            "constructs/__init__.py",
            "constructs/storage.py",
            "constructs/network.py",
            "constructs/compute.py",
            "constructs/api_gateway.py",
            "constructs/distribution.py",
            "src/lambda/fraud_reports.py",
            "src/lambda/comments.py",
            "src/lambda/image_processor.py",
            "deploy.py",
            "requirements.txt",
        ]

        missing_files = []
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)

        if missing_files:
            print("❌ Missing files:")
            for file in missing_files:
                print(f"  - {file}")
            return False
        else:
            print("✅ All required files exist")
            return True

    def test_directory_structure(self) -> bool:
        """Test that all required directories exist"""
        required_dirs = [
            "config",
            "config/environments",
            "config/validation",
            "constructs",
            "patterns",
            "deployments",
            "deployments/dev",
            "deployments/staging",
            "deployments/prod",
            "tests",
            "tests/unit",
            "tests/integration",
            "tests/fixtures",
            "src",
            "src/lambda",
        ]

        missing_dirs = []
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                missing_dirs.append(dir_path)

        if missing_dirs:
            print("❌ Missing directories:")
            for dir in missing_dirs:
                print(f"  - {dir}")
            return False
        else:
            print("✅ All required directories exist")
            return True

    def test_construct_imports(self) -> bool:
        """Test that construct classes can be imported"""
        try:
            # Add project root to path
            import sys

            sys.path.insert(0, str(self.project_root))

            # Test if files are valid Python
            constructs = [
                "constructs.storage",
                "constructs.network",
                "constructs.compute",
                "constructs.api_gateway",
                "constructs.distribution",
            ]

            for construct in constructs:
                try:
                    module = __import__(construct, fromlist=[""])
                    print(f"✅ {construct} - valid Python syntax")
                except SyntaxError as e:
                    print(f"❌ {construct} - syntax error: {e}")
                    return False
                except ImportError as e:
                    if "yaml" in str(e):
                        print(f"⚠️  {construct} - needs PyYAML dependency")
                    else:
                        print(f"❌ {construct} - import error: {e}")
                        return False

            return True

        except Exception as e:
            print(f"❌ Error testing imports: {e}")
            return False

    def test_lambda_handlers(self) -> bool:
        """Test that Lambda handlers are valid Python"""
        handlers = [
            "src.lambda.fraud_reports",
            "src.lambda.comments",
            "src.lambda.image_processor",
        ]

        try:
            import sys

            sys.path.insert(0, str(self.project_root))

            for handler in handlers:
                try:
                    module = __import__(handler, fromlist=[""])
                    if hasattr(module, "lambda_handler"):
                        print(f"✅ {handler} - has lambda_handler function")
                    else:
                        print(f"⚠️  {handler} - missing lambda_handler function")
                except SyntaxError as e:
                    print(f"❌ {handler} - syntax error: {e}")
                    return False
                except ImportError as e:
                    print(f"⚠️  {handler} - import dependency issue: {e}")

            return True

        except Exception as e:
            print(f"❌ Error testing handlers: {e}")
            return False

    def test_utils_integration(self) -> bool:
        """Test that utils submodule is properly set up"""
        utils_path = self.project_root / "utils"

        if not utils_path.exists():
            print("❌ Utils submodule not found")
            return False

        if not (utils_path / "src").exists():
            print("❌ Utils src directory not found")
            return False

        # Check for key utils modules
        required_utils = [
            "utils/src/deployment",
            "utils/src/cloudformation",
            "utils/src/lambda_utils",
            "utils/src/scripts",
        ]

        missing = []
        for util_path in required_utils:
            if not (self.project_root / util_path).exists():
                missing.append(util_path)

        if missing:
            print("❌ Missing utils modules:")
            for m in missing:
                print(f"  - {m}")
            return False

        print("✅ Utils submodule properly integrated")
        return True

    def run_all_tests(self) -> bool:
        """Run all validation tests"""
        print("🔍 Testing Fraud-or-Not Infrastructure Setup")
        print("=" * 50)

        tests: List[Tuple[str, Callable[[], bool]]] = [
            ("File Structure", self.test_file_structure),
            ("Directory Structure", self.test_directory_structure),
            ("Construct Imports", self.test_construct_imports),
            ("Lambda Handlers", self.test_lambda_handlers),
            ("Utils Integration", self.test_utils_integration),
        ]

        results = []
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}:")
            result = test_func()
            results.append(result)

        print("\n" + "=" * 50)
        if all(results):
            print("🎉 All tests passed! Infrastructure setup is complete.")
            print("\nNext steps:")
            print("1. Install dependencies: pip install -r requirements.txt")
            print("2. Test deployment: python deploy.py dev --dry-run")
            print("3. Deploy to AWS: python deploy.py dev")
        else:
            print("❌ Some tests failed. Please fix the issues above.")

        return all(results)


def main():
    """Main test function"""
    import argparse

    parser = argparse.ArgumentParser(description="Test infrastructure setup")
    parser.add_argument("--project-root", type=Path, help="Project root directory")

    args = parser.parse_args()

    # If no project root specified, try to find it
    if not args.project_root:
        # Look for project root (where .gitmodules exists)
        current = Path.cwd()
        while current != current.parent:
            if (current / ".gitmodules").exists():
                args.project_root = current
                break
            current = current.parent
        else:
            args.project_root = Path.cwd()

    validator = InfrastructureValidator(project_root=args.project_root)
    success = validator.run_all_tests()

    return 0 if success else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
