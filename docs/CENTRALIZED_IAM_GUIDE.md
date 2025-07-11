# Centralized IAM Management Guide

This guide explains how to use the centralized IAM management system for the media-register project.

## Overview

The centralized IAM management system replaces inline IAM roles and policies in CloudFormation templates with centrally managed roles. This provides:

- **Consistency**: The project uses a standardized IAM management approach
- **Security**: Centralized policy management with least privilege
- **Simplicity**: No duplicate IAM code across projects
- **Maintainability**: Update permissions in one place

## Architecture

### Components

1. **Centralized Role Manager** (`create_centralized_roles.py`)
   - Creates IAM roles for Lambda functions
   - Manages trust policies and permissions
   - Supports multiple environments (dev, staging, prod)

2. **Unified Permission Manager** (`unified_user_permissions.py`)
   - Manages CI/CD user permissions
   - Generates categorized policies
   - Handles multi-project access

3. **IAM Permission Updater** (`update_iam_permissions.py`)
   - Updates existing IAM policies
   - Adds missing permissions discovered during development
   - Supports dry-run mode

## Setup Guide

### Step 1: Create Centralized IAM Roles

```bash
cd /Users/sj/projects/utils

# Create roles for development environment
python src/scripts/create_centralized_roles.py \
  --environment dev \
  --output roles-dev.json

# Create roles for production environment
python src/scripts/create_centralized_roles.py \
  --environment prod \
  --output roles-prod.json
```

This creates the following roles:

- `central-media-register-lambda-{env}` - For media-register Lambda

### Step 2: Update CI/CD User Permissions

```bash
# Check current permissions
python src/scripts/update_iam_permissions.py check \
  --user-name media-register-cicd \
  --project media-register

# Update permissions (dry run)
python src/scripts/update_iam_permissions.py update \
  --user-name media-register-cicd \
  --project media-register \
  --dry-run

# Update permissions (actual)
python src/scripts/update_iam_permissions.py update \
  --user-name media-register-cicd \
  --project media-register
```

### Step 3: Deploy CloudFormation Stacks

Use the centralized IAM templates with the role ARNs from Step 1:

#### media-register

```bash
aws cloudformation deploy \
  --template-file deploy/template-centralized-iam.yaml \
  --stack-name media-register-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    LambdaExecutionRoleArn=arn:aws:iam::123456789012:role/central-media-register-lambda-dev
```
## Managing Permissions

### Adding New Permissions

1. Edit the appropriate policy generator in `create_centralized_roles.py`
2. Re-run the script to update the roles
3. The changes take effect immediately

### Viewing Current Permissions

```bash
# View all permissions for a CI/CD user
python src/scripts/unified_user_permissions.py list \
  --user media-register-cicd

# Generate policy for specific category
python src/scripts/unified_user_permissions.py generate \
  --user media-register-cicd \
  --category compute \
  --output compute-policy.json
```

### Updating All Projects

```bash
# Update all CI/CD users with latest permissions
python src/scripts/unified_user_permissions.py update-all
```

## Best Practices

1. **Environment Separation**: Always use environment-specific roles (dev, staging, prod)
2. **Least Privilege**: Roles only have permissions they absolutely need
3. **Resource Scoping**: Permissions are scoped to specific resources using naming patterns
4. **Regular Audits**: Use the permission checking tools to audit access regularly
5. **Version Control**: Track all IAM changes in git

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   - Check CloudWatch logs for specific permission failures
   - Run permission check to see current permissions
   - Update roles using the centralized scripts

2. **Stack Deployment Failures**
   - Ensure role ARNs are correct
   - Verify the roles exist before deployment
   - Check CloudFormation events for specific errors

3. **Authentication Issues**
   - Verify Cognito User Pool is created
   - Check environment variables are set correctly
   - Ensure Lambda has access to Cognito

### Support Commands

```bash
# Check if role exists
aws iam get-role --role-name central-fraud-reports-dev

# List inline policies for a role
aws iam list-role-policies --role-name central-fraud-reports-dev

# View specific policy
aws iam get-role-policy \
  --role-name central-fraud-reports-dev \
  --policy-name main

# Test Lambda execution role
aws lambda get-function \
  --function-name media-register-api-dev \
  --query 'Configuration.Role'
```

## Migration Checklist

- [ ] Create centralized IAM roles for all environments
- [ ] Update CI/CD user permissions
- [ ] Deploy new CloudFormation templates
- [ ] Test Lambda functions with new roles
- [ ] Remove old inline IAM policies from original templates
- [ ] Update deployment documentation
- [ ] Test authentication flows

## Next Steps

1. Set up automated IAM policy validation in CI/CD pipeline
2. Implement policy versioning and rollback
3. Add monitoring for permission usage
4. Create dashboard for IAM management
5. Implement cross-account role management for production
