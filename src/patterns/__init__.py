"""
Infrastructure patterns (L3) for complete application deployments.

These patterns combine L2 constructs to create production-ready solutions.
"""

from .cloudfront_lambda_app import CloudFrontLambdaAppPattern
from .full_stack_app import FullStackAppPattern
from .serverless_api import ServerlessAPIPattern
from .static_website import StaticWebsitePattern

__all__ = [
    "ServerlessAPIPattern",
    "StaticWebsitePattern",
    "FullStackAppPattern",
    "CloudFrontLambdaAppPattern",
]
