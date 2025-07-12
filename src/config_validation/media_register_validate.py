#!/usr/bin/env python3
"""
Configuration validation script for Media Register
Validates YAML configuration files against the JSON schema
"""

import os
import sys
import yaml
import json
import jsonschema
from pathlib import Path
from typing import Dict, Any, List, Tuple
import argparse
from deepmerge import always_merger


class ConfigValidator:
    """Validates configuration files against schema"""
    
    def __init__(self, schema_path: Path):
        """Initialize with schema file path"""
        self.schema_path = schema_path
        self.schema = self._load_schema()
        
    def _load_schema(self) -> Dict[str, Any]:
        """Load the JSON schema from YAML file"""
        try:
            with open(self.schema_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading schema: {e}")
            sys.exit(1)
    
    def validate_file(self, config_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a single configuration file
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Load configuration
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate against schema
            jsonschema.validate(instance=config, schema=self.schema)
            
            return True, []
            
        except jsonschema.ValidationError as e:
            # Format the error message
            path = '.'.join(str(p) for p in e.absolute_path)
            if path:
                errors.append(f"  - {path}: {e.message}")
            else:
                errors.append(f"  - {e.message}")
                
        except yaml.YAMLError as e:
            errors.append(f"  - YAML parsing error: {e}")
            
        except Exception as e:
            errors.append(f"  - Unexpected error: {e}")
            
        return False, errors
    
    def validate_merged_config(self, base_path: Path, env_path: Path) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate merged configuration (base + environment)
        
        Returns:
            Tuple of (is_valid, list_of_errors, merged_config)
        """
        errors = []
        merged_config = {}
        
        try:
            # Load base configuration
            with open(base_path, 'r') as f:
                base_config = yaml.safe_load(f)
            
            # Load environment configuration
            with open(env_path, 'r') as f:
                env_config = yaml.safe_load(f)
            
            # Deep merge configurations
            merged_config = always_merger.merge(base_config.copy(), env_config)
            
            # Validate merged configuration
            jsonschema.validate(instance=merged_config, schema=self.schema)
            
            return True, [], merged_config
            
        except jsonschema.ValidationError as e:
            # Format the error message
            path = '.'.join(str(p) for p in e.absolute_path)
            if path:
                errors.append(f"  - {path}: {e.message}")
            else:
                errors.append(f"  - {e.message}")
                
        except Exception as e:
            errors.append(f"  - Unexpected error: {e}")
            
        return False, errors, merged_config


def print_validation_results(results: Dict[str, Tuple[bool, List[str]]]):
    """Print validation results in a formatted way"""
    
    all_valid = all(result[0] for result in results.values())
    
    if all_valid:
        print("✅ All configuration files are valid!")
    else:
        print("❌ Configuration validation failed:")
        print()
        
        for file_path, (is_valid, errors) in results.items():
            if not is_valid:
                print(f"📄 {file_path}:")
                for error in errors:
                    print(error)
                print()


def main():
    """Main validation script"""
    parser = argparse.ArgumentParser(
        description='Validate Media Register configuration files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all configuration files
  media-register-validate
  
  # Validate specific environment
  media-register-validate --env dev
  
  # Show merged configuration
  media-register-validate --env staging --show-merged
  
  # Validate with verbose output
  media-register-validate -v
        """
    )
    
    parser.add_argument('--env', '-e', 
                       help='Specific environment to validate')
    parser.add_argument('--show-merged', '-m', action='store_true',
                       help='Show merged configuration (requires --env)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Determine paths - look for config directory relative to current working directory
    current_dir = Path.cwd()
    config_dir = current_dir / 'config'
    
    # If we're in utils, look in parent directory
    if current_dir.name == 'utils':
        config_dir = current_dir.parent / 'config'
    
    schema_path = config_dir / 'validation' / 'schema.yaml'
    base_path = config_dir / 'base.yaml'
    env_dir = config_dir / 'environments'
    
    # Check schema exists
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        sys.exit(1)
    
    # Initialize validator
    validator = ConfigValidator(schema_path)
    
    # Results dictionary
    results = {}
    
    # Validate base configuration
    if base_path.exists():
        is_valid, errors = validator.validate_file(base_path)
        results[str(base_path)] = (is_valid, errors)
        
        if args.verbose and is_valid:
            print(f"✅ {base_path} is valid")
    else:
        print(f"⚠️  Base configuration not found: {base_path}")
    
    # If specific environment requested
    if args.env:
        env_path = env_dir / f"{args.env}.yaml"
        
        if not env_path.exists():
            print(f"❌ Environment configuration not found: {env_path}")
            sys.exit(1)
        
        # Validate environment file alone
        is_valid, errors = validator.validate_file(env_path)
        results[str(env_path)] = (is_valid, errors)
        
        if args.verbose and is_valid:
            print(f"✅ {env_path} is valid")
        
        # Validate merged configuration
        if base_path.exists():
            is_valid, errors, merged_config = validator.validate_merged_config(base_path, env_path)
            results[f"Merged ({args.env})"] = (is_valid, errors)
            
            if args.verbose and is_valid:
                print(f"✅ Merged configuration for {args.env} is valid")
            
            # Show merged configuration if requested
            if args.show_merged and is_valid:
                print("\n📋 Merged configuration:")
                print(yaml.dump(merged_config, default_flow_style=False, sort_keys=False))
    
    else:
        # Validate all environment files
        if env_dir.exists():
            for env_file in env_dir.glob('*.yaml'):
                is_valid, errors = validator.validate_file(env_file)
                results[str(env_file)] = (is_valid, errors)
                
                if args.verbose and is_valid:
                    print(f"✅ {env_file} is valid")
                
                # Also validate merged configs
                if base_path.exists():
                    env_name = env_file.stem
                    is_valid, errors, _ = validator.validate_merged_config(base_path, env_file)
                    results[f"Merged ({env_name})"] = (is_valid, errors)
                    
                    if args.verbose and is_valid:
                        print(f"✅ Merged configuration for {env_name} is valid")
    
    # Print results
    print()
    print_validation_results(results)
    
    # Exit with appropriate code
    all_valid = all(result[0] for result in results.values())
    sys.exit(0 if all_valid else 1)


if __name__ == '__main__':
    main()