# Centralized IAM Management Guide

This guide explains how to use the centralized IAM management system for the people-cards project.

## Overview

The centralized IAM management system replaces inline IAM roles and policies in CloudFormation templates with centrally managed roles. This provides:

- **Consistency**: Standardized IAM management approach
- **Security**: Centralized policy management with least privilege
- **Simplicity**: No duplicate IAM code across templates
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
   - Handles project access

3. **IAM Permission Updater** (`update_iam_permissions.py`)
   - Updates existing IAM policies
   - Adds missing permissions
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

- `central-people-cards-lambda-{env}` - For people-cards Lambda functions

### Step 2: Update CI/CD User Permissions

```bash
# Check current permissions
python src/scripts/update_iam_permissions.py check \
  --user-name people-cards-cicd \
  --project people-cards

# Update permissions (dry run)
python src/scripts/update_iam_permissions.py update \
  --user-name people-cards-cicd \
  --project people-cards \
  --dry-run

# Update permissions (actual)
python src/scripts/update_iam_permissions.py update \
  --user-name people-cards-cicd \
  --project people-cards
```

### Step 3: Deploy CloudFormation Stacks

Use the centralized IAM templates with the role ARNs from Step 1:

```bash
aws cloudformation deploy \
  --template-file cloudformation-centralized-iam.yaml \
  --stack-name people-cards-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    LambdaExecutionRoleArn=arn:aws:iam::123456789012:role/central-people-cards-lambda-dev
```

### Step 4: Update Lambda Functions

Update Lambda function configurations to use the centralized roles:

```python
# In your Lambda deployment code
lambda_role_arn = f"arn:aws:iam::{account_id}:role/central-people-cards-lambda-{environment}"
```

## Using Unified User Permissions

The newer unified permissions system creates 5 categorized policies per user:

```bash
# Update permissions with categorized policies
python src/scripts/unified_user_permissions.py update \
  --user people-cards-cicd

# Show current permissions
python src/scripts/unified_user_permissions.py show \
  --user people-cards-cicd

# Generate specific category policy
python src/scripts/unified_user_permissions.py generate \
  --user people-cards-cicd \
  --projects people-cards \
  --category infrastructure \
  --output policy.json
```

## Role Configuration

### Lambda Execution Role

The centralized Lambda execution role includes:

- **Basic Lambda permissions**: Logs, metrics, X-Ray tracing
- **DynamoDB access**: Full access to project tables
- **S3 access**: Read/write to project buckets
- **API Gateway integration**: Invoke permissions
- **Cognito integration**: User pool access
- **SSM Parameter Store**: Read access to project parameters

### Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

## Best Practices

1. **Environment Separation**: Use different roles for dev, staging, and prod
2. **Least Privilege**: Only grant permissions that are actually needed
3. **Resource Scoping**: Always scope resources by project name
4. **Regular Audits**: Review permissions quarterly
5. **Version Control**: Track all IAM changes in git

## Troubleshooting

### Common Issues

1. **Missing Permissions**: Check CloudTrail logs to identify required permissions
2. **Trust Policy Issues**: Ensure Lambda service can assume the role
3. **Policy Size Limits**: Use the 5-policy approach for CI/CD users

### Debugging Commands

```bash
# Test role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/central-people-cards-lambda-dev \
  --role-session-name test-session

# List role policies
aws iam list-role-policies \
  --role-name central-people-cards-lambda-dev

# Get policy details
aws iam get-role-policy \
  --role-name central-people-cards-lambda-dev \
  --policy-name DynamoDBAccess
```

## Migration from Inline IAM

If migrating from inline IAM in CloudFormation:

1. Create centralized roles using the script
2. Update CloudFormation templates to use role ARNs as parameters
3. Test Lambda functions with new roles
4. Remove inline IAM resources from templates
5. Delete old inline roles after validation

## Security Considerations

1. **Role Boundaries**: Set permission boundaries on Lambda roles
2. **Tagging**: Tag all IAM resources for tracking
3. **Monitoring**: Set up CloudTrail alerts for role usage
4. **Compliance**: Ensure roles meet organizational policies