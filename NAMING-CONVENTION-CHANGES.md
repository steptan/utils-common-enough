# 3-Letter Naming Convention Implementation Summary

## Overview

The utils submodule has been updated to support a standardized 3-letter naming convention for all AWS resources. This provides shorter, more consistent resource names across all projects.

## Changes Made

### 1. Core Implementation

- **`src/naming.py`**: New module implementing the naming convention
  - Project code mapping (fraud-or-not → fon, people-cards → pec, media-register → mer)
  - Environment code mapping (development → dev, staging → stg, production → prd)
  - Resource name formatting, validation, and parsing
  - Legacy name detection and conversion

### 2. Config Integration

- **`src/config.py`**: Updated to use 3-letter naming
  - Added `use_3_letter_naming` flag (default: True)
  - Modified `format_name()` method to use naming convention
  - Automatic conversion of project/environment names to codes

### 3. Deployment Updates

- **`src/deployment/fraud_or_not_deployer.py`**: Updated stack naming
  - Uses 3-letter codes for stack names and descriptions
  - Maintains backward compatibility with legacy naming

- **`src/deployment/bucket_rotation.py`**: Updated for new naming
  - Supports both naming conventions during transition
  - Handles mixed environments with legacy and new names

- **`src/deployment/infrastructure.py`**: Passes naming flag to bucket rotation

### 4. Documentation

- **`docs/3-letter-naming-convention.md`**: Comprehensive documentation
  - Pattern explanation and examples
  - Migration guide
  - Best practices and troubleshooting

- **`README.md`**: Added section about 3-letter naming convention

- **`NAMING-QUICK-REFERENCE.md`**: Quick reference for correct naming patterns

### 5. Testing

- **`tests/test_naming.py`**: Comprehensive test suite
  - Tests for all naming convention functions
  - Legacy name conversion tests
  - Validation tests

### 6. Migration Tools

- **`scripts/migrate-to-3letter-naming.py`**: Migration script
  - Scans AWS resources for legacy names
  - Generates migration plans
  - Supports dry-run mode

### 7. Examples

- **`examples/naming_convention_example.py`**: Usage examples
  - Demonstrates all naming convention features
  - Shows integration with project config

## Usage

### Basic Usage

```python
from naming import NamingConvention

# Convert project name to code
code = NamingConvention.get_project_code("fraud-or-not")  # Returns: "fon"

# Format resource name
name = NamingConvention.format_resource_name(
    "fraud-or-not", "development", "frontend"
)  # Returns: "fon-dev-frontend"
```

### With Project Config

```python
config = ProjectConfig(name="fraud-or-not", use_3_letter_naming=True)
stack_name = config.get_stack_name("dev")  # Returns: "fon-dev"
```

### Migration

```bash
# Scan for legacy resources
python scripts/migrate-to-3letter-naming.py --region us-east-1 --scan all

# Generate migration plan
python scripts/migrate-to-3letter-naming.py --region us-east-1 --output plan
```

## Benefits

1. **Shorter Names**: Reduces resource name length, avoiding AWS limits
2. **Consistency**: All resources follow the same pattern
3. **Organization**: Resources sort nicely by project and environment
4. **Cost Tracking**: Easy to filter costs by project code
5. **Clarity**: Clear identification of project and environment

## Backward Compatibility

- The naming convention is enabled by default but can be disabled
- Migration tools help transition existing resources
- The system can parse and work with both naming conventions
- Bucket rotation checks for both patterns to avoid conflicts

## Next Steps

1. Deploy new resources using the 3-letter naming convention
2. Use migration tools to identify legacy resources
3. Plan phased migration for existing resources
4. Update application configurations to use new resource names