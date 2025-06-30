"""Configuration file validation."""

import os
import sys
import yaml
import jsonschema
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CloudFormationYAMLLoader(yaml.SafeLoader):
    """YAML loader that can handle CloudFormation intrinsic functions."""
    pass


# Register CloudFormation intrinsic functions as constructors
def cfn_tag_constructor(loader, tag_suffix, node):
    """Generic constructor for CloudFormation tags."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    else:
        raise yaml.constructor.ConstructorError(
            None, None,
            f"could not determine a constructor for the tag '!{tag_suffix}'",
            node.start_mark)


# Register all CloudFormation intrinsic functions
cfn_tags = [
    'Ref', 'GetAtt', 'GetAZs', 'ImportValue', 'Join', 'Select',
    'Split', 'Sub', 'Transform', 'Base64', 'Cidr', 'FindInMap',
    'GetParam', 'Condition', 'Equals', 'If', 'Not', 'And', 'Or'
]

for tag in cfn_tags:
    CloudFormationYAMLLoader.add_constructor(
        f'!{tag}',
        lambda loader, node, tag=tag: cfn_tag_constructor(loader, tag, node)
    )


class ConfigurationValidator:
    """Validates project configuration files."""
    
    def __init__(self, project_name: str, config_dir: Optional[Path] = None):
        """Initialize the configuration validator.
        
        Args:
            project_name: Name of the project
            config_dir: Path to config directory (defaults to project config dir)
        """
        self.project_name = project_name
        self.config_dir = config_dir or self._find_config_dir()
        
    def _find_config_dir(self) -> Path:
        """Find the configuration directory for the project."""
        # Try common locations
        locations = [
            Path.cwd() / 'config',
            Path.cwd() / self.project_name / 'config',
            Path(__file__).parent.parent.parent / 'config',
        ]
        
        for loc in locations:
            if loc.exists() and loc.is_dir():
                return loc
                
        raise FileNotFoundError(f"Could not find config directory for {self.project_name}")
    
    def load_schema(self) -> Dict[str, Any]:
        """Load the configuration schema."""
        schema_path = self.config_dir / 'validation' / 'schema.yaml'
        
        if not schema_path.exists():
            logger.warning(f"Schema file not found: {schema_path}")
            return {}
        
        with open(schema_path, 'r') as f:
            return yaml.load(f, Loader=CloudFormationYAMLLoader)
    
    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return yaml.load(f, Loader=CloudFormationYAMLLoader)
    
    def merge_config(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge override configuration into base configuration."""
        def merge_table_arrays(base_tables: list, override_tables: list) -> list:
            """Special handling for DynamoDB table arrays - merge by name."""
            result = []
            base_by_name = {table['name']: table for table in base_tables}
            override_by_name = {table['name']: table for table in override_tables}
            
            # Process all tables from base
            for name, base_table in base_by_name.items():
                if name in override_by_name:
                    # Merge the override into the base table
                    merged_table = base_table.copy()
                    merged_table.update(override_by_name[name])
                    result.append(merged_table)
                else:
                    # Keep base table as-is
                    result.append(base_table)
            
            # Add any new tables from override
            for name, override_table in override_by_name.items():
                if name not in base_by_name:
                    result.append(override_table)
            
            return result
        
        def deep_merge(base: Dict[str, Any], override: Dict[str, Any], path: str = '') -> Dict[str, Any]:
            result = base.copy()
            
            for key, value in override.items():
                current_path = f"{path}.{key}" if path else key
                
                if key in result:
                    # Special handling for DynamoDB tables array
                    if current_path == 'storage.dynamodb.tables' and isinstance(result[key], list) and isinstance(value, list):
                        result[key] = merge_table_arrays(result[key], value)
                    elif isinstance(result[key], dict) and isinstance(value, dict):
                        result[key] = deep_merge(result[key], value, current_path)
                    else:
                        result[key] = value
                else:
                    result[key] = value
            
            return result
        
        return deep_merge(base_config, override_config)
    
    def validate_config(self, config: Dict[str, Any], schema: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate configuration against schema.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if not schema:
            logger.warning("No schema available for validation")
            return True, []
        
        try:
            jsonschema.validate(config, schema)
            return True, []
        except jsonschema.ValidationError as e:
            errors.append(f"Configuration validation failed: {e.message}")
            errors.append(f"Failed at path: {' -> '.join(str(x) for x in e.absolute_path)}")
            return False, errors
        except jsonschema.SchemaError as e:
            errors.append(f"Schema validation failed: {e.message}")
            return False, errors
    
    def validate_environment(self, environment: str) -> tuple[bool, Dict[str, Any]]:
        """Validate configuration for a specific environment.
        
        Returns:
            Tuple of (is_valid, validation_result)
        """
        result = {
            'environment': environment,
            'valid': False,
            'errors': [],
            'warnings': [],
            'merged_config': None
        }
        
        try:
            # Load schema
            logger.info("Loading configuration schema")
            schema = self.load_schema()
            
            # Load base configuration
            base_config_path = self.config_dir / 'base.yaml'
            logger.info(f"Loading base configuration: {base_config_path}")
            base_config = self.load_config(base_config_path)
            
            # Load environment-specific configuration
            env_config_path = self.config_dir / 'environments' / f'{environment}.yaml'
            if env_config_path.exists():
                logger.info(f"Loading environment configuration: {env_config_path}")
                env_config = self.load_config(env_config_path)
                
                # Merge configurations
                final_config = self.merge_config(base_config, env_config)
            else:
                result['warnings'].append(f"No environment-specific configuration found for {environment}")
                final_config = base_config
            
            result['merged_config'] = final_config
            
            # Validate merged configuration
            logger.info(f"Validating configuration for environment: {environment}")
            is_valid, errors = self.validate_config(final_config, schema)
            
            result['valid'] = is_valid
            result['errors'].extend(errors)
            
            return is_valid, result
            
        except Exception as e:
            result['errors'].append(f"Error during validation: {str(e)}")
            return False, result
    
    def validate_all_environments(self) -> Dict[str, Any]:
        """Validate configurations for all environments.
        
        Returns:
            Dictionary with validation results for all environments
        """
        environments_dir = self.config_dir / 'environments'
        results = {
            'all_valid': True,
            'environments': {}
        }
        
        if not environments_dir.exists():
            logger.error(f"Environments directory not found: {environments_dir}")
            results['all_valid'] = False
            results['error'] = "Environments directory not found"
            return results
        
        # Find all environment files
        env_files = list(environments_dir.glob('*.yaml'))
        environments = [f.stem for f in env_files]
        
        if not environments:
            logger.warning("No environment configurations found")
            return results
        
        logger.info(f"Found environments: {', '.join(environments)}")
        
        for env in environments:
            logger.info(f"Validating {env} environment")
            is_valid, result = self.validate_environment(env)
            results['environments'][env] = result
            if not is_valid:
                results['all_valid'] = False
        
        return results