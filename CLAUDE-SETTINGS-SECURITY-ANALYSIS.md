# Claude Settings Security Analysis

## Overview

This document analyzes the current Claude settings for the media-register project and provides recommendations for improving security by following the principle of least privilege.

## Current Security Issues

### 1. Overly Broad Permissions

The current permission set has several concerning patterns:

#### Wildcard Command Permissions

- `Bash(python:*)` and `Bash(python3:*)` - Allows execution of ANY Python script with ANY arguments
- `Bash(node:*)` - Allows execution of ANY Node.js script
- `Bash(npm:*)` - Allows ANY npm command including install, uninstall, publish
- `Bash(git:*)` - Allows ANY git operation including force pushes, branch deletions
- `Bash(aws cloudformation:*)` - Allows ANY CloudFormation operation
- `Bash(rm:*)` - Allows deletion of ANY file or directory
- `Bash(find:*)` - Allows searching entire filesystem
- `Bash(grep:*)` - Allows searching any file content
- `Bash(sed:*)` - Allows in-place file modifications
- `Bash(chmod:*)` - Allows changing permissions on ANY file

#### Package Management Risks

- `Bash(brew install:*)` - Can install ANY system package
- `Bash(pip install:*)` and `Bash(pip3 install:*)` - Can install ANY Python package
- `Bash(npm:*)` - Can install ANY npm package

#### AWS Operation Risks

- `Bash(aws cloudformation:*)` - Can create/delete ANY infrastructure
- `Bash(aws iam:*)` operations - Can modify IAM policies and permissions
- `Bash(aws s3:*)` operations - Can access/modify ANY S3 bucket

### 2. Duplicate Permissions

- `Bash(aws cloudformation:*)` appears twice in media-register
- Both `pip install` and `pip3 install` are allowed

### 3. No Deny Rules

The project has no deny rules to explicitly block dangerous operations.

### 4. Hardcoded Specific Commands

Some commands are hardcoded with specific arguments, which is good, but inconsistent:

- `Bash(AWS_REGION=us-west-1 python scripts/deploy_staging_direct.py)`
- Specific test commands

## Recommendations

### 1. Remove Unnecessary Permissions

- Remove duplicate entries
- Remove permissions for tools not used by the project
- Remove overly broad system administration commands

### 2. Make Permissions More Specific

- Replace wildcards with specific allowed operations
- Use explicit command arguments where possible
- Limit file operations to project directories

### 3. Add Deny Rules

- Explicitly deny dangerous operations
- Block access to sensitive directories
- Prevent system-wide changes

### 4. Document Permission Rationale

- Add comments explaining why each permission is needed
- Group related permissions together

## Improved Settings Files

### Common Base Settings

The project should start with these restricted base permissions and add specific needs as required.

### Project-Specific Additions

- **media-register**: Needs deployment script permissions

See the improved settings file for specific recommendations.
