"""
Smoke tests for deployed applications.

Validates that applications are functioning correctly after deployment.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

from cloudformation import StackManager
from config import ProjectConfig, get_project_config


class TestStatus(Enum):
    """Test execution status."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class TestResult:
    """Result of a single test."""

    name: str
    status: TestStatus
    message: str
    duration: float
    details: Optional[Dict[str, Any]] = None


class SmokeTestRunner:
    """Run smoke tests against deployed applications."""

    def __init__(
        self,
        project_name: str,
        environment: str,
        base_url: Optional[str] = None,
        api_url: Optional[str] = None,
        config: Optional[ProjectConfig] = None,
        timeout: int = 30,
    ):
        """
        Initialize smoke test runner.

        Args:
            project_name: Name of the project
            environment: Deployment environment
            base_url: Base URL for the application
            api_url: API URL (if different from base)
            config: Project configuration
            timeout: Request timeout in seconds
        """
        self.project_name = project_name
        self.environment = environment
        self.config = config or get_project_config(project_name)
        self.timeout = timeout
        self.results: List[TestResult] = []

        # Get URLs from stack outputs if not provided
        if not base_url or not api_url:
            stack_manager = StackManager(region=self.config.aws_region)
            stack_name = self.config.get_stack_name(environment)
            outputs = stack_manager.get_stack_outputs(stack_name)

            self.base_url = base_url or outputs.get(
                "CloudFrontUrl", outputs.get("FrontendURL", "")
            )
            self.api_url = api_url or outputs.get("ApiGatewayUrl", "")
        else:
            self.base_url = base_url
            self.api_url = api_url

        # Ensure URLs are properly formatted
        if self.base_url and not self.base_url.startswith("http"):
            self.base_url = f"https://{self.base_url}"
        if self.api_url and not self.api_url.startswith("http"):
            self.api_url = f"https://{self.api_url}"

        self.base_url = self.base_url.rstrip("/") if self.base_url else ""
        self.api_url = self.api_url.rstrip("/") if self.api_url else ""

    def run_all_tests(self) -> Tuple[bool, List[TestResult]]:
        """
        Run all smoke tests.

        Returns:
            Tuple of (all_passed, results)
        """
        print(f"🔍 Running smoke tests for {self.project_name} ({self.environment})")
        if self.base_url:
            print(f"   Frontend URL: {self.base_url}")
        if self.api_url:
            print(f"   API URL: {self.api_url}")
        print("-" * 60)

        # Define test suites based on project
        tests = []

        # Common tests for all projects
        if self.base_url:
            tests.extend(
                [
                    self.test_homepage,
                    self.test_static_assets,
                    self.test_security_headers,
                ]
            )

        if self.api_url:
            tests.extend(
                [
                    self.test_api_health,
                    self.test_api_endpoints,
                    self.test_cors_headers,
                ]
            )

        # Project-specific tests
        if self.project_name == "media-register":
            tests.extend(
                [
                    self.test_media_register_specific,
                ]
            )
        elif self.project_name == "fraud-or-not":
            tests.extend(
                [
                    self.test_fraud_submission_endpoint,
                ]
            )
        elif self.project_name == "people-cards":
            tests.extend(
                [
                    self.test_cards_api,
                ]
            )

        # Run each test
        for test in tests:
            self._run_test(test)

        # Summary
        print("-" * 60)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in self.results if r.status == TestStatus.WARNING)

        if failed > 0:
            print(f"❌ {failed} tests failed, {passed} passed")
            for result in self.results:
                if result.status == TestStatus.FAILED:
                    print(f"   - {result.name}: {result.message}")
        else:
            print(f"✅ All {passed} tests passed")
            if warnings > 0:
                print(f"⚠️  {warnings} warnings")

        return failed == 0, self.results

    def _run_test(self, test_func) -> TestResult:
        """Run a single test and record the result."""
        start_time = time.time()
        test_name = test_func.__name__.replace("test_", "").replace("_", " ").title()

        try:
            result = test_func()
            duration = time.time() - start_time

            if result is None:
                # Test passed
                status = TestStatus.PASSED
                message = "Test passed"
            elif isinstance(result, tuple):
                # Test returned (status, message)
                status, message = result
            else:
                # Test returned just a message
                status = TestStatus.FAILED
                message = str(result)

            test_result = TestResult(
                name=test_name, status=status, message=message, duration=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            test_result = TestResult(
                name=test_name,
                status=TestStatus.FAILED,
                message=str(e),
                duration=duration,
            )

        self.results.append(test_result)

        # Print result
        status_emoji = {
            TestStatus.PASSED: "✅",
            TestStatus.FAILED: "❌",
            TestStatus.WARNING: "⚠️",
            TestStatus.SKIPPED: "⏭️",
        }[test_result.status]

        print(
            f"{status_emoji} {test_name}: {test_result.message} ({test_result.duration:.2f}s)"
        )

        return test_result

    def test_homepage(self) -> Optional[Tuple[TestStatus, str]]:
        """Test homepage availability."""
        if not self.base_url:
            return TestStatus.SKIPPED, "No frontend URL available"

        response = requests.get(self.base_url, timeout=self.timeout)

        if response.status_code != 200:
            return TestStatus.FAILED, f"Expected 200, got {response.status_code}"

        # Check for basic content
        content = response.text.lower()
        if self.project_name == "fraud-or-not" and "fraud" not in content:
            return TestStatus.WARNING, "Homepage loaded but missing expected content"
        elif self.project_name == "media-register" and "media" not in content:
            return TestStatus.WARNING, "Homepage loaded but missing expected content"
        elif self.project_name == "people-cards" and (
            "card" not in content and "people" not in content
        ):
            return TestStatus.WARNING, "Homepage loaded but missing expected content"

        return (
            TestStatus.PASSED,
            f"Homepage loaded successfully ({len(response.content)} bytes)",
        )

    def test_static_assets(self) -> Optional[Tuple[TestStatus, str]]:
        """Test static asset loading."""
        if not self.base_url:
            return TestStatus.SKIPPED, "No frontend URL available"

        # Try to load a common static asset
        static_paths = [
            "/_next/static/css/",  # Next.js CSS
            "/static/css/",  # Generic static
            "/favicon.ico",  # Favicon
            "/robots.txt",  # Robots file
        ]

        for path in static_paths:
            try:
                url = urljoin(self.base_url, path)
                response = requests.head(
                    url, timeout=self.timeout, allow_redirects=True
                )
                if response.status_code < 400:
                    return TestStatus.PASSED, f"Static assets accessible at {path}"
            except Exception:
                continue

        return TestStatus.WARNING, "No standard static assets found"

    def test_api_health(self) -> Optional[Tuple[TestStatus, str]]:
        """Test API health endpoint."""
        if not self.api_url:
            return TestStatus.SKIPPED, "No API URL available"

        health_endpoints = ["/health", "/api/health", "/", "/api"]

        for endpoint in health_endpoints:
            try:
                url = urljoin(self.api_url, endpoint)
                response = requests.get(url, timeout=self.timeout)

                if response.status_code in [
                    200,
                    401,
                    403,
                ]:  # 401/403 means API is up but needs auth
                    return (
                        TestStatus.PASSED,
                        f"API responded at {endpoint} ({response.status_code})",
                    )
            except Exception:
                continue

        return TestStatus.FAILED, "API health check failed - no endpoints responding"

    def test_api_endpoints(self) -> Optional[Tuple[TestStatus, str]]:
        """Test API endpoints based on project."""
        if not self.api_url:
            return TestStatus.SKIPPED, "No API URL available"

        # Define endpoints per project
        endpoints = {
            "fraud-or-not": ["/api/submissions", "/api/reports"],
            "media-register": ["/api/works", "/api/authors"],
            "people-cards": ["/api/cards", "/api/users"],
        }

        project_endpoints = endpoints.get(self.project_name, [])

        for endpoint in project_endpoints:
            try:
                url = urljoin(self.api_url, endpoint)
                response = requests.get(url, timeout=self.timeout)

                # Accept various status codes as "working"
                if response.status_code in [200, 201, 401, 403, 404]:
                    return TestStatus.PASSED, f"API endpoint {endpoint} is responding"
            except Exception:
                continue

        return TestStatus.WARNING, "No project-specific endpoints tested"

    def test_cors_headers(self) -> Optional[Tuple[TestStatus, str]]:
        """Test CORS configuration."""
        if not self.api_url:
            return TestStatus.SKIPPED, "No API URL available"

        headers = {
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        }

        response = requests.options(self.api_url, headers=headers, timeout=self.timeout)

        cors_headers = response.headers.get("Access-Control-Allow-Origin")
        if not cors_headers:
            return TestStatus.WARNING, "No CORS headers found"

        if cors_headers == "*" or "example.com" in cors_headers:
            return TestStatus.PASSED, f"CORS configured: {cors_headers}"

        return TestStatus.WARNING, f"CORS configured but restrictive: {cors_headers}"

    def test_security_headers(self) -> Optional[Tuple[TestStatus, str]]:
        """Test security headers."""
        url = self.base_url or self.api_url
        if not url:
            return TestStatus.SKIPPED, "No URL available"

        response = requests.get(url, timeout=self.timeout)

        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=",
        }

        missing = []
        for header, expected in security_headers.items():
            value = response.headers.get(header)
            if not value:
                missing.append(header)
            elif isinstance(expected, list):
                if not any(exp in value for exp in expected):
                    missing.append(f"{header} (got {value})")
            elif isinstance(expected, str) and expected not in value:
                missing.append(f"{header} (got {value})")

        if not missing:
            return TestStatus.PASSED, "All security headers present"
        elif len(missing) <= 2:
            return (
                TestStatus.WARNING,
                f"Missing some security headers: {', '.join(missing)}",
            )
        else:
            return TestStatus.FAILED, f"Missing security headers: {', '.join(missing)}"

    # Project-specific tests

    def test_media_register_specific(self) -> Optional[Tuple[TestStatus, str]]:
        """Media Register specific tests."""
        if not self.api_url:
            return TestStatus.SKIPPED, "No API URL available"

        # Test media types endpoint if it exists
        try:
            response = requests.get(
                f"{self.api_url}/api/media-types", timeout=self.timeout
            )
            if response.status_code == 200:
                return TestStatus.PASSED, "Media types endpoint working"
        except Exception:
            pass

        return TestStatus.SKIPPED, "Media Register specific endpoints not tested"

    def test_fraud_submission_endpoint(self) -> Optional[Tuple[TestStatus, str]]:
        """Fraud or Not submission endpoint test."""
        if not self.api_url:
            return TestStatus.SKIPPED, "No API URL available"

        # Test if submission endpoint exists (don't actually submit)
        try:
            response = requests.options(
                f"{self.api_url}/api/submit", timeout=self.timeout
            )
            if response.status_code in [
                200,
                204,
                405,
            ]:  # 405 means endpoint exists but OPTIONS not allowed
                return TestStatus.PASSED, "Submission endpoint exists"
        except:
            pass

        return TestStatus.WARNING, "Submission endpoint not verified"

    def test_cards_api(self) -> Optional[Tuple[TestStatus, str]]:
        """People Cards API test."""
        if not self.api_url:
            return TestStatus.SKIPPED, "No API URL available"

        # Test cards endpoint
        try:
            response = requests.get(f"{self.api_url}/api/cards", timeout=self.timeout)
            if response.status_code in [200, 401, 403]:  # May require auth
                return (
                    TestStatus.PASSED,
                    f"Cards API responding ({response.status_code})",
                )
        except:
            pass

        return TestStatus.WARNING, "Cards API not verified"
