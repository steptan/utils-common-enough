"""
Static website pattern using S3 + CloudFront.

This L3 pattern creates a complete static website infrastructure with:
- S3 bucket for website hosting
- CloudFront distribution for global CDN
- Optional custom domain support
- Security best practices
"""

import json
from typing import Any, Dict, List, Optional

from troposphere import (
    Condition,
    Equals,
    Export,
    GetAtt,
    If,
    Join,
    Not,
    Output,
    Ref,
    Sub,
    Template,
    cloudfront,
    iam,
    route53,
    s3,
)


class StaticWebsitePattern:
    """
    L3 Pattern for a static website hosted on S3 with CloudFront.

    Creates a production-ready static website with S3 storage,
    CloudFront distribution, and optional custom domain configuration.
    """

    def __init__(
        self, template: Template, config: Dict[str, Any], environment: str = "dev"
    ):
        """
        Initialize static website pattern.

        Args:
            template: CloudFormation template to add resources to
            config: Pattern configuration
            environment: Deployment environment
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.resources: Dict[str, Any] = {}

        # Extract configuration sections
        self.s3_config = config.get("s3", {})
        self.cloudfront_config = config.get("cloudfront", {})
        self.domain_config = config.get("domain", {})
        self.pattern_config = config.get("pattern", {})

        # Create conditions
        self._create_conditions()

        # Build the pattern
        self._create_infrastructure()

    def _create_conditions(self) -> None:
        """Create CloudFormation conditions."""
        # Condition for custom domain
        self.has_custom_domain = self.template.add_condition(
            "HasCustomDomain",
            Not(Equals(self.domain_config.get("domain_name", ""), "")),
        )

        # Condition for SSL certificate
        self.has_certificate = self.template.add_condition(
            "HasCertificate",
            Not(Equals(self.domain_config.get("certificate_arn", ""), "")),
        )

    def _create_infrastructure(self) -> None:
        """Create all infrastructure components."""
        # 1. Create S3 bucket for website hosting
        self._create_s3_bucket()

        # 2. Create Origin Access Identity
        self._create_origin_access_identity()

        # 3. Create bucket policy
        self._create_bucket_policy()

        # 4. Create CloudFront distribution
        self._create_cloudfront_distribution()

        # 5. Create Route53 records if custom domain
        if self.domain_config.get("create_dns_records", False):
            self._create_route53_records()

        # 6. Create pattern-specific outputs
        self._create_pattern_outputs()

    def _create_s3_bucket(self) -> None:
        """Create S3 bucket for static website hosting."""
        bucket_name = self.s3_config.get("bucket_name")
        if not bucket_name:
            bucket_name = Sub(f"${{AWS::StackName}}-static-website-{self.environment}")

        # Create bucket
        self.website_bucket = self.template.add_resource(
            s3.Bucket(
                "WebsiteBucket",
                BucketName=bucket_name,
                WebsiteConfiguration=s3.WebsiteConfiguration(
                    IndexDocument=self.s3_config.get("index_document", "index.html"),
                    ErrorDocument=self.s3_config.get("error_document", "error.html"),
                ),
                PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
                    BlockPublicAcls=True,
                    BlockPublicPolicy=True,
                    IgnorePublicAcls=True,
                    RestrictPublicBuckets=True,
                ),
                BucketEncryption=s3.BucketEncryption(
                    ServerSideEncryptionConfiguration=[
                        s3.ServerSideEncryptionRule(
                            ServerSideEncryptionByDefault=s3.ServerSideEncryptionByDefault(
                                SSEAlgorithm="AES256"
                            )
                        )
                    ]
                ),
                VersioningConfiguration=s3.VersioningConfiguration(
                    Status=(
                        "Enabled"
                        if self.pattern_config.get("enable_versioning", True)
                        else "Suspended"
                    )
                ),
                LifecycleConfiguration=(
                    s3.LifecycleConfiguration(
                        Rules=[
                            s3.LifecycleRule(
                                Id="DeleteOldVersions",
                                Status="Enabled",
                                NoncurrentVersionExpirationInDays=30,
                            )
                        ]
                    )
                    if self.pattern_config.get("enable_versioning", True)
                    else Ref("AWS::NoValue")
                ),
                Tags=[
                    {
                        "Key": "Name",
                        "Value": Sub(f"${{AWS::StackName}}-website-bucket"),
                    },
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Type", "Value": "static-website"},
                ],
            )
        )

        self.resources["website_bucket"] = self.website_bucket

    def _create_origin_access_identity(self) -> None:
        """Create CloudFront Origin Access Identity."""
        self.origin_access_identity = self.template.add_resource(
            cloudfront.CloudFrontOriginAccessIdentity(
                "OriginAccessIdentity",
                CloudFrontOriginAccessIdentityConfig=cloudfront.CloudFrontOriginAccessIdentityConfig(
                    Comment=Sub(f"OAI for ${{AWS::StackName}}-{self.environment}")
                ),
            )
        )

        self.resources["origin_access_identity"] = self.origin_access_identity

    def _create_bucket_policy(self) -> None:
        """Create bucket policy for CloudFront access."""
        self.bucket_policy = self.template.add_resource(
            s3.BucketPolicy(
                "WebsiteBucketPolicy",
                Bucket=Ref(self.website_bucket),
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "AWS": Sub(
                                    "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ${OAI}",
                                    OAI=Ref(self.origin_access_identity),
                                )
                            },
                            "Action": "s3:GetObject",
                            "Resource": Sub(
                                "${BucketArn}/*",
                                BucketArn=GetAtt(self.website_bucket, "Arn"),
                            ),
                        }
                    ],
                },
            )
        )

    def _create_cloudfront_distribution(self) -> None:
        """Create CloudFront distribution."""
        # Cache behaviors
        default_cache_behavior = cloudfront.DefaultCacheBehavior(
            TargetOriginId="S3Origin",
            ViewerProtocolPolicy="redirect-to-https",
            AllowedMethods=["GET", "HEAD", "OPTIONS"],
            CachedMethods=["GET", "HEAD", "OPTIONS"],
            Compress=True,
            ForwardedValues=cloudfront.ForwardedValues(
                QueryString=False, Cookies=cloudfront.Cookies(Forward="none")
            ),
            MinTTL=self.cloudfront_config.get("min_ttl", 0),
            DefaultTTL=self.cloudfront_config.get("default_ttl", 86400),
            MaxTTL=self.cloudfront_config.get("max_ttl", 31536000),
        )

        # Custom error responses
        custom_error_responses: List[cloudfront.CustomErrorResponse] = []

        # Handle SPA routing
        if self.pattern_config.get("single_page_app", True):
            custom_error_responses.append(
                cloudfront.CustomErrorResponse(
                    ErrorCode=404,
                    ResponseCode=200,
                    ResponsePagePath="/index.html",
                    ErrorCachingMinTTL=300,
                )
            )

        custom_error_responses.append(
            cloudfront.CustomErrorResponse(
                ErrorCode=403,
                ResponseCode=404,
                ResponsePagePath="/error.html",
                ErrorCachingMinTTL=300,
            )
        )

        # Origin configuration
        origins = [
            cloudfront.Origin(
                Id="S3Origin",
                DomainName=GetAtt(self.website_bucket, "RegionalDomainName"),
                S3OriginConfig=cloudfront.S3OriginConfig(
                    OriginAccessIdentity=Sub(
                        "origin-access-identity/cloudfront/${OAI}",
                        OAI=Ref(self.origin_access_identity),
                    )
                ),
            )
        ]

        # Distribution configuration
        distribution_config = cloudfront.DistributionConfig(
            Comment=Sub(f"${{AWS::StackName}} static website distribution"),
            Origins=origins,
            DefaultCacheBehavior=default_cache_behavior,
            CustomErrorResponses=custom_error_responses,
            DefaultRootObject=self.s3_config.get("index_document", "index.html"),
            Enabled=True,
            HttpVersion="http2and3",
            IPV6Enabled=True,
            PriceClass=self.cloudfront_config.get(
                "price_class",
                "PriceClass_100" if self.environment != "prod" else "PriceClass_All",
            ),
        )

        # Add custom domain configuration if provided
        if self.domain_config.get("domain_name"):
            distribution_config.Aliases = If(
                "HasCustomDomain",
                [self.domain_config["domain_name"]],
                Ref("AWS::NoValue"),
            )

            if self.domain_config.get("certificate_arn"):
                distribution_config.ViewerCertificate = If(
                    "HasCertificate",
                    cloudfront.ViewerCertificate(
                        AcmCertificateArn=self.domain_config["certificate_arn"],
                        SslSupportMethod="sni-only",
                        MinimumProtocolVersion="TLSv1.2_2021",
                    ),
                    Ref("AWS::NoValue"),
                )

        # Create distribution
        self.distribution = self.template.add_resource(
            cloudfront.Distribution(
                "CloudFrontDistribution",
                DistributionConfig=distribution_config,
                Tags=[
                    {"Key": "Name", "Value": Sub(f"${{AWS::StackName}}-distribution")},
                    {"Key": "Environment", "Value": self.environment},
                ],
            )
        )

        self.resources["cloudfront_distribution"] = self.distribution

    def _create_route53_records(self) -> None:
        """Create Route53 DNS records for custom domain."""
        if not self.domain_config.get("hosted_zone_id"):
            return

        # A record for CloudFront
        self.dns_record = self.template.add_resource(
            route53.RecordSetType(
                "DomainDNSRecord",
                Condition="HasCustomDomain",
                HostedZoneId=self.domain_config["hosted_zone_id"],
                Name=self.domain_config["domain_name"],
                Type="A",
                AliasTarget=route53.AliasTarget(
                    DNSName=GetAtt(self.distribution, "DomainName"),
                    HostedZoneId="Z2FDTNDATAQYW2",  # CloudFront hosted zone ID
                    EvaluateTargetHealth=False,
                ),
            )
        )

        # AAAA record for IPv6
        self.dns_record_ipv6 = self.template.add_resource(
            route53.RecordSetType(
                "DomainDNSRecordIPv6",
                Condition="HasCustomDomain",
                HostedZoneId=self.domain_config["hosted_zone_id"],
                Name=self.domain_config["domain_name"],
                Type="AAAA",
                AliasTarget=route53.AliasTarget(
                    DNSName=GetAtt(self.distribution, "DomainName"),
                    HostedZoneId="Z2FDTNDATAQYW2",  # CloudFront hosted zone ID
                    EvaluateTargetHealth=False,
                ),
            )
        )

    def _create_pattern_outputs(self) -> None:
        """Create pattern-specific outputs."""
        # S3 bucket name
        self.template.add_output(
            Output(
                "WebsiteBucketName",
                Value=Ref(self.website_bucket),
                Description="S3 bucket name for website content",
                Export=Export(Sub(f"${{AWS::StackName}}-website-bucket")),
            )
        )

        # CloudFront distribution URL
        self.template.add_output(
            Output(
                "CloudFrontURL",
                Value=Sub(
                    "https://${Domain}", Domain=GetAtt(self.distribution, "DomainName")
                ),
                Description="CloudFront distribution URL",
                Export=Export(Sub(f"${{AWS::StackName}}-cloudfront-url")),
            )
        )

        # CloudFront distribution ID
        self.template.add_output(
            Output(
                "CloudFrontDistributionId",
                Value=Ref(self.distribution),
                Description="CloudFront distribution ID",
                Export=Export(Sub(f"${{AWS::StackName}}-cloudfront-id")),
            )
        )

        # Custom domain URL (if configured)
        if self.domain_config.get("domain_name"):
            self.template.add_output(
                Output(
                    "WebsiteURL",
                    Condition="HasCustomDomain",
                    Value=Sub(f"https://{self.domain_config['domain_name']}"),
                    Description="Website URL with custom domain",
                )
            )

        # Pattern summary
        pattern_summary = {
            "type": "static-website",
            "environment": self.environment,
            "single_page_app": self.pattern_config.get("single_page_app", True),
            "versioning_enabled": self.pattern_config.get("enable_versioning", True),
        }

        self.template.add_output(
            Output(
                "PatternSummary",
                Value=Sub(json.dumps(pattern_summary)),
                Description="Pattern configuration summary",
            )
        )

    def get_bucket_name(self) -> Ref:
        """Get the S3 bucket name."""
        return Ref(self.website_bucket)

    def get_distribution_id(self) -> Ref:
        """Get the CloudFront distribution ID."""
        return Ref(self.distribution)

    def get_distribution_domain(self) -> GetAtt:
        """Get the CloudFront distribution domain name."""
        return GetAtt(self.distribution, "DomainName")

    @staticmethod
    def get_default_config(environment: str = "dev") -> Dict[str, Any]:
        """
        Get default configuration for the pattern.

        Args:
            environment: Deployment environment

        Returns:
            Default configuration dictionary
        """
        return {
            "pattern": {
                "single_page_app": True,
                "enable_versioning": environment == "prod",
            },
            "s3": {"index_document": "index.html", "error_document": "error.html"},
            "cloudfront": {
                "price_class": (
                    "PriceClass_100" if environment != "prod" else "PriceClass_All"
                ),
                "min_ttl": 0,
                "default_ttl": 86400,
                "max_ttl": 31536000,
            },
            "domain": {
                "domain_name": "",
                "certificate_arn": "",
                "hosted_zone_id": "",
                "create_dns_records": False,
            },
        }

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """
        Validate pattern configuration.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: List[str] = []

        # Check required sections
        required_sections = ["pattern", "s3", "cloudfront"]
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required configuration section: {section}")

        # Validate CloudFront configuration
        if "cloudfront" in config:
            cf = config["cloudfront"]
            valid_price_classes = ["PriceClass_100", "PriceClass_200", "PriceClass_All"]
            if cf.get("price_class") and cf["price_class"] not in valid_price_classes:
                errors.append(
                    f"cloudfront.price_class must be one of: {valid_price_classes}"
                )

            # Validate TTL values
            for ttl_key in ["min_ttl", "default_ttl", "max_ttl"]:
                if ttl_key in cf:
                    ttl_value = cf[ttl_key]
                    if not isinstance(ttl_value, int) or ttl_value < 0:
                        errors.append(
                            f"cloudfront.{ttl_key} must be a non-negative integer"
                        )

        # Validate domain configuration
        if "domain" in config and config["domain"].get("create_dns_records", False):
            domain = config["domain"]
            if not domain.get("domain_name"):
                errors.append(
                    "domain.domain_name is required when create_dns_records is True"
                )
            if not domain.get("hosted_zone_id"):
                errors.append(
                    "domain.hosted_zone_id is required when create_dns_records is True"
                )

        return errors
