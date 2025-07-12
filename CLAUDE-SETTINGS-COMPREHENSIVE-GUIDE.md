# Claude Settings Comprehensive Guide

## Overview

This guide consolidates the analysis, security recommendations, and implementation steps for Claude settings across the fraud-or-not, media-register, and people-cards projects. The goal is to improve security by following the principle of least privilege while maintaining necessary functionality.

Claude settings control what operations Claude can perform through the Bash tool. The settings are stored in `.claude/settings.local.json` files within each project directory.

## Current State Analysis

### Projects Analyzed

- **fraud-or-not**: Most customized with project-specific test commands
- **media-register**: Includes submodule push script permissions
- **people-cards**: Cleanest, most minimal permission set
- **github-build-logs**: Utility for CI/CD monitoring

### Common Permissions Across All Projects

All projects share approximately 95% of their permissions, organized into these categories:

#### Testing
- `Bash(pytest:*)` - Python test runner
- `Bash(python -m pytest:*)` - Python module test execution
- `Bash(npm test:*)` - Node.js test runner
- `Bash(jest:*)` - JavaScript test framework

#### Development Tools
- `Bash(python:*)` / `Bash(python3:*)` - Python interpreter (SECURITY RISK: too broad)
- `Bash(node:*)` - Node.js runtime (SECURITY RISK: too broad)
- `Bash(npm:*)` - Node package manager (SECURITY RISK: too broad)
- `Bash(pip install:*)` - Python package installer

#### Build & Deploy
- `Bash(make:*)` - Make build tool
- `Bash(./scripts/*.sh:*)` - Shell scripts execution
- `Bash(project-utils:*)` - Project utilities
- `Bash(project-deploy:*)` - Project deployment

#### AWS Operations
- `Bash(aws cloudformation:*)` - CloudFormation commands (SECURITY RISK: too broad)
- `Bash(aws s3:*)` - S3 operations (SECURITY RISK: too broad)
- `Bash(aws lambda:*)` - Lambda operations
- `Bash(aws iam list-*:*)` - IAM list operations
- `Bash(aws iam attach-user-policy:*)` - Attach IAM policies

#### Git Operations
- `Bash(git:*)` - Git version control (SECURITY RISK: too broad)
- `Bash(gh:*)` - GitHub CLI

#### File Operations
- `Bash(ls:*)`, `Bash(find:*)`, `Bash(grep:*)` - File searching
- `Bash(rm:*)` - Remove files (SECURITY RISK: too broad)
- `Bash(chmod:*)` - Change permissions (SECURITY RISK: too broad)

### Common Deny Permissions

All projects currently share these deny rules:

- `Bash(rm -rf /*)` - Prevent root deletion
- `Bash(rm -rf ~/*)` - Prevent home deletion
- `Bash(sudo:*)` - Prevent sudo usage
- `Bash(*:~/.aws/*)` - Protect AWS credentials
- `Bash(*:~/.ssh/*)` - Protect SSH keys
- `Bash(git push --force:*)` - Prevent force push
- `Bash(aws s3 rm s3://* --recursive)` - Prevent S3 recursive deletion
- `Bash(aws iam delete-*:*)` - Prevent IAM deletions

### Issues Identified

1. **Duplicate Permissions**: fraud-or-not has `Bash(find:*)` listed twice
2. **Project-Specific Test Commands**: Hardcoded test commands that should be generalized
3. **One-Time Setup Commands**: Language copying commands in fraud-or-not
4. **Formatting Inconsistencies**: people-cards has better formatting than others

## Security Issues & Recommendations

### Major Security Concerns

#### 1. Overly Broad Wildcard Permissions

The current settings allow dangerous operations through wildcards:

- **Code Execution**: `python:*`, `node:*` allow execution of ANY script
- **Package Installation**: `npm:*`, `pip install:*` can install ANY package
- **File Operations**: `rm:*`, `chmod:*` can modify ANY file
- **AWS Operations**: `aws cloudformation:*` can create/delete ANY infrastructure
- **Git Operations**: `git:*` allows ANY git operation including destructive ones

#### 2. Insufficient Deny Rules

Current deny rules don't cover:
- System package installation (brew, apt-get)
- Directory traversal attacks
- AWS account-wide operations
- Dangerous file permission changes (chmod 777)

#### 3. No Project Isolation

Permissions aren't scoped to project directories or AWS resources, allowing cross-project interference.

### Security Recommendations

1. **Remove Wildcards**: Replace with specific, allowed operations
2. **Add Comprehensive Deny Rules**: Block dangerous patterns explicitly
3. **Implement Project Isolation**: Limit operations to project-specific resources
4. **Document Permissions**: Explain why each permission is necessary
5. **Regular Audits**: Review and update permissions quarterly

## Implementation Guide

### Implementation Steps

#### 1. Backup Current Settings

```bash
# For each project, backup the current settings
cp /Users/sj/projects/fraud-or-not/.claude/settings.local.json \
   /Users/sj/projects/fraud-or-not/.claude/settings.local.json.backup

cp /Users/sj/projects/media-register/.claude/settings.local.json \
   /Users/sj/projects/media-register/.claude/settings.local.json.backup

cp /Users/sj/projects/people-cards/.claude/settings.local.json \
   /Users/sj/projects/people-cards/.claude/settings.local.json.backup

cp /Users/sj/projects/people-cards/utils/github-build-logs/.claude/settings.local.json \
   /Users/sj/projects/people-cards/utils/github-build-logs/.claude/settings.local.json.backup
```

#### 2. Copy New Settings Files

```bash
# Copy the improved settings to each project
cp /Users/sj/projects/utils/claude-settings-improved/fraud-or-not-settings.local.json \
   /Users/sj/projects/fraud-or-not/.claude/settings.local.json

cp /Users/sj/projects/utils/claude-settings-improved/media-register-settings.local.json \
   /Users/sj/projects/media-register/.claude/settings.local.json

cp /Users/sj/projects/utils/claude-settings-improved/people-cards-settings.local.json \
   /Users/sj/projects/people-cards/.claude/settings.local.json

cp /Users/sj/projects/utils/claude-settings-improved/github-build-logs-settings.local.json \
   /Users/sj/projects/people-cards/utils/github-build-logs/.claude/settings.local.json
```

#### 3. Test Claude Functionality

After updating settings, verify Claude can still:
- Run build scripts
- Execute tests
- Deploy to staging
- Perform necessary git operations
- Access required AWS resources

#### 4. Adjust as Needed

If Claude needs additional permissions:
1. Add specific commands to the allow list (avoid wildcards)
2. Document why the permission is needed
3. Consider if a deny rule should also be added

### Ongoing Maintenance

#### Regular Reviews
- Review settings quarterly
- After adding new functionality, check if permissions need updating
- Remove permissions for deprecated features

#### Permission Request Guidelines
When Claude requests a new permission:
1. Verify it's necessary for the task
2. Make it as specific as possible
3. Add to allow list only if truly needed
4. Consider adding related deny rules

#### Security Best Practices
1. Never use wildcards unless absolutely necessary
2. Always specify full command paths for scripts
3. Limit AWS operations to specific resources
4. Regularly audit what permissions are actually used
5. Keep deny rules updated with new dangerous patterns

## Improved Settings Structure

The improved settings follow this structure for each project:

### Allow Permissions (Specific and Limited)

#### Testing & Development
```json
"Bash(pytest tests/)": "Run tests in tests directory only",
"Bash(python -m pytest tests/)": "Run pytest as module",
"Bash(npm test)": "Run npm test script only",
"Bash(npm run build)": "Run build script only"
```

#### Git Operations (Specific)
```json
"Bash(git status)": "Check git status",
"Bash(git add .)": "Stage files",
"Bash(git commit -m *)": "Commit with message",
"Bash(git push origin)": "Push to origin only"
```

#### AWS Operations (Project-Scoped)
```json
"Bash(aws cloudformation describe-stacks --stack-name fraud-or-not-*)": "Project stacks only",
"Bash(aws s3 ls s3://fraud-or-not-*)": "Project buckets only"
```

#### File Operations (Directory-Limited)
```json
"Bash(ls ./)": "List current directory",
"Bash(find ./ -name *)": "Find in current directory",
"Bash(rm ./*)": "Remove files in current directory only"
```

### Deny Permissions (Comprehensive)

#### Dangerous Operations
```json
"Bash(rm -rf /*)": "Prevent root deletion",
"Bash(chmod 777 *)": "Prevent insecure permissions",
"Bash(sudo *)": "Prevent privilege escalation"
```

#### System Changes
```json
"Bash(brew install *)": "Prevent system package installation",
"Bash(apt-get *)": "Prevent system modifications"
```

#### Sensitive Access
```json
"Bash(*~/.aws/*)": "Protect AWS credentials",
"Bash(*~/.ssh/*)": "Protect SSH keys",
"Bash(*.env*)": "Protect environment files"
```

#### AWS Account-Wide Operations
```json
"Bash(aws iam create-*)": "Prevent IAM creation",
"Bash(aws iam delete-*)": "Prevent IAM deletion",
"Bash(aws * --all)": "Prevent account-wide operations"
```

## Benefits of These Changes

1. **Reduced Attack Surface**: Limiting permissions reduces potential for accidental or malicious damage
2. **Better Compliance**: Follows principle of least privilege
3. **Clearer Intent**: Specific permissions document what Claude is expected to do
4. **Easier Auditing**: Can track exactly what operations are allowed
5. **Safer Development**: Prevents accidental system-wide changes or data loss
6. **Project Isolation**: Prevents cross-project interference
7. **Documentation**: Clear understanding of allowed operations

## Migration Path

For teams adopting these settings:

1. **Phase 1**: Deploy to development environments first
2. **Phase 2**: Monitor for needed permissions, add specifically
3. **Phase 3**: Deploy to staging after validation
4. **Phase 4**: Final deployment to production

## Troubleshooting

Common issues after implementing restricted settings:

1. **"Permission denied" errors**: Add specific command to allow list
2. **Build failures**: Check if build tools need specific arguments
3. **Test failures**: Ensure test runners have necessary permissions
4. **AWS operations blocked**: Verify operations are project-scoped

## Summary

The improved Claude settings provide:
- **Security**: Principle of least privilege implementation
- **Clarity**: Clear documentation of allowed operations
- **Safety**: Comprehensive deny rules as safety net
- **Maintainability**: Easier to audit and update

By following this guide, teams can significantly improve their Claude security posture while maintaining necessary functionality for development, testing, and deployment operations.