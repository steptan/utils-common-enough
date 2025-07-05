"""
Full stack application pattern combining serverless API and static website.

This L3 pattern creates a complete full-stack application with:
- Frontend: S3 + CloudFront for static website hosting
- Backend: Lambda + API Gateway + DynamoDB for serverless API
- Proper CORS configuration
- Integrated security and monitoring
"""

import json
from troposphere import Template, Output, Ref, GetAtt, Sub, Export
from typing import Dict, List, Any, Optional
from .serverless_api import ServerlessAPIPattern
from .static_website import StaticWebsitePattern


class FullStackAppPattern:
    """
    L3 Pattern for a full-stack application.

    Combines the serverless API and static website patterns to create
    a complete application infrastructure with frontend and backend.
    """

    def __init__(
        self, template: Template, config: Dict[str, Any], environment: str = "dev"
    ):
        """
        Initialize full stack application pattern.

        Args:
            template: CloudFormation template to add resources to
            config: Pattern configuration
            environment: Deployment environment
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.resources = {}

        # Extract configuration sections
        self.api_config = config.get("api", {})
        self.website_config = config.get("website", {})
        self.pattern_config = config.get("pattern", {})

        # Build the pattern
        self._create_infrastructure()

    def _create_infrastructure(self):
        """Create all infrastructure components."""
        # 1. Create backend API infrastructure
        self._create_api_infrastructure()

        # 2. Create frontend website infrastructure
        self._create_website_infrastructure()

        # 3. Configure API Gateway CORS for frontend
        self._configure_cors()

        # 4. Create pattern-specific outputs
        self._create_pattern_outputs()

    def _create_api_infrastructure(self):
        """Create serverless API infrastructure."""
        # Ensure API configuration has proper CORS settings
        if "compute" not in self.api_config:
            self.api_config["compute"] = {}

        if "lambda" not in self.api_config["compute"]:
            self.api_config["compute"]["lambda"] = {}

        if "environment_variables" not in self.api_config["compute"]["lambda"]:
            self.api_config["compute"]["lambda"]["environment_variables"] = {}

        # Add CORS configuration to Lambda environment
        allowed_origins = self._get_allowed_origins()
        self.api_config["compute"]["lambda"]["environment_variables"].update(
            {
                "CORS_ALLOWED_ORIGINS": ",".join(allowed_origins),
                "CORS_ALLOWED_METHODS": "GET,POST,PUT,DELETE,OPTIONS",
                "CORS_ALLOWED_HEADERS": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            }
        )

        # Create serverless API
        self.api = ServerlessAPIPattern(
            template=self.template, config=self.api_config, environment=self.environment
        )

        self.resources["api"] = self.api

    def _create_website_infrastructure(self):
        """Create static website infrastructure."""
        # Configure website with API endpoint
        if "pattern" not in self.website_config:
            self.website_config["pattern"] = {}

        # Ensure it's configured as a single-page app if specified
        self.website_config["pattern"]["single_page_app"] = self.pattern_config.get(
            "single_page_app", True
        )

        # Create static website
        self.website = StaticWebsitePattern(
            template=self.template,
            config=self.website_config,
            environment=self.environment,
        )

        self.resources["website"] = self.website

    def _get_allowed_origins(self) -> List[str]:
        """Get list of allowed origins for CORS."""
        allowed_origins = []

        # Add CloudFront distribution domain
        # This will be resolved at runtime
        allowed_origins.append(
            Sub(
                "https://${Domain}",
                Domain=GetAtt(self.website.distribution, "DomainName"),
            )
        )

        # Add custom domain if configured
        domain_config = self.website_config.get("domain", {})
        if domain_config.get("domain_name"):
            allowed_origins.append(f"https://{domain_config['domain_name']}")

        # Add localhost for development
        if self.environment == "dev":
            allowed_origins.extend(
                [
                    "http://localhost:3000",
                    "http://localhost:3001",
                    "http://127.0.0.1:3000",
                ]
            )

        # Add any additional origins from config
        additional_origins = self.pattern_config.get("additional_cors_origins", [])
        allowed_origins.extend(additional_origins)

        return allowed_origins

    def _configure_cors(self):
        """Configure CORS settings for API Gateway."""
        # CORS is handled by Lambda function with appropriate headers
        # This is more flexible than API Gateway CORS configuration
        pass

    def _create_pattern_outputs(self):
        """Create pattern-specific outputs."""
        # Frontend URL
        self.template.add_output(
            Output(
                "FrontendURL",
                Value=Sub(
                    "https://${Domain}",
                    Domain=GetAtt(self.website.distribution, "DomainName"),
                ),
                Description="Frontend application URL",
                Export=Export(Sub(f"${{AWS::StackName}}-frontend-url")),
            )
        )

        # API endpoint
        self.template.add_output(
            Output(
                "BackendAPIEndpoint",
                Value=self.api.get_api_endpoint(),
                Description="Backend API endpoint URL",
                Export=Export(Sub(f"${{AWS::StackName}}-backend-api")),
            )
        )

        # Deployment instructions
        deployment_instructions = {
            "frontend": {
                "bucket": Ref(self.website.website_bucket),
                "distribution_id": Ref(self.website.distribution),
                "deploy_command": f"aws s3 sync ./dist s3://$(BUCKET_NAME) --delete && aws cloudfront create-invalidation --distribution-id $(DISTRIBUTION_ID) --paths '/*'",
            },
            "backend": {
                "function_name": Sub(f"${{AWS::StackName}}-api-{self.environment}"),
                "api_id": self.api.compute.get_api_gateway_id(),
            },
        }

        self.template.add_output(
            Output(
                "DeploymentInstructions",
                Value=Sub(json.dumps(deployment_instructions, indent=2)),
                Description="Deployment instructions for frontend and backend",
            )
        )

        # Pattern summary
        pattern_summary = {
            "type": "full-stack-app",
            "environment": self.environment,
            "single_page_app": self.pattern_config.get("single_page_app", True),
            "api_in_vpc": self.api_config.get("pattern", {}).get("lambda_in_vpc", True),
            "cost_optimized": self.api_config.get("pattern", {}).get(
                "cost_optimized", True
            )
            and self.environment != "prod",
        }

        self.template.add_output(
            Output(
                "PatternSummary",
                Value=Sub(json.dumps(pattern_summary)),
                Description="Pattern configuration summary",
            )
        )

        # Environment configuration for frontend
        frontend_env_config = {
            "VITE_API_ENDPOINT": self.api.get_api_endpoint(),
            "VITE_ENVIRONMENT": self.environment,
            "VITE_AWS_REGION": Sub("${AWS::Region}"),
        }

        self.template.add_output(
            Output(
                "FrontendEnvironmentConfig",
                Value=Sub(json.dumps(frontend_env_config, indent=2)),
                Description="Environment configuration for frontend application",
            )
        )

    def get_frontend_url(self) -> Any:
        """Get the frontend application URL."""
        return Sub(
            "https://${Domain}", Domain=GetAtt(self.website.distribution, "DomainName")
        )

    def get_api_endpoint(self) -> Any:
        """Get the backend API endpoint."""
        return self.api.get_api_endpoint()

    def get_resources(self) -> Dict[str, Any]:
        """Get all pattern resources."""
        return {
            "api": self.api.get_resources(),
            "website": self.website.resources,
            "combined": self.resources,
        }

    @staticmethod
    def get_default_config(environment: str = "dev") -> Dict[str, Any]:
        """
        Get default configuration for the pattern.

        Args:
            environment: Deployment environment

        Returns:
            Default configuration dictionary
        """
        # Get defaults from sub-patterns
        api_defaults = ServerlessAPIPattern.get_default_config(environment)
        website_defaults = StaticWebsitePattern.get_default_config(environment)

        return {
            "pattern": {"single_page_app": True, "additional_cors_origins": []},
            "api": api_defaults,
            "website": website_defaults,
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
        errors = []

        # Check required sections
        required_sections = ["pattern", "api", "website"]
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required configuration section: {section}")

        # Validate API configuration
        if "api" in config:
            api_errors = ServerlessAPIPattern.validate_config(config["api"])
            errors.extend([f"api.{err}" for err in api_errors])

        # Validate website configuration
        if "website" in config:
            website_errors = StaticWebsitePattern.validate_config(config["website"])
            errors.extend([f"website.{err}" for err in website_errors])

        # Validate pattern-specific configuration
        if "pattern" in config:
            pattern = config["pattern"]

            # Validate CORS origins
            if "additional_cors_origins" in pattern:
                origins = pattern["additional_cors_origins"]
                if not isinstance(origins, list):
                    errors.append("pattern.additional_cors_origins must be a list")
                else:
                    for origin in origins:
                        if not isinstance(origin, str):
                            errors.append("All CORS origins must be strings")
                            break
                        if not (
                            origin.startswith("http://")
                            or origin.startswith("https://")
                        ):
                            errors.append(
                                f"Invalid CORS origin: {origin} (must start with http:// or https://)"
                            )

        return errors

    @staticmethod
    def get_deployment_guide() -> str:
        """
        Get deployment guide for the full stack application.

        Returns:
            Markdown-formatted deployment guide
        """
        return """
# Full Stack Application Deployment Guide

## Prerequisites
- AWS CLI configured with appropriate credentials
- Node.js 20.x or later
- Python 3.11 or later

## Deployment Steps

### 1. Deploy Infrastructure
```bash
# Deploy the CloudFormation stack
aws cloudformation deploy \\
    --template-file template.yaml \\
    --stack-name my-app-{environment} \\
    --capabilities CAPABILITY_IAM \\
    --parameter-overrides Environment={environment}
```

### 2. Deploy Backend
```bash
# Build Lambda function
cd backend
npm install
npm run build

# Package and deploy
zip -r lambda.zip dist node_modules
aws lambda update-function-code \\
    --function-name my-app-api-{environment} \\
    --zip-file fileb://lambda.zip
```

### 3. Deploy Frontend
```bash
# Get deployment values from CloudFormation outputs
BUCKET_NAME=$(aws cloudformation describe-stacks \\
    --stack-name my-app-{environment} \\
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \\
    --output text)

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \\
    --stack-name my-app-{environment} \\
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \\
    --output text)

API_ENDPOINT=$(aws cloudformation describe-stacks \\
    --stack-name my-app-{environment} \\
    --query 'Stacks[0].Outputs[?OutputKey==`BackendAPIEndpoint`].OutputValue' \\
    --output text)

# Build frontend with API endpoint
cd frontend
echo "VITE_API_ENDPOINT=$API_ENDPOINT" > .env.production
npm install
npm run build

# Deploy to S3
aws s3 sync dist/ s3://$BUCKET_NAME --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \\
    --distribution-id $DISTRIBUTION_ID \\
    --paths '/*'
```

## Verification
1. Check CloudFormation stack status
2. Test API endpoint: `curl $API_ENDPOINT/health`
3. Visit frontend URL from CloudFormation outputs
4. Check CloudWatch logs for any errors

## Rollback
To rollback a deployment:
1. Update Lambda to previous version
2. Sync previous frontend build to S3
3. Invalidate CloudFront cache
"""
