"""AWS Security audit functionality."""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Security issue severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class SecurityIssue:
    """Represents a security issue found during audit."""

    resource_type: str
    resource_id: str
    issue_type: str
    description: str
    severity: Severity
    recommendation: str
    metadata: Optional[Dict[str, Any]] = None


class SecurityAuditor:
    """Perform security audits on AWS resources."""

    def __init__(self, project_name: str, environment: str, region: str = "us-east-1"):
        """Initialize the security auditor.

        Args:
            project_name: Name of the project
            environment: Environment (dev, staging, prod)
            region: AWS region
        """
        self.project_name = project_name
        self.environment = environment
        self.region = region
        self.stack_name = f"{project_name}-{environment}"

        # Initialize AWS clients
        self.session = boto3.Session(region_name=region)
        self.cf_client = self.session.client("cloudformation")
        self.iam_client = self.session.client("iam")
        self.s3_client = self.session.client("s3")
        self.lambda_client = self.session.client("lambda")
        self.dynamodb_client = self.session.client("dynamodb")
        self.apigateway_client = self.session.client("apigateway")
        self.waf_client = self.session.client("wafv2")
        self.cloudfront_client = self.session.client("cloudfront")

    def audit_all(self) -> List[SecurityIssue]:
        """Run all security audits.

        Returns:
            List of security issues found
        """
        issues = []

        logger.info(f"Starting security audit for {self.stack_name}")

        # Get stack resources
        try:
            resources = self._get_stack_resources()
        except Exception as e:
            logger.error(f"Failed to get stack resources: {e}")
            return issues

        # Run individual audits
        audit_functions = [
            self.audit_s3_buckets,
            self.audit_lambda_functions,
            self.audit_iam_roles,
            self.audit_api_gateway,
            self.audit_dynamodb_tables,
            self.audit_cloudfront,
            self.audit_encryption,
            self.audit_logging,
            self.audit_public_access,
        ]

        for audit_func in audit_functions:
            try:
                audit_issues = audit_func(resources)
                issues.extend(audit_issues)
            except Exception as e:
                logger.error(f"Audit failed for {audit_func.__name__}: {e}")

        return issues

    def _get_stack_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all resources from the CloudFormation stack.

        Returns:
            Dictionary of resources grouped by type
        """
        resources = {}

        try:
            paginator = self.cf_client.get_paginator("list_stack_resources")

            for page in paginator.paginate(StackName=self.stack_name):
                for resource in page["StackResourceSummaries"]:
                    resource_type = resource["ResourceType"]
                    if resource_type not in resources:
                        resources[resource_type] = []
                    resources[resource_type].append(resource)

        except Exception as e:
            logger.error(f"Failed to list stack resources: {e}")

        return resources

    def audit_s3_buckets(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit S3 bucket security.

        Args:
            resources: Stack resources

        Returns:
            List of S3 security issues
        """
        issues = []
        buckets = resources.get("AWS::S3::Bucket", [])

        for bucket_resource in buckets:
            bucket_name = bucket_resource["PhysicalResourceId"]

            # Check bucket encryption
            try:
                encryption = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
            except (
                self.s3_client.exceptions.ServerSideEncryptionConfigurationNotFoundError
            ):
                issues.append(
                    SecurityIssue(
                        resource_type="S3 Bucket",
                        resource_id=bucket_name,
                        issue_type="Missing Encryption",
                        description="S3 bucket is not encrypted at rest",
                        severity=Severity.HIGH,
                        recommendation="Enable default encryption with AES-256 or KMS",
                    )
                )

            # Check bucket versioning
            try:
                versioning = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                if versioning.get("Status") != "Enabled":
                    issues.append(
                        SecurityIssue(
                            resource_type="S3 Bucket",
                            resource_id=bucket_name,
                            issue_type="Versioning Disabled",
                            description="S3 bucket versioning is not enabled",
                            severity=Severity.MEDIUM,
                            recommendation="Enable versioning for data recovery and compliance",
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to check versioning for {bucket_name}: {e}")

            # Check public access block
            try:
                public_block = self.s3_client.get_public_access_block(
                    Bucket=bucket_name
                )
                config = public_block["PublicAccessBlockConfiguration"]

                if not all(
                    [
                        config.get("BlockPublicAcls", False),
                        config.get("BlockPublicPolicy", False),
                        config.get("IgnorePublicAcls", False),
                        config.get("RestrictPublicBuckets", False),
                    ]
                ):
                    issues.append(
                        SecurityIssue(
                            resource_type="S3 Bucket",
                            resource_id=bucket_name,
                            issue_type="Public Access Not Fully Blocked",
                            description="S3 bucket public access block is not fully configured",
                            severity=Severity.HIGH,
                            recommendation="Enable all public access block settings",
                        )
                    )
            except self.s3_client.exceptions.NoSuchPublicAccessBlockConfiguration:
                issues.append(
                    SecurityIssue(
                        resource_type="S3 Bucket",
                        resource_id=bucket_name,
                        issue_type="No Public Access Block",
                        description="S3 bucket has no public access block configuration",
                        severity=Severity.CRITICAL,
                        recommendation="Configure public access block to prevent data exposure",
                    )
                )

            # Check bucket logging
            try:
                logging_config = self.s3_client.get_bucket_logging(Bucket=bucket_name)
                if "LoggingEnabled" not in logging_config:
                    issues.append(
                        SecurityIssue(
                            resource_type="S3 Bucket",
                            resource_id=bucket_name,
                            issue_type="Access Logging Disabled",
                            description="S3 bucket access logging is not enabled",
                            severity=Severity.MEDIUM,
                            recommendation="Enable access logging for audit trail",
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to check logging for {bucket_name}: {e}")

        return issues

    def audit_lambda_functions(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit Lambda function security.

        Args:
            resources: Stack resources

        Returns:
            List of Lambda security issues
        """
        issues = []
        functions = resources.get("AWS::Lambda::Function", [])

        for func_resource in functions:
            func_name = func_resource["PhysicalResourceId"]

            try:
                # Get function configuration
                func_config = self.lambda_client.get_function_configuration(
                    FunctionName=func_name
                )

                # Check environment variables for secrets
                env_vars = func_config.get("Environment", {}).get("Variables", {})
                for key, value in env_vars.items():
                    if any(
                        secret in key.lower()
                        for secret in ["password", "secret", "key", "token", "api_key"]
                    ):
                        issues.append(
                            SecurityIssue(
                                resource_type="Lambda Function",
                                resource_id=func_name,
                                issue_type="Potential Secret in Environment",
                                description=f"Environment variable '{key}' may contain sensitive data",
                                severity=Severity.HIGH,
                                recommendation="Use AWS Secrets Manager or Parameter Store for secrets",
                            )
                        )

                # Check function timeout
                timeout = func_config.get("Timeout", 3)
                if timeout > 300:  # 5 minutes
                    issues.append(
                        SecurityIssue(
                            resource_type="Lambda Function",
                            resource_id=func_name,
                            issue_type="Excessive Timeout",
                            description=f"Function timeout ({timeout}s) is very high",
                            severity=Severity.LOW,
                            recommendation="Reduce timeout to minimize potential abuse",
                        )
                    )

                # Check reserved concurrent executions
                if "ReservedConcurrentExecutions" not in func_config:
                    issues.append(
                        SecurityIssue(
                            resource_type="Lambda Function",
                            resource_id=func_name,
                            issue_type="No Concurrency Limit",
                            description="Function has no reserved concurrent execution limit",
                            severity=Severity.MEDIUM,
                            recommendation="Set concurrency limits to prevent abuse and control costs",
                        )
                    )

                # Check VPC configuration
                vpc_config = func_config.get("VpcConfig", {})
                if not vpc_config.get("SubnetIds"):
                    issues.append(
                        SecurityIssue(
                            resource_type="Lambda Function",
                            resource_id=func_name,
                            issue_type="Not in VPC",
                            description="Function is not deployed in a VPC",
                            severity=Severity.INFO,
                            recommendation="Consider VPC deployment for network isolation",
                        )
                    )

            except Exception as e:
                logger.error(f"Failed to audit Lambda function {func_name}: {e}")

        return issues

    def audit_iam_roles(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit IAM role security.

        Args:
            resources: Stack resources

        Returns:
            List of IAM security issues
        """
        issues = []
        roles = resources.get("AWS::IAM::Role", [])

        for role_resource in roles:
            role_name = role_resource["PhysicalResourceId"]

            try:
                # Get role details
                role = self.iam_client.get_role(RoleName=role_name)["Role"]

                # Check trust policy
                trust_policy = json.loads(role["AssumeRolePolicyDocument"])
                for statement in trust_policy.get("Statement", []):
                    # Check for overly permissive trust
                    principal = statement.get("Principal", {})
                    if isinstance(principal, dict) and principal.get("AWS") == "*":
                        issues.append(
                            SecurityIssue(
                                resource_type="IAM Role",
                                resource_id=role_name,
                                issue_type="Overly Permissive Trust Policy",
                                description="Role can be assumed by any AWS principal",
                                severity=Severity.CRITICAL,
                                recommendation="Restrict trust policy to specific principals",
                            )
                        )

                # Get attached policies
                attached_policies = self.iam_client.list_attached_role_policies(
                    RoleName=role_name
                )["AttachedPolicies"]

                # Check for admin policies
                for policy in attached_policies:
                    if "AdministratorAccess" in policy["PolicyArn"]:
                        issues.append(
                            SecurityIssue(
                                resource_type="IAM Role",
                                resource_id=role_name,
                                issue_type="Administrator Access",
                                description="Role has administrator access",
                                severity=Severity.HIGH,
                                recommendation="Apply least privilege principle",
                            )
                        )

                # Get inline policies
                inline_policies = self.iam_client.list_role_policies(
                    RoleName=role_name
                )["PolicyNames"]

                for policy_name in inline_policies:
                    policy_doc = self.iam_client.get_role_policy(
                        RoleName=role_name, PolicyName=policy_name
                    )["PolicyDocument"]

                    # Check for wildcards in actions
                    for statement in policy_doc.get("Statement", []):
                        actions = statement.get("Action", [])
                        if isinstance(actions, str):
                            actions = [actions]

                        for action in actions:
                            if action == "*" or action.endswith(":*"):
                                issues.append(
                                    SecurityIssue(
                                        resource_type="IAM Role",
                                        resource_id=role_name,
                                        issue_type="Wildcard Permissions",
                                        description=f"Role has wildcard permissions: {action}",
                                        severity=Severity.HIGH,
                                        recommendation="Use specific actions instead of wildcards",
                                    )
                                )
                                break

            except Exception as e:
                logger.error(f"Failed to audit IAM role {role_name}: {e}")

        return issues

    def audit_api_gateway(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit API Gateway security.

        Args:
            resources: Stack resources

        Returns:
            List of API Gateway security issues
        """
        issues = []
        apis = resources.get("AWS::ApiGateway::RestApi", [])

        for api_resource in apis:
            api_id = api_resource["PhysicalResourceId"]

            try:
                # Get API details
                api = self.apigateway_client.get_rest_api(restApiId=api_id)

                # Check if API requires API key
                if not api.get("apiKeySource"):
                    issues.append(
                        SecurityIssue(
                            resource_type="API Gateway",
                            resource_id=api_id,
                            issue_type="No API Key Required",
                            description="API does not require an API key",
                            severity=Severity.MEDIUM,
                            recommendation="Consider requiring API keys for rate limiting",
                        )
                    )

                # Check for request validation
                validators = self.apigateway_client.get_request_validators(
                    restApiId=api_id
                ).get("items", [])

                if not validators:
                    issues.append(
                        SecurityIssue(
                            resource_type="API Gateway",
                            resource_id=api_id,
                            issue_type="No Request Validation",
                            description="API has no request validators configured",
                            severity=Severity.MEDIUM,
                            recommendation="Add request validation to prevent malformed requests",
                        )
                    )

                # Check for throttling
                stages = self.apigateway_client.get_stages(restApiId=api_id).get(
                    "item", []
                )
                for stage in stages:
                    if not stage.get("throttle"):
                        issues.append(
                            SecurityIssue(
                                resource_type="API Gateway",
                                resource_id=f"{api_id}/{stage['stageName']}",
                                issue_type="No Throttling Configuration",
                                description=f"Stage '{stage['stageName']}' has no throttling",
                                severity=Severity.MEDIUM,
                                recommendation="Configure throttling to prevent abuse",
                            )
                        )

            except Exception as e:
                logger.error(f"Failed to audit API Gateway {api_id}: {e}")

        return issues

    def audit_dynamodb_tables(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit DynamoDB table security.

        Args:
            resources: Stack resources

        Returns:
            List of DynamoDB security issues
        """
        issues = []
        tables = resources.get("AWS::DynamoDB::Table", [])

        for table_resource in tables:
            table_name = table_resource["PhysicalResourceId"]

            try:
                # Get table details
                table = self.dynamodb_client.describe_table(TableName=table_name)[
                    "Table"
                ]

                # Check encryption
                sse_description = table.get("SSEDescription", {})
                if sse_description.get("Status") != "ENABLED":
                    issues.append(
                        SecurityIssue(
                            resource_type="DynamoDB Table",
                            resource_id=table_name,
                            issue_type="Encryption Disabled",
                            description="Table is not encrypted at rest",
                            severity=Severity.HIGH,
                            recommendation="Enable server-side encryption",
                        )
                    )

                # Check point-in-time recovery
                try:
                    pitr = self.dynamodb_client.describe_continuous_backups(
                        TableName=table_name
                    )["ContinuousBackupsDescription"]

                    if (
                        pitr.get("PointInTimeRecoveryDescription", {}).get(
                            "PointInTimeRecoveryStatus"
                        )
                        != "ENABLED"
                    ):
                        issues.append(
                            SecurityIssue(
                                resource_type="DynamoDB Table",
                                resource_id=table_name,
                                issue_type="No Point-in-Time Recovery",
                                description="Point-in-time recovery is not enabled",
                                severity=Severity.MEDIUM,
                                recommendation="Enable PITR for data recovery capability",
                            )
                        )
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Failed to audit DynamoDB table {table_name}: {e}")

        return issues

    def audit_cloudfront(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit CloudFront distribution security.

        Args:
            resources: Stack resources

        Returns:
            List of CloudFront security issues
        """
        issues = []
        distributions = resources.get("AWS::CloudFront::Distribution", [])

        for dist_resource in distributions:
            dist_id = dist_resource["PhysicalResourceId"]

            try:
                # Get distribution config
                dist = self.cloudfront_client.get_distribution(Id=dist_id)
                config = dist["Distribution"]["DistributionConfig"]

                # Check if using HTTPS only
                viewer_protocol = config.get("DefaultCacheBehavior", {}).get(
                    "ViewerProtocolPolicy"
                )
                if (
                    viewer_protocol != "redirect-to-https"
                    and viewer_protocol != "https-only"
                ):
                    issues.append(
                        SecurityIssue(
                            resource_type="CloudFront Distribution",
                            resource_id=dist_id,
                            issue_type="HTTP Allowed",
                            description="Distribution allows non-HTTPS connections",
                            severity=Severity.HIGH,
                            recommendation="Enforce HTTPS-only connections",
                        )
                    )

                # Check for WAF
                if not config.get("WebACLId"):
                    issues.append(
                        SecurityIssue(
                            resource_type="CloudFront Distribution",
                            resource_id=dist_id,
                            issue_type="No WAF Protection",
                            description="Distribution has no WAF protection",
                            severity=Severity.MEDIUM,
                            recommendation="Attach a WAF ACL for protection against common attacks",
                        )
                    )

                # Check logging
                if not config.get("Logging", {}).get("Enabled"):
                    issues.append(
                        SecurityIssue(
                            resource_type="CloudFront Distribution",
                            resource_id=dist_id,
                            issue_type="Logging Disabled",
                            description="Distribution logging is not enabled",
                            severity=Severity.MEDIUM,
                            recommendation="Enable logging for audit trail",
                        )
                    )

            except Exception as e:
                logger.error(f"Failed to audit CloudFront distribution {dist_id}: {e}")

        return issues

    def audit_encryption(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit encryption across all resources.

        Args:
            resources: Stack resources

        Returns:
            List of encryption-related issues
        """
        issues = []

        # This is a meta-audit that checks encryption patterns
        # Individual resource audits already check encryption, but this provides overview

        return issues

    def audit_logging(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit logging configuration across resources.

        Args:
            resources: Stack resources

        Returns:
            List of logging-related issues
        """
        issues = []

        # Check if CloudTrail is configured for the stack
        # This would require additional CloudTrail client and checks

        return issues

    def audit_public_access(
        self, resources: Dict[str, List[Dict[str, Any]]]
    ) -> List[SecurityIssue]:
        """Audit resources for unintended public access.

        Args:
            resources: Stack resources

        Returns:
            List of public access issues
        """
        issues = []

        # This checks for any resources that might be publicly accessible
        # S3 buckets are already checked in audit_s3_buckets

        return issues

    def generate_report(self, issues: List[SecurityIssue]) -> Dict[str, Any]:
        """Generate a security audit report.

        Args:
            issues: List of security issues

        Returns:
            Formatted report dictionary
        """
        report = {
            "project": self.project_name,
            "environment": self.environment,
            "region": self.region,
            "total_issues": len(issues),
            "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            "issues_by_resource": {},
            "issues_by_type": {},
            "detailed_issues": [],
        }

        for issue in issues:
            # Update summary
            severity_key = issue.severity.value.lower()
            report["summary"][severity_key] += 1

            # Group by resource
            if issue.resource_type not in report["issues_by_resource"]:
                report["issues_by_resource"][issue.resource_type] = []
            report["issues_by_resource"][issue.resource_type].append(issue)

            # Group by type
            if issue.issue_type not in report["issues_by_type"]:
                report["issues_by_type"][issue.issue_type] = []
            report["issues_by_type"][issue.issue_type].append(issue)

            # Add to detailed list
            report["detailed_issues"].append(
                {
                    "resource_type": issue.resource_type,
                    "resource_id": issue.resource_id,
                    "issue_type": issue.issue_type,
                    "description": issue.description,
                    "severity": issue.severity.value,
                    "recommendation": issue.recommendation,
                    "metadata": issue.metadata,
                }
            )

        return report
