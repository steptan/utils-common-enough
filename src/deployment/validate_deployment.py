#!/usr/bin/env python3
"""
Validate Media Register deployment by running health checks and basic tests.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    import requests
except ImportError:
    requests = None


class DeploymentValidator:
    """Validates a deployed Media Register application."""

    def __init__(self, outputs_file: str):
        self.outputs_file = Path(outputs_file)
        self.outputs = self._load_outputs()
        self.api_url = self.outputs.get("ApiUrl", "")
        self.website_url = self.outputs.get("WebsiteUrl", "")
        self.results: List[Tuple[str, bool, str]] = []

    def _load_outputs(self) -> Dict[str, str]:
        """Load deployment outputs."""
        if not self.outputs_file.exists():
            print(f"❌ Outputs file not found: {self.outputs_file}")
            return {}

        with open(self.outputs_file) as f:
            return json.load(f)

    def add_result(self, test_name: str, success: bool, message: str) -> None:
        """Add a test result."""
        self.results.append((test_name, success, message))

        icon = "✅" if success else "❌"
        print(f"{icon} {test_name}: {message}")

    def test_api_health(self) -> bool:
        """Test API health endpoint."""
        if requests is None:
            self.add_result("API Health", False, "requests library not installed")
            return False
        
        if not self.api_url:
            self.add_result("API Health", False, "No API URL found")
            return False

        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)

            if response.status_code == 200:
                data: Dict[str, Any] = response.json()
                self.add_result(
                    "API Health",
                    True,
                    f"Healthy - {data.get('service', 'Unknown')} v{data.get('version', 'Unknown')}",
                )
                return True
            else:
                self.add_result(
                    "API Health", False, f"Unhealthy - Status: {response.status_code}"
                )
                return False

        except Exception as e:
            self.add_result("API Health", False, f"Failed: {e}")
            return False

    def test_api_detailed_health(self) -> bool:
        """Test API detailed health endpoint."""
        if requests is None:
            return False
        
        if not self.api_url:
            return False

        try:
            response = requests.get(f"{self.api_url}/health/detailed", timeout=10)

            if response.status_code == 200:
                data: Dict[str, Any] = response.json()
                db_healthy: bool = data.get("database", {}).get("healthy", False)

                self.add_result(
                    "API Detailed Health",
                    db_healthy,
                    f"Database: {'Connected' if db_healthy else 'Disconnected'}",
                )
                return db_healthy
            else:
                self.add_result(
                    "API Detailed Health",
                    False,
                    f"Failed - Status: {response.status_code}",
                )
                return False

        except Exception as e:
            self.add_result("API Detailed Health", False, f"Failed: {e}")
            return False

    def test_website_availability(self) -> bool:
        """Test website availability."""
        if requests is None:
            self.add_result("Website", False, "requests library not installed")
            return False
        
        if not self.website_url:
            self.add_result("Website", False, "No website URL found")
            return False

        try:
            response = requests.get(self.website_url, timeout=10, allow_redirects=True)

            if response.status_code == 200:
                # Check for expected content
                has_content: bool = "Media Register" in response.text

                self.add_result(
                    "Website",
                    has_content,
                    f"{'Available' if has_content else 'Available but missing expected content'}",
                )
                return has_content
            else:
                self.add_result(
                    "Website", False, f"Unavailable - Status: {response.status_code}"
                )
                return False

        except Exception as e:
            self.add_result("Website", False, f"Failed: {e}")
            return False

    def test_api_cors(self) -> bool:
        """Test API CORS configuration."""
        if requests is None:
            return False
        
        if not self.api_url:
            return False

        try:
            response = requests.options(
                f"{self.api_url}/health",
                headers={
                    "Origin": self.website_url or "https://example.com",
                    "Access-Control-Request-Method": "GET",
                },
                timeout=10,
            )

            cors_headers: set[str] = {
                "access-control-allow-origin",
                "access-control-allow-methods",
                "access-control-allow-headers",
            }

            has_cors: bool = all(h in response.headers for h in cors_headers)

            self.add_result(
                "API CORS", has_cors, "Configured" if has_cors else "Not configured"
            )
            return has_cors

        except Exception as e:
            self.add_result("API CORS", False, f"Failed: {e}")
            return False

    def test_api_endpoints(self) -> bool:
        """Test various API endpoints."""
        if requests is None:
            return False
        
        if not self.api_url:
            return False

        endpoints: List[Tuple[str, str, str]] = [
            ("GET", "/authors", "List Authors"),
            ("GET", "/works", "List Works"),
            ("GET", "/health/readiness", "Readiness Check"),
            ("GET", "/health/liveness", "Liveness Check"),
        ]

        all_passed: bool = True

        for method, path, name in endpoints:
            try:
                response = requests.request(method, f"{self.api_url}{path}", timeout=10)

                # We expect 200 for successful endpoints
                # Some might return empty lists which is fine
                success: bool = response.status_code in [200, 201]

                self.add_result(
                    f"API {name}", success, f"Status: {response.status_code}"
                )

                if not success:
                    all_passed = False

            except Exception as e:
                self.add_result(f"API {name}", False, f"Failed: {e}")
                all_passed = False

        return all_passed

    def test_cloudfront_headers(self) -> bool:
        """Test CloudFront cache headers."""
        if requests is None:
            return False
        
        if not self.website_url:
            return False

        try:
            response = requests.get(self.website_url, timeout=10)

            # Check for CloudFront headers
            cf_headers: List[str] = [
                h
                for h in response.headers
                if h.lower().startswith("x-amz-cf-") or h.lower() == "x-cache"
            ]

            has_cf: bool = len(cf_headers) > 0

            self.add_result(
                "CloudFront",
                has_cf,
                (
                    f"Active - {len(cf_headers)} CF headers found"
                    if has_cf
                    else "Not detected"
                ),
            )
            return has_cf

        except Exception as e:
            self.add_result("CloudFront", False, f"Failed: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all validation tests."""
        print("\n🔍 Running deployment validation tests...\n")

        # Basic connectivity tests
        self.test_website_availability()
        self.test_api_health()

        # Detailed tests
        self.test_api_detailed_health()
        self.test_api_cors()
        self.test_cloudfront_headers()

        # API endpoint tests
        self.test_api_endpoints()

        # Summary
        print("\n" + "=" * 50)
        print("📊 Validation Summary")
        print("=" * 50)

        passed: int = sum(1 for _, success, _ in self.results if success)
        total: int = len(self.results)

        print(f"\nTests passed: {passed}/{total}")

        if passed == total:
            print("\n✅ All validation tests passed!")
            return True
        else:
            print("\n❌ Some validation tests failed")
            print("\nFailed tests:")
            for name, success, message in self.results:
                if not success:
                    print(f"  - {name}: {message}")
            return False

    def wait_for_deployment(self, max_wait: int = 300) -> bool:
        """Wait for deployment to be ready."""
        if requests is None:
            print("❌ requests library not installed")
            return False
        
        print(f"\n⏳ Waiting for deployment to be ready (max {max_wait}s)...")

        start_time: float = time.time()

        while time.time() - start_time < max_wait:
            # Check API health
            try:
                response = requests.get(f"{self.api_url}/health", timeout=5)
                if response.status_code == 200:
                    print("✅ Deployment is ready!")
                    return True
            except:
                pass

            # Wait before retrying
            time.sleep(10)
            elapsed: int = int(time.time() - start_time)
            print(f"  Still waiting... ({elapsed}s elapsed)")

        print("❌ Deployment did not become ready in time")
        return False


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Media Register deployment")
    parser.add_argument("outputs_file", help="Path to deployment outputs JSON file")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for deployment to be ready before testing",
    )
    parser.add_argument(
        "--wait-time",
        type=int,
        default=300,
        help="Maximum time to wait in seconds (default: 300)",
    )

    args = parser.parse_args()

    # Create validator
    validator = DeploymentValidator(args.outputs_file)

    # Wait if requested
    if args.wait:
        if not validator.wait_for_deployment(args.wait_time):
            sys.exit(1)

    # Run tests
    if validator.run_all_tests():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
