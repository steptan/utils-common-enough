"""
Comprehensive tests for full stack application pattern module.
Tests the complete full-stack app infrastructure pattern with frontend and backend.
"""

import json
import pytest
from troposphere import Template, GetAtt, Ref, Sub
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from typing import Any, Dict, List, Optional, Union

from src.patterns.full_stack_app import FullStackAppPattern


class TestFullStackAppPattern:
    """Test FullStackAppPattern class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template = Template()
        self.environment = "test"
        self.config = {
            "pattern": {
                "single_page_app": True,
                "additional_cors_origins": ["https://test.example.com"]
            },
            "api": {
                "pattern": {
                    "lambda_in_vpc": True,
                    "cost_optimized": True
                },
                "network": {
                    "vpc": {"cidr": "10.0.0.0/16"}
                },
                "compute": {
                    "lambda": {
                        "runtime": "nodejs20.x"
                    }
                },
                "storage": {
                    "dynamodb": {
                        "tables": [
                            {"name": "main"}
                        ]
                    }
                }
            },
            "website": {
                "cloudfront": {
                    "price_class": "PriceClass_100"
                },
                "s3": {
                    "versioning": True
                },
                "domain": {
                    "domain_name": "app.example.com"
                }
            }
        }

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_init_creates_all_components(self, mock_website, mock_api) -> None:
        """Test that initialization creates all infrastructure components."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.get_api_endpoint.return_value = Sub("https://api.example.com")
        mock_api_instance.compute = Mock()
        mock_api_instance.compute.get_api_gateway_id.return_value = Ref("APIGateway")
        mock_api.return_value = mock_api_instance

        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        mock_website_instance.website_bucket = Mock()
        mock_website_instance.resources = {}
        mock_website.return_value = mock_website_instance

        # Create pattern
        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Verify both patterns were created
        mock_api.assert_called_once()
        mock_website.assert_called_once()

        # Verify resources
        assert "api" in pattern.resources
        assert "website" in pattern.resources

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_api_cors_configuration(self, mock_website, mock_api) -> None:
        """Test that API is configured with proper CORS settings."""
        # Setup mocks
        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Check API was called with CORS configuration
        api_config = mock_api.call_args[1]["config"]
        env_vars = api_config["compute"]["lambda"]["environment_variables"]
        
        assert "CORS_ALLOWED_ORIGINS" in env_vars
        assert "CORS_ALLOWED_METHODS" in env_vars
        assert "CORS_ALLOWED_HEADERS" in env_vars
        assert env_vars["CORS_ALLOWED_METHODS"] == "GET,POST,PUT,DELETE,OPTIONS"

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')  
    def test_allowed_origins_dev(self, mock_website, mock_api) -> None:
        """Test allowed origins include localhost for dev environment."""
        self.environment = "dev"
        
        # Setup mocks
        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        type(mock_website_instance.distribution).DomainName = PropertyMock(return_value="test")
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Get allowed origins
        allowed_origins = pattern._get_allowed_origins()
        
        # Convert Sub objects to strings for testing
        origins_str = []
        for origin in allowed_origins:
            if isinstance(origin, Sub):
                origins_str.append("https://cloudfront.domain")
            else:
                origins_str.append(origin)
        
        assert "http://localhost:3000" in origins_str
        assert "http://localhost:3001" in origins_str
        assert "http://127.0.0.1:3000" in origins_str
        assert "https://app.example.com" in origins_str
        assert "https://test.example.com" in origins_str

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_allowed_origins_prod(self, mock_website, mock_api) -> None:
        """Test allowed origins exclude localhost for prod environment."""
        self.environment = "prod"
        
        # Setup mocks
        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        type(mock_website_instance.distribution).DomainName = PropertyMock(return_value="test")
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Get allowed origins
        allowed_origins = pattern._get_allowed_origins()
        
        # Convert to strings for testing
        origins_str = []
        for origin in allowed_origins:
            if not isinstance(origin, Sub):
                origins_str.append(origin)
        
        assert "http://localhost:3000" not in origins_str
        assert "https://app.example.com" in origins_str
        assert "https://test.example.com" in origins_str

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_website_single_page_app_config(self, mock_website, mock_api) -> None:
        """Test website is configured as single page app."""
        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Check website was called with SPA configuration
        website_config = mock_website.call_args[1]["config"]
        assert website_config["pattern"]["single_page_app"] is True

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_pattern_outputs(self, mock_website, mock_api) -> None:
        """Test creation of pattern outputs."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.get_api_endpoint.return_value = Sub("https://api.example.com")
        mock_api_instance.compute = Mock()
        mock_api_instance.compute.get_api_gateway_id.return_value = Ref("APIGateway")
        mock_api.return_value = mock_api_instance

        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        mock_website_instance.website_bucket = Mock()
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Check outputs
        outputs = self.template.outputs
        assert "FrontendURL" in outputs
        assert "BackendAPIEndpoint" in outputs
        assert "DeploymentInstructions" in outputs
        assert "PatternSummary" in outputs
        assert "FrontendEnvironmentConfig" in outputs

        # Check pattern summary
        summary_output = outputs["PatternSummary"]
        summary_value = json.loads(summary_output.Value.data)
        assert summary_value["type"] == "full-stack-app"
        assert summary_value["environment"] == self.environment
        assert summary_value["single_page_app"] is True

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_frontend_environment_config(self, mock_website, mock_api) -> None:
        """Test frontend environment configuration output."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.get_api_endpoint.return_value = Sub("https://api.example.com")
        mock_api.return_value = mock_api_instance

        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        mock_website_instance.website_bucket = Mock()
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Check frontend env config
        outputs = self.template.outputs
        env_config_output = outputs["FrontendEnvironmentConfig"]
        env_config = json.loads(env_config_output.Value.data)
        
        assert "VITE_API_ENDPOINT" in env_config
        assert env_config["VITE_ENVIRONMENT"] == self.environment
        assert "VITE_AWS_REGION" in env_config

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_get_frontend_url(self, mock_website, mock_api) -> None:
        """Test get_frontend_url method."""
        # Setup mocks
        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        url = pattern.get_frontend_url()
        assert isinstance(url, Sub)

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_get_api_endpoint(self, mock_website, mock_api) -> None:
        """Test get_api_endpoint method."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.get_api_endpoint.return_value = Sub("https://api.example.com")
        mock_api.return_value = mock_api_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        endpoint = pattern.get_api_endpoint()
        assert isinstance(endpoint, Sub)
        mock_api_instance.get_api_endpoint.assert_called()

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_get_resources(self, mock_website, mock_api) -> None:
        """Test get_resources method."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.get_resources.return_value = {"network": {}, "compute": {}}
        mock_api.return_value = mock_api_instance

        mock_website_instance = Mock()
        mock_website_instance.resources = {"bucket": {}, "distribution": {}}
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        resources = pattern.get_resources()
        assert "api" in resources
        assert "website" in resources
        assert "combined" in resources

    def test_get_default_config(self) -> None:
        """Test get_default_config static method."""
        # Test development config
        dev_config = FullStackAppPattern.get_default_config("dev")
        assert "pattern" in dev_config
        assert "api" in dev_config
        assert "website" in dev_config
        assert dev_config["pattern"]["single_page_app"] is True
        assert dev_config["pattern"]["additional_cors_origins"] == []

        # Test production config
        prod_config = FullStackAppPattern.get_default_config("prod")
        assert "pattern" in prod_config
        assert "api" in prod_config
        assert "website" in prod_config

    def test_validate_config_valid(self) -> None:
        """Test validate_config with valid configuration."""
        errors = FullStackAppPattern.validate_config(self.config)
        assert len(errors) == 0

    def test_validate_config_missing_sections(self) -> None:
        """Test validate_config with missing sections."""
        invalid_config = {"pattern": {}}
        
        errors = FullStackAppPattern.validate_config(invalid_config)
        assert len(errors) >= 2
        assert any("Missing required configuration section: api" in err for err in errors)
        assert any("Missing required configuration section: website" in err for err in errors)

    def test_validate_config_invalid_cors_origins(self) -> None:
        """Test validate_config with invalid CORS origins."""
        self.config["pattern"]["additional_cors_origins"] = [
            "https://valid.com",
            "invalid-origin",  # Missing protocol
            123  # Not a string
        ]
        
        errors = FullStackAppPattern.validate_config(self.config)
        assert any("must start with http://" in err for err in errors)
        assert any("must be strings" in err for err in errors)

    def test_validate_config_cors_origins_not_list(self) -> None:
        """Test validate_config with CORS origins not as list."""
        self.config["pattern"]["additional_cors_origins"] = "https://example.com"
        
        errors = FullStackAppPattern.validate_config(self.config)
        assert any("must be a list" in err for err in errors)

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern.validate_config')
    def test_validate_config_api_errors(self, mock_api_validate) -> None:
        """Test validate_config propagates API validation errors."""
        mock_api_validate.return_value = ["Invalid runtime"]
        
        errors = FullStackAppPattern.validate_config(self.config)
        assert any("api.Invalid runtime" in err for err in errors)

    @patch('src.patterns.full_stack_app.StaticWebsitePattern.validate_config')
    def test_validate_config_website_errors(self, mock_website_validate) -> None:
        """Test validate_config propagates website validation errors."""
        mock_website_validate.return_value = ["Invalid CloudFront config"]
        
        errors = FullStackAppPattern.validate_config(self.config)
        assert any("website.Invalid CloudFront config" in err for err in errors)

    def test_get_deployment_guide(self) -> None:
        """Test get_deployment_guide static method."""
        guide = FullStackAppPattern.get_deployment_guide()
        
        assert isinstance(guide, str)
        assert "# Full Stack Application Deployment Guide" in guide
        assert "## Prerequisites" in guide
        assert "## Deployment Steps" in guide
        assert "### 1. Deploy Infrastructure" in guide
        assert "### 2. Deploy Backend" in guide
        assert "### 3. Deploy Frontend" in guide
        assert "## Verification" in guide
        assert "## Rollback" in guide

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_deployment_instructions_output(self, mock_website, mock_api) -> None:
        """Test deployment instructions output format."""
        # Setup mocks
        mock_api_instance = Mock()
        mock_api_instance.compute = Mock()
        mock_api_instance.compute.get_api_gateway_id.return_value = Ref("APIGateway")
        mock_api.return_value = mock_api_instance

        mock_website_instance = Mock()
        mock_website_instance.distribution = Mock()
        mock_website_instance.website_bucket = Mock()
        mock_website.return_value = mock_website_instance

        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Check deployment instructions
        outputs = self.template.outputs
        deploy_output = outputs["DeploymentInstructions"]
        deploy_info = json.loads(deploy_output.Value.data)
        
        assert "frontend" in deploy_info
        assert "backend" in deploy_info
        assert "bucket" in deploy_info["frontend"]
        assert "distribution_id" in deploy_info["frontend"]
        assert "deploy_command" in deploy_info["frontend"]
        assert "function_name" in deploy_info["backend"]
        assert "api_id" in deploy_info["backend"]

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_configure_cors_noop(self, mock_website, mock_api) -> None:
        """Test _configure_cors is a no-op (handled by Lambda)."""
        pattern = FullStackAppPattern(
            self.template,
            self.config,
            self.environment
        )

        # Method exists but does nothing
        result = pattern._configure_cors()
        assert result is None

    @patch('src.patterns.full_stack_app.ServerlessAPIPattern')
    @patch('src.patterns.full_stack_app.StaticWebsitePattern')
    def test_minimal_configuration(self, mock_website, mock_api) -> None:
        """Test pattern with minimal configuration."""
        minimal_config = {
            "pattern": {},
            "api": {},
            "website": {}
        }
        
        pattern = FullStackAppPattern(
            self.template,
            minimal_config,
            self.environment
        )
        
        # Should have created both components
        assert pattern.resources["api"] is not None
        assert pattern.resources["website"] is not None