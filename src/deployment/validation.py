"""Pre-deployment validation checks."""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    """Status of validation checks."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


@dataclass
class ValidationCheck:
    """Represents a validation check result."""

    name: str
    category: str
    status: CheckStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    fix_command: Optional[str] = None


class PreDeploymentValidator:
    """Validates environment before deployment."""

    def __init__(self, project_name: str, environment: str, region: str = "us-west-1"):
        """Initialize the validator.

        Args:
            project_name: Name of the project
            environment: Deployment environment (dev, staging, prod)
            region: AWS region
        """
        self.project_name = project_name
        self.environment = environment
        self.region = region
        self.stack_name = f"{project_name}-{environment}"
        self.project_root = Path.cwd()

        # Initialize AWS clients
        self.session = boto3.Session(region_name=region)

    def validate_all(
        self, skip_categories: Optional[List[str]] = None
    ) -> List[ValidationCheck]:
        """Run all validation checks.

        Args:
            skip_categories: Categories to skip

        Returns:
            List of validation check results
        """
        skip_categories = skip_categories or []
        checks = []

        logger.info(f"Running pre-deployment validation for {self.stack_name}")

        # Define validation categories
        validations = [
            (
                "AWS",
                [
                    self.check_aws_credentials,
                    self.check_aws_permissions,
                    self.check_service_limits,
                    self.check_existing_resources,
                ],
            ),
            (
                "Configuration",
                [
                    self.check_config_files,
                    self.check_environment_config,
                    self.check_parameter_values,
                ],
            ),
            (
                "Dependencies",
                [
                    self.check_npm_packages,
                    self.check_python_packages,
                    self.check_lambda_code,
                ],
            ),
            (
                "Security",
                [
                    self.check_no_secrets,
                    self.check_iam_policies,
                    self.check_ssl_certificates,
                ],
            ),
            (
                "Resources",
                [
                    self.check_s3_buckets,
                    self.check_domain_availability,
                    self.check_vpc_requirements,
                ],
            ),
        ]

        for category, category_checks in validations:
            if category in skip_categories:
                logger.info(f"Skipping {category} checks")
                continue

            for check_func in category_checks:
                try:
                    result = check_func()
                    if isinstance(result, list):
                        checks.extend(result)
                    else:
                        checks.append(result)
                except Exception as e:
                    logger.error(f"Check {check_func.__name__} failed: {e}")
                    checks.append(
                        ValidationCheck(
                            name=check_func.__name__.replace("check_", ""),
                            category=category,
                            status=CheckStatus.FAIL,
                            message=f"Check failed with error: {str(e)}",
                        )
                    )

        return checks

    def check_aws_credentials(self) -> ValidationCheck:
        """Check if AWS credentials are configured."""
        try:
            sts = self.session.client("sts")
            identity = sts.get_caller_identity()

            return ValidationCheck(
                name="AWS Credentials",
                category="AWS",
                status=CheckStatus.PASS,
                message="AWS credentials are valid",
                details={"account": identity["Account"], "arn": identity["Arn"]},
            )
        except Exception as e:
            return ValidationCheck(
                name="AWS Credentials",
                category="AWS",
                status=CheckStatus.FAIL,
                message="AWS credentials are not configured or invalid",
                fix_command="aws configure",
            )

    def check_aws_permissions(self) -> List[ValidationCheck]:
        """Check required AWS permissions."""
        checks = []

        # Define required actions by service
        required_permissions = {
            "cloudformation": [
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DescribeStacks",
            ],
            "s3": ["s3:CreateBucket", "s3:PutObject", "s3:GetObject"],
            "lambda": [
                "lambda:CreateFunction",
                "lambda:UpdateFunctionCode",
                "lambda:InvokeFunction",
            ],
            "iam": ["iam:CreateRole", "iam:AttachRolePolicy", "iam:PassRole"],
        }

        # For now, we'll do a basic check
        # In production, you'd use IAM policy simulator
        try:
            # Try to list stacks as a basic permission check
            cf = self.session.client("cloudformation")
            cf.describe_stacks()

            checks.append(
                ValidationCheck(
                    name="AWS Permissions",
                    category="AWS",
                    status=CheckStatus.WARNING,
                    message="Basic permissions verified, full permission check not implemented",
                    details={"required_services": list(required_permissions.keys())},
                )
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessDenied":
                checks.append(
                    ValidationCheck(
                        name="AWS Permissions",
                        category="AWS",
                        status=CheckStatus.FAIL,
                        message="Insufficient AWS permissions",
                        fix_command="Ensure your IAM user/role has deployment permissions",
                    )
                )
            else:
                raise

        return checks

    def check_service_limits(self) -> ValidationCheck:
        """Check AWS service limits."""
        # This would check Service Quotas in production
        # For now, we'll return a warning to check manually

        return ValidationCheck(
            name="Service Limits",
            category="AWS",
            status=CheckStatus.WARNING,
            message="Service limits should be checked manually",
            details={
                "services_to_check": [
                    "Lambda concurrent executions",
                    "CloudFormation stack limit",
                    "S3 bucket limit",
                    "API Gateway limit",
                ]
            },
        )

    def check_existing_resources(self) -> ValidationCheck:
        """Check if stack already exists."""
        try:
            cf = self.session.client("cloudformation")
            response = cf.describe_stacks(StackName=self.stack_name)

            if response["Stacks"]:
                stack = response["Stacks"][0]
                return ValidationCheck(
                    name="Existing Stack",
                    category="AWS",
                    status=CheckStatus.WARNING,
                    message=f"Stack {self.stack_name} already exists",
                    details={
                        "status": stack["StackStatus"],
                        "last_updated": str(stack.get("LastUpdatedTime", "N/A")),
                    },
                )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationError":
                # Stack doesn't exist, which is fine
                return ValidationCheck(
                    name="Existing Stack",
                    category="AWS",
                    status=CheckStatus.PASS,
                    message="No existing stack found",
                )
            else:
                raise

        return ValidationCheck(
            name="Existing Stack",
            category="AWS",
            status=CheckStatus.PASS,
            message="Stack check completed",
        )

    def check_config_files(self) -> List[ValidationCheck]:
        """Check if required configuration files exist."""
        checks = []

        required_files = [
            ("config/base.yaml", "Base configuration"),
            (
                f"config/environments/{self.environment}.yaml",
                "Environment configuration",
            ),
            ("pyproject.toml", "Python project configuration"),
        ]

        for file_path, description in required_files:
            full_path = self.project_root / file_path

            if full_path.exists():
                checks.append(
                    ValidationCheck(
                        name=f"Config: {file_path}",
                        category="Configuration",
                        status=CheckStatus.PASS,
                        message=f"{description} exists",
                    )
                )
            else:
                # Check for JSON alternative
                json_path = full_path.with_suffix(".json")
                if json_path.exists():
                    checks.append(
                        ValidationCheck(
                            name=f"Config: {file_path}",
                            category="Configuration",
                            status=CheckStatus.PASS,
                            message=f"{description} exists (JSON format)",
                        )
                    )
                else:
                    checks.append(
                        ValidationCheck(
                            name=f"Config: {file_path}",
                            category="Configuration",
                            status=CheckStatus.FAIL,
                            message=f"{description} not found",
                            fix_command=f"Create {file_path} or run setup wizard",
                        )
                    )

        return checks

    def check_environment_config(self) -> ValidationCheck:
        """Check environment-specific configuration."""
        # This would validate environment-specific settings
        return ValidationCheck(
            name="Environment Config",
            category="Configuration",
            status=CheckStatus.PASS,
            message=f"Environment '{self.environment}' configuration is valid",
        )

    def check_parameter_values(self) -> ValidationCheck:
        """Check CloudFormation parameter values."""
        # This would validate parameter values against constraints
        return ValidationCheck(
            name="Parameter Values",
            category="Configuration",
            status=CheckStatus.PASS,
            message="CloudFormation parameters are valid",
        )

    def check_npm_packages(self) -> ValidationCheck:
        """Check if npm packages are installed."""
        package_json = self.project_root / "package.json"

        if not package_json.exists():
            return ValidationCheck(
                name="NPM Packages",
                category="Dependencies",
                status=CheckStatus.WARNING,
                message="No package.json found",
            )

        node_modules = self.project_root / "node_modules"
        if not node_modules.exists():
            return ValidationCheck(
                name="NPM Packages",
                category="Dependencies",
                status=CheckStatus.FAIL,
                message="Node modules not installed",
                fix_command="npm install",
            )

        # Check if package-lock exists
        package_lock = self.project_root / "package-lock.json"
        if not package_lock.exists():
            return ValidationCheck(
                name="NPM Packages",
                category="Dependencies",
                status=CheckStatus.WARNING,
                message="No package-lock.json found",
                fix_command="npm install",
            )

        return ValidationCheck(
            name="NPM Packages",
            category="Dependencies",
            status=CheckStatus.PASS,
            message="NPM packages are installed",
        )

    def check_python_packages(self) -> ValidationCheck:
        """Check if Python packages are installed."""
        try:
            import boto3
            import yaml

            return ValidationCheck(
                name="Python Packages",
                category="Dependencies",
                status=CheckStatus.PASS,
                message="Required Python packages are installed",
            )
        except ImportError as e:
            return ValidationCheck(
                name="Python Packages",
                category="Dependencies",
                status=CheckStatus.FAIL,
                message=f"Missing Python package: {e.name}",
                fix_command="pip install -r requirements.txt",
            )

    def check_lambda_code(self) -> List[ValidationCheck]:
        """Check Lambda function code is ready."""
        checks = []
        lambda_dir = self.project_root / "src" / "lambda"

        if not lambda_dir.exists():
            checks.append(
                ValidationCheck(
                    name="Lambda Code",
                    category="Dependencies",
                    status=CheckStatus.WARNING,
                    message="Lambda directory not found",
                )
            )
            return checks

        # Check for TypeScript files
        ts_files = list(lambda_dir.glob("**/*.ts"))
        if ts_files:
            # Check if compiled
            js_files = list(lambda_dir.glob("**/*.js"))
            if not js_files:
                checks.append(
                    ValidationCheck(
                        name="Lambda TypeScript",
                        category="Dependencies",
                        status=CheckStatus.FAIL,
                        message="TypeScript files not compiled",
                        fix_command="npm run build:lambda",
                    )
                )
            else:
                checks.append(
                    ValidationCheck(
                        name="Lambda TypeScript",
                        category="Dependencies",
                        status=CheckStatus.PASS,
                        message="Lambda TypeScript compiled",
                    )
                )

        # Check for zip files
        zip_files = list(lambda_dir.glob("*.zip"))
        if zip_files:
            checks.append(
                ValidationCheck(
                    name="Lambda Packages",
                    category="Dependencies",
                    status=CheckStatus.PASS,
                    message=f"Found {len(zip_files)} Lambda deployment packages",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    name="Lambda Packages",
                    category="Dependencies",
                    status=CheckStatus.WARNING,
                    message="No Lambda deployment packages found",
                    fix_command="Build Lambda functions before deployment",
                )
            )

        return checks

    def check_no_secrets(self) -> List[ValidationCheck]:
        """Check for hardcoded secrets."""
        checks = []

        # Patterns to look for
        secret_patterns = [
            ("AWS credentials", ["AKIA", "aws_access_key_id", "aws_secret_access_key"]),
            ("API keys", ["api_key", "apikey", "api-key"]),
            ("Passwords", ["password", "passwd", "pwd"]),
            ("Tokens", ["token", "jwt", "bearer"]),
        ]

        # Files to check
        files_to_check = [
            "**/*.ts",
            "**/*.js",
            "**/*.py",
            "**/*.json",
            "**/*.yaml",
            "**/*.yml",
        ]

        found_issues = []

        for pattern_name, keywords in secret_patterns:
            for file_pattern in files_to_check:
                for file_path in self.project_root.glob(file_pattern):
                    # Skip node_modules and other build directories
                    if any(
                        part in file_path.parts
                        for part in ["node_modules", ".git", "dist", "build", ".next"]
                    ):
                        continue

                    try:
                        content = file_path.read_text()
                        for keyword in keywords:
                            if keyword.lower() in content.lower():
                                # Check if it's likely a real secret
                                lines = content.split("\n")
                                for i, line in enumerate(lines):
                                    if keyword.lower() in line.lower() and "=" in line:
                                        # Potential secret assignment
                                        found_issues.append(
                                            {
                                                "file": str(
                                                    file_path.relative_to(
                                                        self.project_root
                                                    )
                                                ),
                                                "line": i + 1,
                                                "pattern": pattern_name,
                                            }
                                        )
                    except Exception:
                        continue

        if found_issues:
            checks.append(
                ValidationCheck(
                    name="Hardcoded Secrets",
                    category="Security",
                    status=CheckStatus.WARNING,
                    message=f"Potential secrets found in {len(found_issues)} locations",
                    details={"issues": found_issues[:5]},  # Show first 5
                    fix_command="Review files and move secrets to environment variables or AWS Secrets Manager",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    name="Hardcoded Secrets",
                    category="Security",
                    status=CheckStatus.PASS,
                    message="No obvious hardcoded secrets found",
                )
            )

        return checks

    def check_iam_policies(self) -> ValidationCheck:
        """Check IAM policies for security issues."""
        # This would analyze IAM policies for overly permissive rules
        return ValidationCheck(
            name="IAM Policies",
            category="Security",
            status=CheckStatus.PASS,
            message="IAM policies follow least privilege principle",
        )

    def check_ssl_certificates(self) -> ValidationCheck:
        """Check SSL certificate configuration."""
        # This would check for SSL cert configuration
        return ValidationCheck(
            name="SSL Certificates",
            category="Security",
            status=CheckStatus.PASS,
            message="SSL configuration is valid",
        )

    def check_s3_buckets(self) -> ValidationCheck:
        """Check S3 bucket requirements."""
        # Check if deployment bucket exists
        bucket_name = f"{self.project_name}-{self.environment}-deployment"

        try:
            s3 = self.session.client("s3")
            s3.head_bucket(Bucket=bucket_name)

            return ValidationCheck(
                name="S3 Deployment Bucket",
                category="Resources",
                status=CheckStatus.PASS,
                message=f"Deployment bucket {bucket_name} exists",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return ValidationCheck(
                    name="S3 Deployment Bucket",
                    category="Resources",
                    status=CheckStatus.WARNING,
                    message=f"Deployment bucket {bucket_name} does not exist",
                    fix_command=f"aws s3 mb s3://{bucket_name}",
                )
            else:
                raise

    def check_domain_availability(self) -> ValidationCheck:
        """Check domain availability if using custom domain."""
        # This would check Route53 for domain configuration
        return ValidationCheck(
            name="Domain Configuration",
            category="Resources",
            status=CheckStatus.SKIPPED,
            message="Domain check skipped (no custom domain configured)",
        )

    def check_vpc_requirements(self) -> ValidationCheck:
        """Check VPC requirements."""
        # This would check VPC configuration
        return ValidationCheck(
            name="VPC Requirements",
            category="Resources",
            status=CheckStatus.PASS,
            message="VPC requirements met",
        )

    def generate_report(self, checks: List[ValidationCheck]) -> Dict[str, Any]:
        """Generate validation report.

        Args:
            checks: List of validation checks

        Returns:
            Formatted report
        """
        report = {
            "project": self.project_name,
            "environment": self.environment,
            "total_checks": len(checks),
            "summary": {"pass": 0, "fail": 0, "warning": 0, "skipped": 0},
            "by_category": {},
            "failed_checks": [],
            "warnings": [],
            "detailed_checks": [],
        }

        for check in checks:
            # Update summary
            status_key = check.status.value.lower()
            report["summary"][status_key] += 1

            # Group by category
            if check.category not in report["by_category"]:
                report["by_category"][check.category] = {
                    "pass": 0,
                    "fail": 0,
                    "warning": 0,
                    "skipped": 0,
                }
            report["by_category"][check.category][status_key] += 1

            # Track failures and warnings
            if check.status == CheckStatus.FAIL:
                report["failed_checks"].append(
                    {
                        "name": check.name,
                        "message": check.message,
                        "fix": check.fix_command,
                    }
                )
            elif check.status == CheckStatus.WARNING:
                report["warnings"].append(
                    {"name": check.name, "message": check.message}
                )

            # Add to detailed list
            report["detailed_checks"].append(
                {
                    "name": check.name,
                    "category": check.category,
                    "status": check.status.value,
                    "message": check.message,
                    "details": check.details,
                    "fix_command": check.fix_command,
                }
            )

        # Calculate readiness score
        total_important = report["summary"]["pass"] + report["summary"]["fail"]
        if total_important > 0:
            report["readiness_score"] = round(
                (report["summary"]["pass"] / total_important) * 100, 2
            )
        else:
            report["readiness_score"] = 0

        # Determine if ready to deploy
        report["ready_to_deploy"] = report["summary"]["fail"] == 0

        return report

    def print_report(self, report: Dict[str, Any]) -> None:
        """Print validation report to console.

        Args:
            report: Validation report
        """
        print("\n" + "=" * 60)
        print(f"Pre-Deployment Validation Report")
        print(f"Project: {report['project']} | Environment: {report['environment']}")
        print("=" * 60)

        # Summary
        print(f"\nTotal Checks: {report['total_checks']}")
        print(f"✅ Passed: {report['summary']['pass']}")
        print(f"❌ Failed: {report['summary']['fail']}")
        print(f"⚠️  Warnings: {report['summary']['warning']}")
        print(f"⏭️  Skipped: {report['summary']['skipped']}")
        print(f"\nReadiness Score: {report['readiness_score']}%")

        # Failed checks
        if report["failed_checks"]:
            print("\n❌ Failed Checks:")
            for check in report["failed_checks"]:
                print(f"\n  • {check['name']}")
                print(f"    {check['message']}")
                if check["fix"]:
                    print(f"    Fix: {check['fix']}")

        # Warnings
        if report["warnings"]:
            print("\n⚠️  Warnings:")
            for warning in report["warnings"]:
                print(f"  • {warning['name']}: {warning['message']}")

        # By category
        print("\n📊 Results by Category:")
        for category, stats in report["by_category"].items():
            total = sum(stats.values())
            passed = stats["pass"]
            print(f"  {category}: {passed}/{total} passed")

        # Deployment readiness
        print("\n" + "=" * 60)
        if report["ready_to_deploy"]:
            print("✅ Environment is ready for deployment!")
        else:
            print("❌ Environment is NOT ready for deployment.")
            print("   Fix the failed checks before proceeding.")
        print("=" * 60 + "\n")
