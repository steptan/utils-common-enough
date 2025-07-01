#!/usr/bin/env python3
"""
Configuration Validation Script for Media Register

Validates configuration files against the JSON schema and performs
additional logical validations.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

from config_manager import ConfigManager


def validate_environment_config(environment: str, config_dir: str = "config") -> List[str]:
    """
    Validate configuration for a specific environment.
    
    Args:
        environment: Environment name (dev, staging, prod)
        config_dir: Configuration directory path
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    try:
        # Load configuration
        config_manager = ConfigManager(config_dir=config_dir, environment=environment)
        config = config_manager.config
        
        # Perform additional logical validations
        errors.extend(_validate_network_config(config))
        errors.extend(_validate_storage_config(config))
        errors.extend(_validate_compute_config(config))
        errors.extend(_validate_security_config(config))
        errors.extend(_validate_environment_specific(config, environment))
        
    except Exception as e:
        errors.append(f"Failed to load configuration: {str(e)}")
    
    return errors


def _validate_network_config(config: Dict[str, Any]) -> List[str]:
    """Validate network configuration."""
    errors = []
    
    network = config.get("network", {})
    vpc = network.get("vpc", {})
    subnets = network.get("subnets", {})
    
    # Validate VPC CIDR
    vpc_cidr = vpc.get("cidr")
    if vpc_cidr:
        if not _is_valid_cidr(vpc_cidr):
            errors.append(f"Invalid VPC CIDR: {vpc_cidr}")
    
    # Validate subnet configuration
    public_subnets = subnets.get("public", [])
    private_subnets = subnets.get("private", [])
    
    if not public_subnets:
        errors.append("At least one public subnet is required")
    
    if not private_subnets:
        errors.append("At least one private subnet is required")
    
    # Check subnet CIDR overlaps
    all_subnet_cidrs = []
    for subnet in public_subnets + private_subnets:
        cidr = subnet.get("cidr")
        if cidr:
            if cidr in all_subnet_cidrs:
                errors.append(f"Duplicate subnet CIDR: {cidr}")
            all_subnet_cidrs.append(cidr)
            
            if not _is_valid_cidr(cidr):
                errors.append(f"Invalid subnet CIDR: {cidr}")
    
    # Validate availability zones
    public_azs = [s.get("availability_zone") for s in public_subnets]
    private_azs = [s.get("availability_zone") for s in private_subnets]
    
    if len(set(public_azs)) != len(public_azs):
        errors.append("Public subnets must be in different availability zones")
    
    if len(set(private_azs)) != len(private_azs):
        errors.append("Private subnets must be in different availability zones")
    
    return errors


def _validate_storage_config(config: Dict[str, Any]) -> List[str]:
    """Validate storage configuration."""
    errors = []
    
    storage = config.get("storage", {})
    dynamodb = storage.get("dynamodb", {})
    s3 = storage.get("s3", {})
    
    # Validate DynamoDB configuration
    billing_mode = dynamodb.get("billing_mode")
    if billing_mode and billing_mode not in ["PAY_PER_REQUEST", "PROVISIONED"]:
        errors.append(f"Invalid DynamoDB billing mode: {billing_mode}")
    
    # Validate S3 configuration
    encryption = s3.get("encryption")
    if encryption and encryption not in ["AES256", "aws:kms"]:
        errors.append(f"Invalid S3 encryption type: {encryption}")
    
    return errors


def _validate_compute_config(config: Dict[str, Any]) -> List[str]:
    """Validate compute configuration."""
    errors = []
    
    compute = config.get("compute", {})
    lambda_config = compute.get("lambda", {})
    
    # Validate Lambda runtime
    runtime = lambda_config.get("runtime")
    valid_runtimes = ["python3.9", "python3.10", "python3.11", "python3.12"]
    if runtime and runtime not in valid_runtimes:
        errors.append(f"Invalid Lambda runtime: {runtime}. Must be one of {valid_runtimes}")
    
    # Validate timeout
    timeout = lambda_config.get("timeout")
    if timeout and (timeout < 1 or timeout > 900):
        errors.append(f"Invalid Lambda timeout: {timeout}. Must be between 1 and 900 seconds")
    
    # Validate memory size
    memory_size = lambda_config.get("memory_size")
    if memory_size:
        if memory_size < 128 or memory_size > 10240:
            errors.append(f"Invalid Lambda memory size: {memory_size}. Must be between 128 and 10240 MB")
        if memory_size % 64 != 0:
            errors.append(f"Invalid Lambda memory size: {memory_size}. Must be a multiple of 64 MB")
    
    return errors


def _validate_security_config(config: Dict[str, Any]) -> List[str]:
    """Validate security configuration."""
    errors = []
    
    security = config.get("security", {})
    auth = config.get("auth", {})
    
    # Validate WAF configuration
    waf = security.get("waf", {})
    if waf.get("enabled") and not waf.get("rules"):
        errors.append("WAF is enabled but no rules are configured")
    
    # Validate API Gateway throttling
    api_gateway = security.get("api_gateway", {})
    throttling = api_gateway.get("throttling", {})
    
    rate_limit = throttling.get("rate_limit")
    burst_limit = throttling.get("burst_limit")
    
    if rate_limit and burst_limit and burst_limit < rate_limit:
        errors.append("API Gateway burst limit must be >= rate limit")
    
    # Validate Cognito password policy
    cognito = auth.get("cognito", {})
    password_policy = cognito.get("password_policy", {})
    
    min_length = password_policy.get("minimum_length")
    if min_length and min_length < 6:
        errors.append("Cognito password minimum length must be at least 6")
    
    return errors


def _validate_environment_specific(config: Dict[str, Any], environment: str) -> List[str]:
    """Validate environment-specific constraints."""
    errors = []
    
    # Production-specific validations
    if environment == "prod":
        storage = config.get("storage", {})
        dynamodb = storage.get("dynamodb", {})
        
        if not dynamodb.get("deletion_protection", False):
            errors.append("Production DynamoDB tables must have deletion protection enabled")
        
        if not dynamodb.get("point_in_time_recovery", False):
            errors.append("Production DynamoDB tables must have point-in-time recovery enabled")
        
        security = config.get("security", {})
        waf = security.get("waf", {})
        
        if not waf.get("enabled", False):
            errors.append("Production environment must have WAF enabled")
        
        auth = config.get("auth", {})
        cognito = auth.get("cognito", {})
        
        if cognito.get("mfa_configuration") == "OFF":
            errors.append("Production environment should not disable MFA completely")
    
    # Development-specific validations
    if environment == "dev":
        # Dev environments can have relaxed settings, but warn about potential issues
        pass
    
    return errors


def _is_valid_cidr(cidr: str) -> bool:
    """Validate CIDR notation."""
    try:
        import ipaddress
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False


def validate_all_environments(config_dir: str = "config") -> Dict[str, List[str]]:
    """
    Validate all environment configurations.
    
    Returns:
        Dictionary mapping environment names to their validation errors
    """
    results = {}
    
    # Get list of available environments
    env_dir = Path(config_dir) / "environments"
    if not env_dir.exists():
        return {"error": ["Environment configuration directory not found"]}
    
    env_files = list(env_dir.glob("*.yaml"))
    environments = [f.stem for f in env_files]
    
    for env in environments:
        results[env] = validate_environment_config(env, config_dir)
    
    return results


def main():
    """CLI for configuration validation."""
    parser = argparse.ArgumentParser(
        description="Validate Media Register configuration files"
    )
    parser.add_argument(
        "environment",
        nargs="?",
        help="Environment to validate (dev, staging, prod). If not specified, validates all environments"
    )
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Configuration directory path (default: config)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed validation results"
    )
    
    args = parser.parse_args()
    
    if args.environment:
        # Validate single environment
        errors = validate_environment_config(args.environment, args.config_dir)
        
        if errors:
            print(f"❌ Validation failed for {args.environment} environment:")
            for error in errors:
                print(f"  • {error}")
            sys.exit(1)
        else:
            print(f"✅ {args.environment} environment configuration is valid")
    else:
        # Validate all environments
        results = validate_all_environments(args.config_dir)
        
        total_errors = 0
        for env, errors in results.items():
            if errors:
                total_errors += len(errors)
                print(f"❌ {env} environment has {len(errors)} error(s):")
                for error in errors:
                    print(f"  • {error}")
            else:
                print(f"✅ {env} environment configuration is valid")
        
        if total_errors > 0:
            print(f"\nTotal validation errors: {total_errors}")
            sys.exit(1)
        else:
            print("\n✅ All environment configurations are valid")


if __name__ == "__main__":
    main()