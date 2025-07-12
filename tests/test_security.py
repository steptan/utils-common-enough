"""
Comprehensive tests for security auditing and compliance modules.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from config import ProjectConfig
from security.audit import SecurityAuditor
from security.aws_security import AWSSecurityValidator
from security.compliance import ComplianceChecker


class TestSecurityAuditor:
    """Test security auditing functionality."""

    @pytest.fixture
    def basic_config(self):
        """Create a basic project configuration."""
        return ProjectConfig(
            name="test-project", display_name="Test Project", aws_region="us-east-1"
        )

    @pytest.fixture
    def mock_aws_clients(self):
        """Create mock AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_s3 = Mock()
            mock_lambda = Mock()
            mock_iam = Mock()
            mock_dynamodb = Mock()
            mock_apigateway = Mock()
            mock_cloudfront = Mock()
            mock_ec2 = Mock()

            mock_session.return_value.client.side_effect = lambda service: {
                "s3": mock_s3,
                "lambda": mock_lambda,
                "iam": mock_iam,
                "dynamodb": mock_dynamodb,
                "apigateway": mock_apigateway,
                "cloudfront": mock_cloudfront,
                "ec2": mock_ec2,
            }[service]

            yield {
                "s3": mock_s3,
                "lambda": mock_lambda,
                "iam": mock_iam,
                "dynamodb": mock_dynamodb,
                "apigateway": mock_apigateway,
                "cloudfront": mock_cloudfront,
                "ec2": mock_ec2,
            }

    @pytest.fixture
    def auditor(self, basic_config, mock_aws_clients):
        """Create a SecurityAuditor instance."""
        return SecurityAuditor(
            project_name="test-project", environment="prod", region="us-east-1"
        )

    def test_initialization(self, auditor):
        """Test SecurityAuditor initialization."""
        assert auditor.project_name == "test-project"
        assert auditor.environment == "prod"
        assert hasattr(auditor, "findings")
        assert auditor.findings == []

    def test_audit_s3_buckets_public_access(self, auditor, mock_aws_clients):
        """Test S3 bucket public access audit."""
        # Mock S3 responses
        mock_aws_clients["s3"].list_buckets.return_value = {
            "Buckets": [
                {"Name": "test-project-bucket-1"},
                {"Name": "test-project-bucket-2"},
            ]
        }

        # Bucket 1: Public access blocked
        mock_aws_clients["s3"].get_public_access_block.side_effect = [
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                }
            },
            # Bucket 2: Public access not blocked
            ClientError(
                {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}},
                "GetPublicAccessBlock",
            ),
        ]

        findings = auditor.audit_s3_buckets()

        # Should find issue with bucket 2
        assert len(findings) > 0
        assert any("public access" in f["description"].lower() for f in findings)
        assert any(f["severity"] == "HIGH" for f in findings)

    def test_audit_s3_buckets_encryption(self, auditor, mock_aws_clients):
        """Test S3 bucket encryption audit."""
        mock_aws_clients["s3"].list_buckets.return_value = {
            "Buckets": [{"Name": "test-project-bucket"}]
        }

        mock_aws_clients["s3"].get_bucket_encryption.side_effect = ClientError(
            {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
            "GetBucketEncryption",
        )

        findings = auditor.audit_s3_buckets()

        assert len(findings) > 0
        assert any("encryption" in f["description"].lower() for f in findings)

    def test_audit_lambda_functions_env_vars(self, auditor, mock_aws_clients):
        """Test Lambda function environment variables audit."""
        mock_aws_clients["lambda"].list_functions.return_value = {
            "Functions": [
                {
                    "FunctionName": "test-project-function",
                    "Environment": {
                        "Variables": {
                            "API_KEY": "secret-key-12345",
                            "DATABASE_URL": "postgres://user:pass@host:5432/db",
                            "NODE_ENV": "production",
                        }
                    },
                }
            ]
        }

        findings = auditor.audit_lambda_functions()

        # Should detect potential secrets in env vars
        assert len(findings) > 0
        assert any("API_KEY" in f["description"] for f in findings)
        assert any("DATABASE_URL" in f["description"] for f in findings)

    def test_audit_iam_roles_trust_policies(self, auditor, mock_aws_clients):
        """Test IAM role trust policy audit."""
        mock_aws_clients["iam"].list_roles.return_value = {
            "Roles": [
                {
                    "RoleName": "test-project-role",
                    "AssumeRolePolicyDocument": {
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": "*"},  # Overly permissive
                                "Action": "sts:AssumeRole",
                            }
                        ]
                    },
                }
            ]
        }

        findings = auditor.audit_iam_roles()

        assert len(findings) > 0
        assert any("trust policy" in f["description"].lower() for f in findings)
        assert any(f["severity"] == "HIGH" for f in findings)

    def test_audit_dynamodb_tables_encryption(self, auditor, mock_aws_clients):
        """Test DynamoDB table encryption audit."""
        mock_aws_clients["dynamodb"].list_tables.return_value = {
            "TableNames": ["test-project-table"]
        }

        mock_aws_clients["dynamodb"].describe_table.return_value = {
            "Table": {
                "TableName": "test-project-table",
                "SSEDescription": None,  # No encryption
            }
        }

        findings = auditor.audit_dynamodb_tables()

        assert len(findings) > 0
        assert any("encryption" in f["description"].lower() for f in findings)

    def test_audit_api_gateway_auth(self, auditor, mock_aws_clients):
        """Test API Gateway authentication audit."""
        mock_aws_clients["apigateway"].get_rest_apis.return_value = {
            "items": [{"id": "api123", "name": "test-project-api"}]
        }

        mock_aws_clients["apigateway"].get_resources.return_value = {
            "items": [{"id": "resource123", "path": "/public"}]
        }

        mock_aws_clients["apigateway"].get_method.return_value = {
            "authorizationType": "NONE",  # No auth
            "apiKeyRequired": False,
        }

        findings = auditor.audit_api_gateway()

        assert len(findings) > 0
        assert any("authentication" in f["description"].lower() for f in findings)

    def test_audit_cloudfront_https(self, auditor, mock_aws_clients):
        """Test CloudFront HTTPS enforcement audit."""
        mock_aws_clients["cloudfront"].list_distributions.return_value = {
            "DistributionList": {
                "Items": [
                    {
                        "Id": "dist123",
                        "Comment": "test-project-distribution",
                        "ViewerCertificate": {"CloudFrontDefaultCertificate": True},
                        "DefaultCacheBehavior": {
                            "ViewerProtocolPolicy": "allow-all"  # Allows HTTP
                        },
                    }
                ]
            }
        }

        findings = auditor.audit_cloudfront_distributions()

        assert len(findings) > 0
        assert any("HTTPS" in f["description"] for f in findings)

    def test_audit_vpc_security_groups(self, auditor, mock_aws_clients):
        """Test VPC security group audit."""
        mock_aws_clients["ec2"].describe_security_groups.return_value = {
            "SecurityGroups": [
                {
                    "GroupId": "sg-123",
                    "GroupName": "test-project-sg",
                    "IpPermissions": [
                        {
                            "IpProtocol": "-1",  # All protocols
                            "FromPort": 0,
                            "ToPort": 65535,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],  # Open to world
                        }
                    ],
                }
            ]
        }

        findings = auditor.audit_vpc_security()

        assert len(findings) > 0
        assert any("0.0.0.0/0" in f["description"] for f in findings)
        assert any(f["severity"] == "CRITICAL" for f in findings)

    def test_generate_audit_report(self, auditor):
        """Test audit report generation."""
        # Add some findings
        auditor.findings = [
            {
                "resource": "s3://test-bucket",
                "type": "S3_PUBLIC_ACCESS",
                "severity": "HIGH",
                "description": "Bucket allows public access",
            },
            {
                "resource": "lambda:test-function",
                "type": "LAMBDA_SECRETS",
                "severity": "MEDIUM",
                "description": "Potential secrets in environment variables",
            },
        ]

        report = auditor.generate_report()

        assert "security_score" in report
        assert "findings_by_severity" in report
        assert "findings_by_type" in report
        assert "recommendations" in report
        assert report["total_findings"] == 2


class TestComplianceChecker:
    """Test compliance checking functionality."""

    @pytest.fixture
    def checker(self):
        """Create a ComplianceChecker instance."""
        with patch("boto3.Session"):
            return ComplianceChecker(project_name="test-project", environment="prod")

    def test_initialization(self, checker):
        """Test ComplianceChecker initialization."""
        assert checker.project_name == "test-project"
        assert checker.environment == "prod"
        assert hasattr(checker, "checks")

    def test_check_operational_excellence(self, checker):
        """Test operational excellence pillar checks."""
        with patch.object(checker, "check_cloudwatch_alarms") as mock_alarms:
            with patch.object(checker, "check_logging_enabled") as mock_logging:
                with patch.object(checker, "check_tagging_compliance") as mock_tagging:
                    mock_alarms.return_value = True
                    mock_logging.return_value = True
                    mock_tagging.return_value = False

                    results = checker.check_operational_excellence()

                    assert results["pillar"] == "Operational Excellence"
                    assert results["score"] < 100  # Not perfect due to tagging
                    assert len(results["findings"]) > 0

    def test_check_security_pillar(self, checker):
        """Test security pillar checks."""
        with patch.object(checker, "check_encryption_at_rest") as mock_encryption:
            with patch.object(checker, "check_encryption_in_transit") as mock_transit:
                with patch.object(checker, "check_iam_best_practices") as mock_iam:
                    mock_encryption.return_value = True
                    mock_transit.return_value = True
                    mock_iam.return_value = True

                    results = checker.check_security()

                    assert results["pillar"] == "Security"
                    assert results["score"] == 100  # All checks pass
                    assert len(results["findings"]) == 0

    def test_check_reliability_pillar(self, checker):
        """Test reliability pillar checks."""
        results = checker.check_reliability()

        assert results["pillar"] == "Reliability"
        assert "findings" in results
        assert "recommendations" in results

    def test_check_performance_efficiency(self, checker):
        """Test performance efficiency pillar checks."""
        results = checker.check_performance_efficiency()

        assert results["pillar"] == "Performance Efficiency"
        assert "score" in results

    def test_check_cost_optimization(self, checker):
        """Test cost optimization pillar checks."""
        with patch.object(checker, "check_unused_resources") as mock_unused:
            with patch.object(checker, "check_right_sizing") as mock_sizing:
                mock_unused.return_value = []  # No unused resources
                mock_sizing.return_value = ["Lambda functions may be over-provisioned"]

                results = checker.check_cost_optimization()

                assert results["pillar"] == "Cost Optimization"
                assert len(results["findings"]) > 0

    def test_check_sustainability(self, checker):
        """Test sustainability pillar checks."""
        results = checker.check_sustainability()

        assert results["pillar"] == "Sustainability"
        assert "recommendations" in results

    def test_full_compliance_check(self, checker):
        """Test full Well-Architected compliance check."""
        report = checker.check_all_pillars()

        assert "overall_score" in report
        assert "pillars" in report
        assert len(report["pillars"]) == 6  # All 6 pillars
        assert "recommendations" in report
        assert "compliance_level" in report


class TestAWSSecurityScanner:
    """Test AWS security scanning functionality."""

    @pytest.fixture
    def scanner(self):
        """Create an AWSSecurityScanner instance."""
        with patch("boto3.Session"):
            return AWSSecurityScanner(region="us-east-1")

    def test_scan_exposed_credentials(self, scanner):
        """Test scanning for exposed credentials."""
        test_content = """
        export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
        export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
        const apiKey = 'sk-1234567890abcdef';
        """

        findings = scanner.scan_for_credentials(test_content)

        assert len(findings) > 0
        assert any("AWS_ACCESS_KEY" in f for f in findings)
        assert any("AWS_SECRET" in f for f in findings)

    def test_check_mfa_enabled(self, scanner):
        """Test MFA enforcement check."""
        with patch.object(scanner.iam, "get_account_summary") as mock_summary:
            mock_summary.return_value = {
                "SummaryMap": {"AccountMFAEnabled": 0}  # MFA not enabled
            }

            result = scanner.check_root_mfa()

            assert result is False

    def test_check_password_policy(self, scanner):
        """Test password policy compliance."""
        with patch.object(scanner.iam, "get_account_password_policy") as mock_policy:
            mock_policy.return_value = {
                "PasswordPolicy": {
                    "MinimumPasswordLength": 8,  # Too short
                    "RequireSymbols": False,
                    "RequireNumbers": True,
                    "RequireUppercaseCharacters": True,
                    "RequireLowercaseCharacters": True,
                    "MaxPasswordAge": 90,
                }
            }

            issues = scanner.check_password_policy()

            assert len(issues) > 0
            assert any("length" in issue.lower() for issue in issues)
            assert any("symbols" in issue.lower() for issue in issues)

    def test_scan_public_resources(self, scanner):
        """Test scanning for publicly accessible resources."""
        with patch.object(scanner, "scan_public_s3_buckets") as mock_s3:
            with patch.object(scanner, "scan_public_rds_instances") as mock_rds:
                with patch.object(scanner, "scan_public_ec2_instances") as mock_ec2:
                    mock_s3.return_value = ["bucket1", "bucket2"]
                    mock_rds.return_value = []
                    mock_ec2.return_value = ["i-12345"]

                    public_resources = scanner.scan_public_resources()

                    assert len(public_resources["s3_buckets"]) == 2
                    assert len(public_resources["rds_instances"]) == 0
                    assert len(public_resources["ec2_instances"]) == 1


class TestSecurityRecommendations:
    """Test security recommendation generation."""

    def test_generate_s3_recommendations(self):
        """Test S3 security recommendations."""
        from security.audit import generate_s3_recommendations

        findings = [
            {"type": "S3_PUBLIC_ACCESS", "resource": "bucket1"},
            {"type": "S3_NO_ENCRYPTION", "resource": "bucket2"},
        ]

        recommendations = generate_s3_recommendations(findings)

        assert len(recommendations) > 0
        assert any("public access" in r.lower() for r in recommendations)
        assert any("encryption" in r.lower() for r in recommendations)

    def test_generate_iam_recommendations(self):
        """Test IAM security recommendations."""
        from security.audit import generate_iam_recommendations

        findings = [
            {"type": "IAM_OVERLY_PERMISSIVE", "resource": "role1"},
            {"type": "IAM_NO_MFA", "resource": "user1"},
        ]

        recommendations = generate_iam_recommendations(findings)

        assert len(recommendations) > 0
        assert any("least privilege" in r.lower() for r in recommendations)
        assert any("MFA" in r for r in recommendations)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=security", "--cov-report=term-missing"])
