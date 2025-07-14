"""
Tests for the 3-letter naming convention module.
"""

import pytest

from src.naming import NamingConvention, get_resource_name, validate_name


class TestNamingConvention:
    """Test the NamingConvention class."""
    
    def test_get_project_code(self):
        """Test project code mapping."""
        assert NamingConvention.get_project_code("fraud-or-not") == "fon"
        assert NamingConvention.get_project_code("people-cards") == "pec"
        assert NamingConvention.get_project_code("media-register") == "mer"
        
        # Test fallback for unknown projects
        assert NamingConvention.get_project_code("new-project") == "new"
        
        # Test error for short names
        with pytest.raises(ValueError):
            NamingConvention.get_project_code("ab")
    
    def test_get_environment_code(self):
        """Test environment code mapping."""
        assert NamingConvention.get_environment_code("development") == "dev"
        assert NamingConvention.get_environment_code("dev") == "dev"
        assert NamingConvention.get_environment_code("staging") == "stg"
        assert NamingConvention.get_environment_code("stage") == "stg"
        assert NamingConvention.get_environment_code("production") == "prd"
        assert NamingConvention.get_environment_code("prod") == "prd"
        
        # Test fallback
        assert NamingConvention.get_environment_code("testing") == "tes"
    
    def test_format_resource_name(self):
        """Test resource name formatting."""
        # Test with full names
        assert NamingConvention.format_resource_name(
            "fraud-or-not", "development", "frontend"
        ) == "fon-dev-frontend"
        
        assert NamingConvention.format_resource_name(
            "people-cards", "staging", "api-gateway"
        ) == "pec-stg-api-gateway"
        
        # Test with codes
        assert NamingConvention.format_resource_name(
            "fon", "dev", "lambda-role"
        ) == "fon-dev-lambda-role"
        
        # Test invalid resource names
        with pytest.raises(ValueError):
            NamingConvention.format_resource_name(
                "fon", "dev", "Invalid_Resource"
            )
    
    def test_validate_resource_name(self):
        """Test resource name validation."""
        # Valid names
        assert NamingConvention.validate_resource_name("fon-dev-frontend")
        assert NamingConvention.validate_resource_name("pec-stg-api-gateway")
        assert NamingConvention.validate_resource_name("mer-prd-lambda-001-002")
        
        # Invalid names
        assert not NamingConvention.validate_resource_name("fraud-or-not-dev-frontend")
        assert not NamingConvention.validate_resource_name("fon-development-frontend")
        assert not NamingConvention.validate_resource_name("fon_dev_frontend")
        assert not NamingConvention.validate_resource_name("FON-DEV-frontend")
    
    def test_parse_resource_name(self):
        """Test parsing resource names."""
        # Valid parse
        result = NamingConvention.parse_resource_name("fon-dev-frontend")
        assert result == {
            'project': 'fon',
            'environment': 'dev',
            'resource': 'frontend'
        }
        
        result = NamingConvention.parse_resource_name("pec-stg-api-gateway")
        assert result == {
            'project': 'pec',
            'environment': 'stg',
            'resource': 'api-gateway'
        }
        
        # Invalid parse
        assert NamingConvention.parse_resource_name("invalid-name") is None
        assert NamingConvention.parse_resource_name("fraud-or-not-dev-frontend") is None
    
    def test_is_legacy_name(self):
        """Test legacy name detection."""
        # Legacy names
        assert NamingConvention.is_legacy_name("fraud-or-not-frontend-dev")
        assert NamingConvention.is_legacy_name("people-cards-api-prod")
        assert NamingConvention.is_legacy_name("media-register-lambda-staging")
        assert NamingConvention.is_legacy_name("fraud-or-not-development-vpc")
        
        # New names
        assert not NamingConvention.is_legacy_name("fon-dev-frontend")
        assert not NamingConvention.is_legacy_name("pec-stg-api")
        assert not NamingConvention.is_legacy_name("mer-prd-lambda")
    
    def test_convert_legacy_name(self):
        """Test legacy name conversion."""
        # Convertible names
        assert NamingConvention.convert_legacy_name(
            "fraud-or-not-frontend-dev"
        ) == "fon-dev-frontend"
        
        assert NamingConvention.convert_legacy_name(
            "people-cards-api-staging"
        ) == "pec-stg-api"
        
        assert NamingConvention.convert_legacy_name(
            "media-register-lambda-production"
        ) == "mer-prd-lambda"
        
        # Handles redundant environment suffix
        assert NamingConvention.convert_legacy_name(
            "fraud-or-not-dev-frontend-dev"
        ) == "fon-dev-frontend"
        
        # Non-convertible names
        assert NamingConvention.convert_legacy_name("some-random-name") is None


class TestConvenienceFunctions:
    """Test the convenience functions."""
    
    def test_get_resource_name(self):
        """Test the get_resource_name convenience function."""
        assert get_resource_name(
            "fraud-or-not", "development", "dynamodb-table"
        ) == "fon-dev-dynamodb-table"
    
    def test_validate_name(self):
        """Test the validate_name convenience function."""
        assert validate_name("fon-dev-frontend")
        assert not validate_name("invalid-resource-name")