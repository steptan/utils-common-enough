# 3-Letter Naming Convention

## Overview

The utils module now supports a standardized 3-letter naming convention for AWS resources. This provides:

- Shorter, more consistent resource names
- Better organization and sorting
- Easier cost tracking by project code
- Compliance with AWS naming length limits

## Convention Pattern

All AWS resources follow the pattern: `[PROJ]-[ENV]-[resource-name]`

### Project Codes

| Project | Code |
|---------|------|
| fraud-or-not | `fon` |
| people-cards | `pec` |
| media-register | `mer` |

### Environment Codes

| Environment | Code |
|-------------|------|
| development/dev | `dev` |
| staging/stage | `stg` |
| production/prod | `prd` |

## Examples

### Resource Names

```
# CloudFormation Stacks
fon-dev                    # Main stack for fraud-or-not development
pec-stg                    # Main stack for people-cards staging

# S3 Buckets
fon-dev-frontend           # Frontend assets bucket
mer-prd-media              # Media storage bucket
pec-dev-lambda-001-023     # Lambda deployment bucket (with rotation)

# DynamoDB Tables
fon-dev-fraud-reports      # Fraud reports table
pec-stg-users             # Users table
mer-prd-sessions          # Sessions table

# Lambda Functions
fon-dev-api               # API handler function
pec-stg-image-processor   # Image processing function
mer-prd-auth              # Authentication function

# IAM Roles
fon-dev-lambda-role       # Lambda execution role
pec-stg-api-role         # API Gateway role
```

## Configuration

### Enabling 3-Letter Naming

The naming convention is enabled by default for all new deployments. It's controlled by the `use_3_letter_naming` flag in `ProjectConfig`:

```python
# In your project configuration
config = ProjectConfig(
    name="fraud-or-not",
    use_3_letter_naming=True  # Default is True
)
```

### Disabling for Legacy Compatibility

If you need to maintain legacy naming during a transition period:

```python
config = ProjectConfig(
    name="fraud-or-not",
    use_3_letter_naming=False  # Use legacy naming
)
```

## Migration

### Identifying Legacy Resources

Use the migration script to identify resources using the old naming convention:

```bash
python scripts/migrate-to-3letter-naming.py \
  --region us-east-1 \
  --scan all \
  --output summary
```

### Generating Migration Plan

Get detailed migration steps:

```bash
python scripts/migrate-to-3letter-naming.py \
  --region us-east-1 \
  --scan all \
  --output plan > migration-plan.md
```

### Resource-Specific Migration

#### S3 Buckets
- Create new bucket with new name
- Copy all objects to new bucket
- Update application configuration
- Delete old bucket after verification

#### DynamoDB Tables
- Option 1: Use AWS Data Migration Service
- Option 2: Export to S3, then import to new table
- Option 3: Use DynamoDB Streams for live migration

#### Lambda Functions
- Create new function with new name
- Copy code and configuration
- Update all integrations
- Test thoroughly
- Delete old function

#### CloudFormation Stacks
- Update template with new naming
- Deploy as new stack
- Migrate resources
- Delete old stack

## Implementation Details

### Naming Module

The `src/naming.py` module provides:

```python
from naming import NamingConvention

# Get project code
code = NamingConvention.get_project_code("fraud-or-not")  # Returns: "fon"

# Format resource name
name = NamingConvention.format_resource_name(
    project="fraud-or-not",
    environment="development",
    resource="frontend"
)  # Returns: "fon-dev-frontend"

# Validate resource name
is_valid = NamingConvention.validate_resource_name("fon-dev-api")  # Returns: True

# Parse resource name
parts = NamingConvention.parse_resource_name("fon-dev-frontend")
# Returns: {'project': 'fon', 'environment': 'dev', 'resource': 'frontend'}

# Check if legacy name
is_legacy = NamingConvention.is_legacy_name("fraud-or-not-dev-frontend-dev")  # Returns: True

# Convert legacy name
new_name = NamingConvention.convert_legacy_name("fraud-or-not-frontend-dev")
# Returns: "fon-dev-frontend"
```

### Config Integration

The `ProjectConfig` class automatically uses 3-letter naming when formatting resource names:

```python
config = ProjectConfig(name="fraud-or-not", use_3_letter_naming=True)

# All these methods return 3-letter formatted names
stack_name = config.get_stack_name("dev")           # Returns: "fon-dev"
bucket_name = config.get_frontend_bucket("dev")     # Returns: "fon-dev-frontend"
lambda_bucket = config.get_lambda_bucket("dev")     # Returns: "fon-dev-lambda-{account_id}"
```

### Bucket Rotation

The `BucketRotationManager` supports both naming conventions:

```python
manager = BucketRotationManager(
    project_name="fraud-or-not",
    environment="dev",
    region="us-east-1",
    account_id="123456789012",
    use_3_letter_naming=True  # Enable 3-letter naming
)

# Creates buckets like: fon-dev-lambda-001-023
new_bucket = manager.rotate_and_create()
```

## Best Practices

1. **Always use lowercase** - AWS resource names should be lowercase
2. **Use hyphens, not underscores** - Maintain consistency with AWS naming
3. **Keep resource descriptors short** - The resource part should be concise
4. **No redundant environment suffixes** - Avoid patterns like `fon-dev-table-dev`
5. **Plan migrations carefully** - Some resources (like S3 buckets) require new names

## Validation Patterns

### Valid Names
```
fon-dev-frontend          ✓
pec-stg-api-gateway       ✓
mer-prd-lambda-auth       ✓
fon-dev-dynamodb-users    ✓
```

### Invalid Names
```
fraud-or-not-dev-frontend     ✗ (uses full project name)
fon-development-api           ✗ (uses full environment name)
fon_dev_frontend              ✗ (uses underscores)
FON-DEV-API                   ✗ (uppercase)
fon-dev-frontend-dev          ✗ (redundant environment)
```

## Troubleshooting

### Resource Not Found After Migration

If applications can't find resources after migration:

1. Check environment variables for hardcoded resource names
2. Update application configuration files
3. Verify IAM policies reference new resource names
4. Check CloudFormation outputs and exports

### Naming Conflicts

If you encounter naming conflicts:

1. S3 buckets are globally unique - add a unique suffix if needed
2. Use the migration script to identify all resources before starting
3. Plan a phased migration for complex applications

### Mixed Naming Environments

During transition, you may have both naming conventions:

1. The naming module can parse both formats
2. Bucket rotation manager checks for both patterns
3. Set `use_3_letter_naming=False` to maintain legacy naming temporarily