"""
Naming convention utilities for 3-letter project and environment codes.

This module provides utilities for converting between full project/environment
names and their 3-letter codes according to the standardized naming convention.
"""

import re
from typing import Dict, Optional


class NamingConvention:
    """Manages 3-letter naming convention for projects and environments."""
    
    # Project code mappings
    PROJECT_CODES: Dict[str, str] = {
        "fraud-or-not": "fon",
        "people-cards": "pec",
        "media-register": "mer",
    }
    
    # Environment code mappings
    ENVIRONMENT_CODES: Dict[str, str] = {
        "development": "dev",
        "dev": "dev",
        "staging": "stg",
        "stage": "stg",
        "production": "prd",
        "prod": "prd",
    }
    
    # Resource name validation pattern
    RESOURCE_NAME_PATTERN = re.compile(r'^[a-z0-9-]+$')
    
    @classmethod
    def get_project_code(cls, project_name: str) -> str:
        """
        Get 3-letter project code from project name.
        
        Args:
            project_name: Full project name (e.g., "fraud-or-not")
            
        Returns:
            3-letter project code (e.g., "fon")
            
        Raises:
            ValueError: If project name is not recognized
        """
        code = cls.PROJECT_CODES.get(project_name)
        if not code:
            # Try to generate a code from the first 3 letters as fallback
            # Remove hyphens and take first 3 letters
            fallback = project_name.replace('-', '')[:3].lower()
            if len(fallback) == 3:
                return fallback
            raise ValueError(f"Unknown project: {project_name}")
        return code
    
    @classmethod
    def get_environment_code(cls, environment: str) -> str:
        """
        Get 3-letter environment code from environment name.
        
        Args:
            environment: Full environment name (e.g., "development", "staging")
            
        Returns:
            3-letter environment code (e.g., "dev", "stg")
            
        Raises:
            ValueError: If environment name is not recognized
        """
        env_lower = environment.lower()
        code = cls.ENVIRONMENT_CODES.get(env_lower)
        if not code:
            # Try to use first 3 letters as fallback
            fallback = env_lower[:3]
            if len(fallback) == 3:
                return fallback
            raise ValueError(f"Unknown environment: {environment}")
        return code
    
    @classmethod
    def format_resource_name(
        cls, 
        project: str, 
        environment: str, 
        resource_name: str
    ) -> str:
        """
        Format a resource name following the 3-letter convention.
        
        Pattern: [PROJ]-[ENV]-[resource-name]
        
        Args:
            project: Project name or code
            environment: Environment name or code
            resource_name: The specific resource name
            
        Returns:
            Formatted resource name (e.g., "fon-dev-frontend")
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Get codes
        project_code = cls.get_project_code(project) if len(project) > 3 else project
        env_code = cls.get_environment_code(environment) if len(environment) > 3 else environment
        
        # Validate resource name
        if not cls.RESOURCE_NAME_PATTERN.match(resource_name):
            raise ValueError(
                f"Invalid resource name: {resource_name}. "
                "Must contain only lowercase letters, numbers, and hyphens."
            )
        
        return f"{project_code}-{env_code}-{resource_name}"
    
    @classmethod
    def validate_resource_name(cls, name: str) -> bool:
        """
        Validate if a resource name follows the 3-letter convention.
        
        Args:
            name: Resource name to validate
            
        Returns:
            True if valid, False otherwise
        """
        pattern = re.compile(r'^(fon|pec|mer)-(dev|stg|prd)-[a-z0-9-]+$')
        return bool(pattern.match(name))
    
    @classmethod
    def parse_resource_name(cls, name: str) -> Optional[Dict[str, str]]:
        """
        Parse a resource name into its components.
        
        Args:
            name: Resource name to parse (e.g., "fon-dev-frontend")
            
        Returns:
            Dictionary with 'project', 'environment', and 'resource' keys,
            or None if the name doesn't match the pattern
        """
        pattern = re.compile(r'^([a-z]{3})-([a-z]{3})-(.+)$')
        match = pattern.match(name)
        
        if match:
            return {
                'project': match.group(1),
                'environment': match.group(2),
                'resource': match.group(3)
            }
        return None
    
    @classmethod
    def is_legacy_name(cls, name: str) -> bool:
        """
        Check if a resource name uses the legacy naming convention.
        
        Args:
            name: Resource name to check
            
        Returns:
            True if it uses legacy naming, False otherwise
        """
        # Legacy patterns to check for
        legacy_patterns = [
            r'fraud-or-not-.*-dev$',
            r'people-cards-.*-prod$',
            r'media-register-.*-staging$',
            r'.*-development-.*',
            r'.*-production-.*',
            r'.*-staging-.*',
        ]
        
        for pattern in legacy_patterns:
            if re.match(pattern, name):
                return True
        return False
    
    @classmethod
    def convert_legacy_name(cls, legacy_name: str) -> Optional[str]:
        """
        Attempt to convert a legacy resource name to the new convention.
        
        Args:
            legacy_name: Legacy resource name
            
        Returns:
            New formatted name or None if conversion isn't possible
        """
        # Try to extract project, environment, and resource from legacy name
        
        # Pattern 1: {project}-{environment}-{resource}-{environment} (redundant env)
        pattern1 = re.compile(r'^(fraud-or-not|people-cards|media-register)-(dev|development|staging|stage|prod|production)-(.+)-(dev|development|staging|stage|prod|production)$')
        match = pattern1.match(legacy_name)
        if match:
            project = match.group(1)
            env = match.group(2)
            resource = match.group(3)
            # Ignore the redundant environment suffix
            return cls.format_resource_name(project, env, resource)
        
        # Pattern 2: {project}-{resource}-{environment}
        pattern2 = re.compile(r'^(fraud-or-not|people-cards|media-register)-(.+)-(dev|development|staging|stage|prod|production)$')
        match = pattern2.match(legacy_name)
        if match:
            project = match.group(1)
            resource = match.group(2)
            env = match.group(3)
            return cls.format_resource_name(project, env, resource)
        
        return None


def get_resource_name(project: str, environment: str, resource: str) -> str:
    """
    Convenience function to format a resource name.
    
    Args:
        project: Project name or code
        environment: Environment name or code
        resource: Resource identifier
        
    Returns:
        Formatted resource name following 3-letter convention
    """
    return NamingConvention.format_resource_name(project, environment, resource)


def validate_name(name: str) -> bool:
    """
    Convenience function to validate a resource name.
    
    Args:
        name: Resource name to validate
        
    Returns:
        True if valid, False otherwise
    """
    return NamingConvention.validate_resource_name(name)