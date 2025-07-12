"""
Comprehensive tests for distribution constructs module.
Tests CloudFront distribution, S3 origins, and API Gateway integration.
"""

import pytest
from moto import mock_aws
from troposphere import Template, GetAtt, Ref, Sub, Join
from unittest.mock import Mock, patch, MagicMock

from typing import Any, Dict, List, Optional, Union

from src.constructs.distribution import DistributionConstruct


class TestDistributionConstruct:
    """Test DistributionConstruct class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template = Template()
        self.environment = "test"
        self.config = {
            "cloudfront": {
                "default_cache_behavior": {
                    "viewer_protocol_policy": "redirect-to-https",
                    "allowed_methods": ["GET", "HEAD"],
                    "compress": True,
                    "cache_policy_id": "658327ea-f89d-4fab-a63d-7e88639e58f6"
                },
                "price_class": "PriceClass_100",
                "enable_logging": True,
                "web_acl_id": None
            }
        }
        self.api_domain_name = Sub("${RestAPI}.execute-api.${AWS::Region}.amazonaws.com")
        self.api_stage = "api"

    @mock_aws
    def test_init_creates_all_resources(self) -> None:
        """Test that initialization creates all required resources."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment,
            api_domain_name=self.api_domain_name,
            api_stage=self.api_stage
        )

        # Check that resources were created
        assert construct.s3_bucket is not None
        assert construct.oai is not None
        assert construct.distribution is not None
        assert "s3_bucket" in construct.resources
        assert "oai" in construct.resources
        assert "bucket_policy" in construct.resources
        assert "distribution" in construct.resources

    def test_s3_bucket_creation(self) -> None:
        """Test S3 bucket creation for static assets."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        bucket = construct.s3_bucket
        assert hasattr(bucket, 'BucketName')
        assert isinstance(bucket.BucketName, Sub)
        assert hasattr(bucket, 'PublicAccessBlockConfiguration')
        assert bucket.PublicAccessBlockConfiguration.BlockPublicAcls is True
        assert hasattr(bucket, 'BucketEncryption')
        assert hasattr(bucket, 'Tags')

    def test_s3_bucket_versioning_prod(self) -> None:
        """Test S3 bucket versioning enabled in production."""
        self.environment = "prod"
        
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        bucket = construct.s3_bucket
        assert bucket.VersioningConfiguration.Status == "Enabled"

    def test_s3_bucket_versioning_non_prod(self) -> None:
        """Test S3 bucket versioning suspended in non-production."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        bucket = construct.s3_bucket
        assert bucket.VersioningConfiguration.Status == "Suspended"

    def test_existing_s3_bucket(self) -> None:
        """Test using existing S3 bucket."""
        existing_bucket = Mock()
        
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment,
            s3_bucket=existing_bucket
        )

        # Should use provided bucket
        assert construct.s3_bucket == existing_bucket

    def test_origin_access_identity_creation(self) -> None:
        """Test CloudFront Origin Access Identity creation."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        oai = construct.oai
        assert hasattr(oai, 'CloudFrontOriginAccessIdentityConfig')
        assert hasattr(oai.CloudFrontOriginAccessIdentityConfig, 'Comment')

    def test_bucket_policy_creation(self) -> None:
        """Test S3 bucket policy for CloudFront access."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check bucket policy exists
        assert "bucket_policy" in construct.resources
        
        # Find bucket policy in template
        resources = self.template.resources
        bucket_policies = [r for r in resources.values() 
                          if hasattr(r, 'PolicyDocument')]
        assert len(bucket_policies) >= 1
        
        # Check policy allows CloudFront access
        policy = bucket_policies[0]
        assert "AllowCloudFrontAccess" in str(policy.PolicyDocument)

    def test_cloudfront_distribution_basic(self) -> None:
        """Test basic CloudFront distribution creation."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        dist = construct.distribution
        assert hasattr(dist, 'DistributionConfig')
        config = dist.DistributionConfig
        
        assert config.Enabled is True
        assert isinstance(config.Comment, Sub)
        assert config.DefaultRootObject == "index.html"
        assert config.HttpVersion == "http2"
        assert config.PriceClass == "PriceClass_100"

    def test_cloudfront_origins(self) -> None:
        """Test CloudFront origins configuration."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment,
            api_domain_name=self.api_domain_name
        )

        config = construct.distribution.DistributionConfig
        assert len(config.Origins) == 2
        
        # Check S3 origin
        s3_origin = config.Origins[0]
        assert s3_origin.Id == "S3Origin"
        assert hasattr(s3_origin, 'S3OriginConfig')
        assert hasattr(s3_origin.S3OriginConfig, 'OriginAccessIdentity')
        
        # Check API origin
        api_origin = config.Origins[1]
        assert api_origin.Id == "APIOrigin"
        assert api_origin.DomainName == self.api_domain_name
        assert api_origin.OriginPath == "/api"
        assert api_origin.CustomOriginConfig.OriginProtocolPolicy == "https-only"

    def test_cloudfront_without_api_origin(self) -> None:
        """Test CloudFront distribution without API origin."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        config = construct.distribution.DistributionConfig
        assert len(config.Origins) == 1
        assert config.Origins[0].Id == "S3Origin"

    def test_cache_behaviors(self) -> None:
        """Test CloudFront cache behaviors."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment,
            api_domain_name=self.api_domain_name
        )

        config = construct.distribution.DistributionConfig
        
        # Check API cache behavior
        assert len(config.CacheBehaviors) == 1
        api_behavior = config.CacheBehaviors[0]
        assert api_behavior.PathPattern == "/api/*"
        assert api_behavior.TargetOriginId == "APIOrigin"
        assert "DELETE" in api_behavior.AllowedMethods
        assert api_behavior.Compress is True
        
        # Check default cache behavior
        default_behavior = config.DefaultCacheBehavior
        assert default_behavior.TargetOriginId == "S3Origin"
        assert default_behavior.ViewerProtocolPolicy == "redirect-to-https"
        assert default_behavior.Compress is True

    def test_custom_error_responses(self) -> None:
        """Test CloudFront custom error responses."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        config = construct.distribution.DistributionConfig
        assert len(config.CustomErrorResponses) == 2
        
        # Check 403 error response
        error_403 = config.CustomErrorResponses[0]
        assert error_403.ErrorCode == 403
        assert error_403.ResponseCode == 200
        assert error_403.ResponsePagePath == "/index.html"
        
        # Check 404 error response
        error_404 = config.CustomErrorResponses[1]
        assert error_404.ErrorCode == 404
        assert error_404.ResponseCode == 200
        assert error_404.ResponsePagePath == "/index.html"

    def test_cloudfront_logging_enabled(self) -> None:
        """Test CloudFront logging configuration when enabled."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check logging bucket was created
        assert "logging_bucket" in construct.resources
        
        # Check distribution logging config
        config = construct.distribution.DistributionConfig
        assert hasattr(config, 'Logging')
        assert config.Logging.IncludeCookies is False
        assert f"cloudfront-logs/{self.environment}/" in config.Logging.Prefix

    def test_cloudfront_logging_disabled(self) -> None:
        """Test CloudFront without logging."""
        self.config["cloudfront"]["enable_logging"] = False
        
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        # No logging bucket
        assert "logging_bucket" not in construct.resources
        
        # No logging config
        config = construct.distribution.DistributionConfig
        assert not hasattr(config, 'Logging')

    def test_cloudfront_web_acl(self) -> None:
        """Test CloudFront with WAF Web ACL."""
        self.config["cloudfront"]["web_acl_id"] = "arn:aws:wafv2:us-east-1:123456789012:global/webacl/test/abc123"
        
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        config = construct.distribution.DistributionConfig
        assert config.WebACLId == self.config["cloudfront"]["web_acl_id"]

    def test_outputs_creation(self) -> None:
        """Test CloudFormation outputs creation."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        outputs = self.template.outputs
        
        # Check expected outputs
        assert "CloudFrontDistributionId" in outputs
        assert "CloudFrontDistributionDomainName" in outputs
        assert "StaticAssetsBucketName" in outputs
        assert "StaticAssetsBucketArn" in outputs
        assert "StaticAssetsBucketDomainName" in outputs
        assert "DistributionURL" in outputs
        
        # Check output properties
        for output in outputs.values():
            assert hasattr(output, 'Export')
            assert hasattr(output, 'Description')

    def test_get_distribution_id(self) -> None:
        """Test get_distribution_id method."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        dist_id = construct.get_distribution_id()
        assert isinstance(dist_id, Ref)

    def test_get_distribution_domain_name(self) -> None:
        """Test get_distribution_domain_name method."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        domain_name = construct.get_distribution_domain_name()
        assert isinstance(domain_name, GetAtt)

    def test_get_s3_bucket_name(self) -> None:
        """Test get_s3_bucket_name method."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        bucket_name = construct.get_s3_bucket_name()
        assert isinstance(bucket_name, Ref)

    def test_get_distribution_url(self) -> None:
        """Test get_distribution_url method."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        url = construct.get_distribution_url()
        assert isinstance(url, Join)
        assert "https://" in str(url)

    def test_logging_bucket_lifecycle(self) -> None:
        """Test logging bucket lifecycle configuration."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        logging_bucket = construct.resources["logging_bucket"]
        assert hasattr(logging_bucket, 'LifecycleConfiguration')
        
        rules = logging_bucket.LifecycleConfiguration.Rules
        assert len(rules) == 1
        assert rules[0].Id == "DeleteOldLogs"
        assert rules[0].ExpirationInDays == 90
        assert len(rules[0].Transitions) == 2

    def test_api_origin_custom_stage(self) -> None:
        """Test API origin with custom stage name."""
        custom_stage = "v1"
        
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment,
            api_domain_name=self.api_domain_name,
            api_stage=custom_stage
        )

        api_origin = construct.distribution.DistributionConfig.Origins[1]
        assert api_origin.OriginPath == f"/{custom_stage}"

    def test_default_cache_policy(self) -> None:
        """Test default cache policy configuration."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        default_behavior = construct.distribution.DistributionConfig.DefaultCacheBehavior
        assert default_behavior.CachePolicyId == "658327ea-f89d-4fab-a63d-7e88639e58f6"

    def test_tags_on_resources(self) -> None:
        """Test that all resources have appropriate tags."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check S3 bucket tags
        assert hasattr(construct.s3_bucket, 'Tags')
        
        # Check distribution tags
        assert hasattr(construct.distribution, 'Tags')
        
        # Check logging bucket tags if exists
        if "logging_bucket" in construct.resources:
            assert hasattr(construct.resources["logging_bucket"], 'Tags')

    def test_viewer_certificate_default(self) -> None:
        """Test default viewer certificate configuration."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        config = construct.distribution.DistributionConfig
        assert hasattr(config, 'ViewerCertificate')
        assert config.ViewerCertificate.CloudFrontDefaultCertificate is True

    def test_api_origin_ssl_protocols(self) -> None:
        """Test API origin SSL protocols."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment,
            api_domain_name=self.api_domain_name
        )

        api_origin = construct.distribution.DistributionConfig.Origins[1]
        assert api_origin.CustomOriginConfig.HTTPPort == 443
        assert api_origin.CustomOriginConfig.OriginSSLProtocols == ["TLSv1.2"]

    def test_s3_bucket_lifecycle(self) -> None:
        """Test S3 bucket lifecycle configuration."""
        construct = DistributionConstruct(
            self.template,
            self.config,
            self.environment
        )

        bucket = construct.s3_bucket
        assert hasattr(bucket, 'LifecycleConfiguration')
        
        rules = bucket.LifecycleConfiguration.Rules
        assert len(rules) == 1
        assert rules[0].Id == "DeleteIncompleteMultipartUploads"
        assert rules[0].Status == "Enabled"
        assert hasattr(rules[0], 'AbortIncompleteMultipartUpload')
        assert rules[0].AbortIncompleteMultipartUpload.DaysAfterInitiation == 7