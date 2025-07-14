#!/usr/bin/env python3
"""
Example usage of the 3-letter naming convention in utils.

This demonstrates how to use the naming convention when deploying resources.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_project_config
from src.deployment.bucket_rotation import BucketRotationManager
from src.naming import NamingConvention, get_resource_name


def main():
    """Demonstrate naming convention usage."""
    
    print("3-Letter Naming Convention Examples")
    print("=" * 50)
    print()
    
    # Example 1: Using the naming module directly
    print("1. Direct naming module usage:")
    print("-" * 30)
    
    # Get project codes
    for project in ["fraud-or-not", "people-cards", "media-register"]:
        code = NamingConvention.get_project_code(project)
        print(f"  {project} → {code}")
    print()
    
    # Format resource names
    print("2. Formatting resource names:")
    print("-" * 30)
    
    examples = [
        ("fraud-or-not", "development", "frontend"),
        ("people-cards", "staging", "api-gateway"),
        ("media-register", "production", "lambda-auth"),
    ]
    
    for project, env, resource in examples:
        name = get_resource_name(project, env, resource)
        print(f"  {project}/{env}/{resource} → {name}")
    print()
    
    # Example 2: Using project config
    print("3. Using project configuration:")
    print("-" * 30)
    
    # Get fraud-or-not config
    config = get_project_config("fraud-or-not")
    
    # Check if 3-letter naming is enabled
    print(f"  3-letter naming enabled: {config.use_3_letter_naming}")
    print()
    
    # Generate various resource names
    environments = ["dev", "staging", "prod"]
    
    for env in environments:
        print(f"  Environment: {env}")
        print(f"    Stack name: {config.get_stack_name(env)}")
        print(f"    Frontend bucket: {config.get_frontend_bucket(env)}")
        print(f"    Lambda bucket: {config.get_lambda_bucket(env)}")
        print()
    
    # Example 3: Bucket rotation with new naming
    print("4. Bucket rotation example:")
    print("-" * 30)
    
    # This is a simulation - won't actually create buckets
    print("  Simulating bucket rotation (dry run)...")
    
    # Show what bucket names would look like
    project_code = NamingConvention.get_project_code("fraud-or-not")
    env_code = NamingConvention.get_environment_code("dev")
    
    for i in range(3):
        thousands, number = divmod(i, 1000)
        bucket_name = f"{project_code}-{env_code}-lambda-{thousands:03d}-{number:03d}"
        print(f"    Bucket {i}: {bucket_name}")
    print()
    
    # Example 4: Legacy name conversion
    print("5. Converting legacy names:")
    print("-" * 30)
    
    legacy_names = [
        "fraud-or-not-frontend-dev",
        "people-cards-api-staging",
        "media-register-lambda-production",
        "fraud-or-not-dev-dynamodb-dev",
    ]
    
    for legacy in legacy_names:
        new_name = NamingConvention.convert_legacy_name(legacy)
        if new_name:
            print(f"  {legacy} → {new_name}")
        else:
            print(f"  {legacy} → (cannot convert)")
    print()
    
    # Example 5: Validation
    print("6. Validating resource names:")
    print("-" * 30)
    
    names_to_check = [
        ("fon-dev-frontend", True),
        ("fraud-or-not-dev-frontend", False),
        ("fon-development-api", False),
        ("pec-stg-lambda-function", True),
        ("mer_prd_table", False),
    ]
    
    for name, expected in names_to_check:
        valid = NamingConvention.validate_resource_name(name)
        status = "✓" if valid else "✗"
        print(f"  {name}: {status} (expected: {'valid' if expected else 'invalid'})")
    print()
    
    # Example 6: Parsing resource names
    print("7. Parsing resource names:")
    print("-" * 30)
    
    names_to_parse = [
        "fon-dev-frontend",
        "pec-stg-api",
        "mer-prd-lambda-auth",
    ]
    
    for name in names_to_parse:
        parts = NamingConvention.parse_resource_name(name)
        if parts:
            print(f"  {name}:")
            print(f"    Project: {parts['project']}")
            print(f"    Environment: {parts['environment']}")
            print(f"    Resource: {parts['resource']}")
        else:
            print(f"  {name}: Failed to parse")
    print()
    
    print("Done! These examples show how to use the 3-letter naming convention.")
    print("Remember: This convention is enabled by default for all new deployments.")


if __name__ == "__main__":
    main()