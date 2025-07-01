"""
L2 Distribution Construct for People Cards Infrastructure
Provides CloudFront distribution with S3 origin and API Gateway integration
"""

from troposphere import (
    Template, Output, Ref, GetAtt, Tags, Sub, 
    Parameter, Export, ImportValue, Join
)
from troposphere import cloudfront, s3, iam
from typing import Dict, List, Any


class DistributionConstruct:
    """
    L2 Construct for content distribution infrastructure
    Creates CloudFront distribution with S3 and API Gateway origins
    """
    
    def __init__(self, template: Template, config: Dict[str, Any], environment: str,
                 api_domain_name=None, api_stage=None, s3_bucket=None):
        """
        Initialize distribution construct
        
        Args:
            template: CloudFormation template to add resources to
            config: Distribution configuration from YAML
            environment: Deployment environment (dev/staging/prod)
            api_domain_name: API Gateway domain name for API origin
            api_stage: API Gateway stage name
            s3_bucket: Existing S3 bucket resource (optional)
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.api_domain_name = api_domain_name
        self.api_stage = api_stage or environment
        self.resources = {}
        self.s3_bucket = s3_bucket
        
        # Create distribution resources
        if not self.s3_bucket:
            self._create_s3_bucket()
        self._create_origin_access_identity()
        self._create_cloudfront_distribution()
        self._create_outputs()
    
    def _create_s3_bucket(self):
        """Create S3 bucket for static assets"""
        self.s3_bucket = self.template.add_resource(
            s3.Bucket(
                "StaticAssetsBucket",
                BucketName=Sub(f"people-cards-static-{self.environment}-${{AWS::AccountId}}"),
                PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
                    BlockPublicAcls=True,
                    BlockPublicPolicy=True,
                    IgnorePublicAcls=True,
                    RestrictPublicBuckets=True
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
                    Status="Enabled" if self.environment == "prod" else "Suspended"
                ),
                LifecycleConfiguration=s3.LifecycleConfiguration(
                    Rules=[
                        s3.LifecycleRule(
                            Id="DeleteIncompleteMultipartUploads",
                            Status="Enabled",
                            AbortIncompleteMultipartUpload=s3.AbortIncompleteMultipartUpload(
                                DaysAfterInitiation=7
                            )
                        )
                    ]
                ),
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-static-assets"),
                    Environment=self.environment
                )
            )
        )
        
        self.resources["s3_bucket"] = self.s3_bucket
    
    def _create_origin_access_identity(self):
        """Create CloudFront Origin Access Identity for S3 access"""
        self.oai = self.template.add_resource(
            cloudfront.CloudFrontOriginAccessIdentity(
                "OriginAccessIdentity",
                CloudFrontOriginAccessIdentityConfig=cloudfront.CloudFrontOriginAccessIdentityConfig(
                    Comment=Sub(f"OAI for ${{AWS::StackName}} static assets")
                )
            )
        )
        
        # Bucket policy to allow CloudFront access
        bucket_policy = self.template.add_resource(
            s3.BucketPolicy(
                "StaticAssetsBucketPolicy",
                Bucket=Ref(self.s3_bucket),
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AllowCloudFrontAccess",
                            "Effect": "Allow",
                            "Principal": {
                                "AWS": Join("", [
                                    "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ",
                                    Ref(self.oai)
                                ])
                            },
                            "Action": "s3:GetObject",
                            "Resource": Join("", [GetAtt(self.s3_bucket, "Arn"), "/*"])
                        }
                    ]
                }
            )
        )
        
        self.resources["oai"] = self.oai
        self.resources["bucket_policy"] = bucket_policy
    
    def _create_cloudfront_distribution(self):
        """Create CloudFront distribution with multiple origins"""
        cf_config = self.config["cloudfront"]
        
        # Origins
        origins = []
        
        # S3 origin for static assets
        s3_origin = cloudfront.Origin(
            Id="S3Origin",
            DomainName=GetAtt(self.s3_bucket, "RegionalDomainName"),
            S3OriginConfig=cloudfront.S3OriginConfig(
                OriginAccessIdentity=Sub(f"origin-access-identity/cloudfront/{Ref(self.oai)}")
            )
        )
        origins.append(s3_origin)
        
        # API Gateway origin if provided
        if self.api_domain_name:
            api_origin = cloudfront.Origin(
                Id="APIOrigin",
                DomainName=self.api_domain_name,
                OriginPath=f"/{self.api_stage}",
                CustomOriginConfig=cloudfront.CustomOriginConfig(
                    HTTPPort=443,
                    OriginProtocolPolicy="https-only",
                    OriginSSLProtocols=["TLSv1.2"]
                )
            )
            origins.append(api_origin)
        
        # Cache behaviors
        cache_behaviors = []
        
        # API cache behavior (if API origin exists)
        if self.api_domain_name:
            api_cache_behavior = cloudfront.CacheBehavior(
                PathPattern="/api/*",
                TargetOriginId="APIOrigin",
                ViewerProtocolPolicy="redirect-to-https",
                AllowedMethods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                CachedMethods=["GET", "HEAD", "OPTIONS"],
                Compress=True,
                CachePolicyId="4135ea2d-6df8-44a3-9df3-4b5a84be39ad",  # CachingDisabled
                OriginRequestPolicyId="88a5eaf4-2fd4-4709-b370-b4c650ea3fcf",  # CORS-S3Origin
                ResponseHeadersPolicyId="67f7725c-6f97-4210-82d7-5512b31e9d03"  # SecurityHeadersPolicy
            )
            cache_behaviors.append(api_cache_behavior)
        
        # Default cache behavior for static assets
        default_cache_behavior = cloudfront.DefaultCacheBehavior(
            TargetOriginId="S3Origin",
            ViewerProtocolPolicy=cf_config.get("default_cache_behavior", {}).get("viewer_protocol_policy", "redirect-to-https"),
            AllowedMethods=cf_config.get("default_cache_behavior", {}).get("allowed_methods", ["GET", "HEAD"]),
            CachedMethods=["GET", "HEAD"],
            Compress=cf_config.get("default_cache_behavior", {}).get("compress", True),
            CachePolicyId=cf_config.get("default_cache_behavior", {}).get("cache_policy_id", "658327ea-f89d-4fab-a63d-7e88639e58f6")  # CachingOptimized
        )
        
        # Custom error pages
        custom_error_responses = [
            cloudfront.CustomErrorResponse(
                ErrorCode=403,
                ResponseCode=200,
                ResponsePagePath="/index.html",
                ErrorCachingMinTTL=300
            ),
            cloudfront.CustomErrorResponse(
                ErrorCode=404,
                ResponseCode=200,
                ResponsePagePath="/index.html",
                ErrorCachingMinTTL=300
            )
        ]
        
        # Distribution configuration
        distribution_config = cloudfront.DistributionConfig(
            Enabled=True,
            Comment=Sub(f"People Cards distribution - {self.environment}"),
            DefaultRootObject="index.html",
            Origins=origins,
            DefaultCacheBehavior=default_cache_behavior,
            CacheBehaviors=cache_behaviors if cache_behaviors else [],
            CustomErrorResponses=custom_error_responses,
            PriceClass=cf_config.get("price_class", "PriceClass_100"),
            ViewerCertificate=cloudfront.ViewerCertificate(
                CloudFrontDefaultCertificate=True
            ),
            HttpVersion="http2"
        )
        
        # Add logging configuration if enabled
        if cf_config.get("enable_logging", False):
            # Create logging bucket
            logging_bucket = self.template.add_resource(
                s3.Bucket(
                    "CloudFrontLogsBucket",
                    BucketName=Sub(f"people-cards-cf-logs-{self.environment}-${{AWS::AccountId}}"),
                    PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
                        BlockPublicAcls=True,
                        BlockPublicPolicy=True,
                        IgnorePublicAcls=True,
                        RestrictPublicBuckets=True
                    ),
                    LifecycleConfiguration=s3.LifecycleConfiguration(
                        Rules=[
                            s3.LifecycleRule(
                                Id="DeleteOldLogs",
                                Status="Enabled",
                                ExpirationInDays=90,
                                Transitions=[
                                    s3.LifecycleRuleTransition(
                                        StorageClass="STANDARD_IA",
                                        TransitionInDays=30
                                    ),
                                    s3.LifecycleRuleTransition(
                                        StorageClass="GLACIER",
                                        TransitionInDays=60
                                    )
                                ]
                            )
                        ]
                    ),
                    Tags=Tags(
                        Name=Sub(f"${{AWS::StackName}}-cf-logs"),
                        Environment=self.environment
                    )
                )
            )
            
            distribution_config.Logging = cloudfront.Logging(
                Bucket=GetAtt(logging_bucket, "DomainName"),
                IncludeCookies=False,
                Prefix=f"cloudfront-logs/{self.environment}/"
            )
            
            self.resources["logging_bucket"] = logging_bucket
        
        # Add WAF Web ACL if specified
        if cf_config.get("web_acl_id"):
            distribution_config.WebACLId = cf_config["web_acl_id"]
        
        # Create the distribution
        self.distribution = self.template.add_resource(
            cloudfront.Distribution(
                "CloudFrontDistribution",
                DistributionConfig=distribution_config,
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-distribution"),
                    Environment=self.environment
                )
            )
        )
        
        self.resources["distribution"] = self.distribution
    
    def _create_outputs(self):
        """Create CloudFormation outputs for cross-stack references"""
        outputs = {
            "CloudFrontDistributionId": {
                "value": Ref(self.distribution),
                "description": "CloudFront distribution ID"
            },
            "CloudFrontDistributionDomainName": {
                "value": GetAtt(self.distribution, "DomainName"),
                "description": "CloudFront distribution domain name"
            },
            "StaticAssetsBucketName": {
                "value": Ref(self.s3_bucket),
                "description": "S3 bucket name for static assets"
            },
            "StaticAssetsBucketArn": {
                "value": GetAtt(self.s3_bucket, "Arn"),
                "description": "S3 bucket ARN for static assets"
            },
            "StaticAssetsBucketDomainName": {
                "value": GetAtt(self.s3_bucket, "RegionalDomainName"),
                "description": "S3 bucket regional domain name"
            },
            "DistributionURL": {
                "value": Sub(f"https://{GetAtt(self.distribution, 'DomainName')}"),
                "description": "CloudFront distribution URL"
            }
        }
        
        for name, output_config in outputs.items():
            self.template.add_output(
                Output(
                    name,
                    Value=output_config["value"],
                    Description=output_config["description"],
                    Export=Export(Sub(f"${{AWS::StackName}}-{name}"))
                )
            )
    
    def get_distribution_id(self):
        """Get reference to CloudFront distribution ID"""
        return Ref(self.distribution)
    
    def get_distribution_domain_name(self):
        """Get reference to CloudFront distribution domain name"""
        return GetAtt(self.distribution, "DomainName")
    
    def get_s3_bucket_name(self):
        """Get reference to S3 bucket name"""
        return Ref(self.s3_bucket)
    
    def get_distribution_url(self):
        """Get CloudFront distribution URL"""
        return Sub(f"https://{GetAtt(self.distribution, 'DomainName')}")