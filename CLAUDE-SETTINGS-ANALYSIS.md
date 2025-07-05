# Claude Settings Permissions Analysis

## Overview

This analysis compares the `.claude/settings.local.json` files across three projects:

- fraud-or-not
- media-register
- people-cards

## Common Permissions Across All Projects

### Allow Permissions (Common to All)

| Category              | Permission                                                           | Description                     |
| --------------------- | -------------------------------------------------------------------- | ------------------------------- |
| **Testing**           |                                                                      |                                 |
|                       | `Bash(pytest:*)`                                                     | Python test runner              |
|                       | `Bash(python -m pytest:*)`                                           | Python module test execution    |
|                       | `Bash(python3 -m pytest:*)`                                          | Python3 module test execution   |
|                       | `Bash(npm test:*)`                                                   | Node.js test runner             |
|                       | `Bash(npm run test:*)`                                               | Node.js script runner for tests |
|                       | `Bash(jest:*)`                                                       | JavaScript test framework       |
|                       | `Bash(npx jest:*)`                                                   | NPX Jest execution              |
| **Development Tools** |                                                                      |                                 |
|                       | `Bash(python:*)`                                                     | Python interpreter              |
|                       | `Bash(python3:*)`                                                    | Python3 interpreter             |
|                       | `Bash(node:*)`                                                       | Node.js runtime                 |
|                       | `Bash(npm:*)`                                                        | Node package manager            |
|                       | `Bash(npx:*)`                                                        | Node package executor           |
|                       | `Bash(pip install:*)`                                                | Python package installer        |
|                       | `Bash(pip3 install:*)`                                               | Python3 package installer       |
|                       | `Bash(pip3 list:*)`                                                  | List Python3 packages           |
| **Build & Deploy**    |                                                                      |                                 |
|                       | `Bash(make:*)`                                                       | Make build tool                 |
|                       | `Bash(./scripts/*.sh:*)`                                             | Shell scripts execution         |
|                       | `Bash(./scripts/*.py:*)`                                             | Python scripts execution        |
|                       | `Bash(AWS_REGION=us-west-1 ENVIRONMENT=staging python scripts/*.py)` | Staging deployment scripts      |
|                       | `Bash(project-utils:*)`                                              | Project utilities               |
|                       | `Bash(project-deploy:*)`                                             | Project deployment              |
|                       | `Bash(project-iam:*)`                                                | Project IAM management          |
| **AWS Operations**    |                                                                      |                                 |
|                       | `Bash(aws cloudformation:*)`                                         | CloudFormation commands         |
|                       | `Bash(aws s3:*)`                                                     | S3 operations                   |
|                       | `Bash(aws s3api:*)`                                                  | S3 API operations               |
|                       | `Bash(aws lambda:*)`                                                 | Lambda operations               |
|                       | `Bash(aws dynamodb:*)`                                               | DynamoDB operations             |
|                       | `Bash(aws cognito-idp:*)`                                            | Cognito identity provider       |
|                       | `Bash(aws iam list-*:*)`                                             | IAM list operations             |
|                       | `Bash(aws iam get-*:*)`                                              | IAM get operations              |
|                       | `Bash(aws iam attach-user-policy:*)`                                 | Attach IAM policies             |
|                       | `Bash(aws iam detach-user-policy:*)`                                 | Detach IAM policies             |
|                       | `Bash(aws iam create-policy-version:*)`                              | Create policy versions          |
| **Git Operations**    |                                                                      |                                 |
|                       | `Bash(git:*)`                                                        | Git version control             |
|                       | `Bash(gh:*)`                                                         | GitHub CLI                      |
| **File Operations**   |                                                                      |                                 |
|                       | `Bash(ls:*)`                                                         | List directory contents         |
|                       | `Bash(find:*)`                                                       | Find files                      |
|                       | `Bash(grep:*)`                                                       | Search text patterns            |
|                       | `Bash(rg:*)`                                                         | Ripgrep search                  |
|                       | `Bash(cat:*)`                                                        | Display file contents           |
|                       | `Bash(echo:*)`                                                       | Print text                      |
|                       | `Bash(touch:*)`                                                      | Create/update files             |
|                       | `Bash(mkdir:*)`                                                      | Create directories              |
|                       | `Bash(chmod:*)`                                                      | Change file permissions         |
|                       | `Bash(mv:*)`                                                         | Move/rename files               |
|                       | `Bash(rm:*)`                                                         | Remove files                    |
|                       | `Bash(sed:*)`                                                        | Stream editor                   |
|                       | `Bash(tree:*)`                                                       | Display directory tree          |
| **Environment**       |                                                                      |                                 |
|                       | `Bash(source:*)`                                                     | Source shell scripts            |
|                       | `Bash(brew install:*)`                                               | Homebrew package installer      |
|                       | `Bash(true)`                                                         | True command                    |

### Deny Permissions (Common to All)

| Category                       | Permission                           | Description                   |
| ------------------------------ | ------------------------------------ | ----------------------------- |
| **Dangerous Operations**       |                                      |                               |
|                                | `Bash(rm -rf /*)`                    | Prevent root deletion         |
|                                | `Bash(rm -rf ~/*)`                   | Prevent home deletion         |
|                                | `Bash(sudo:*)`                       | Prevent sudo usage            |
| **Sensitive Files**            |                                      |                               |
|                                | `Bash(*:~/.aws/*)`                   | Protect AWS credentials       |
|                                | `Bash(*:~/.ssh/*)`                   | Protect SSH keys              |
|                                | `Bash(*:.env*)`                      | Protect environment files     |
| **Destructive Git Operations** |                                      |                               |
|                                | `Bash(git push --force:*)`           | Prevent force push            |
|                                | `Bash(git reset --hard HEAD~*)`      | Prevent hard reset            |
| **Destructive AWS Operations** |                                      |                               |
|                                | `Bash(aws s3 rm s3://* --recursive)` | Prevent S3 recursive deletion |
|                                | `Bash(aws iam delete-*:*)`           | Prevent IAM deletions         |
|                                | `Bash(aws iam create-*:*)`           | Prevent IAM creations         |
|                                | `Bash(aws iam put-*:*)`              | Prevent IAM put operations    |

## Unique Permissions by Project

### fraud-or-not (Unique Permissions)

| Permission                                                                                                           | Description               |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `Bash(for lang in pt it nl sv no da)`                                                                                | Language loop command     |
| `Bash(do cp messages/en.json messages/$lang.json)`                                                                   | Copy language files       |
| `Bash(done)`                                                                                                         | Loop terminator           |
| `Bash(NODE_ENV=test npm test -- --testPathPattern=Comments.test.tsx --no-coverage 2 >& 1)`                           | Specific test execution   |
| `Bash(NODE_ENV=test npm test -- --testNamePattern=Comments --no-coverage 2 >& 1)`                                    | Test by name pattern      |
| `Bash(NODE_ENV=development npm test -- --testNamePattern=\"Comments.*should render comments\" --no-coverage 2 >& 1)` | Development test pattern  |
| `Bash(gh workflow view:*)`                                                                                           | GitHub workflow viewing   |
| `Bash(npm update:*)`                                                                                                 | NPM update command        |
| `Bash(gh secret set:*)`                                                                                              | GitHub secret management  |
| `Bash(find:*)`                                                                                                       | Duplicate find permission |

### media-register (Unique Permissions)

| Permission                          | Description           |
| ----------------------------------- | --------------------- |
| `Bash(./push-with-submodules.sh:*)` | Submodule push script |

### people-cards (Unique Permissions)

None - This project has the cleanest, most minimal permission set.

## Inconsistencies and Issues

### 1. Duplicate Permissions

- **fraud-or-not** has `Bash(find:*)` listed twice (lines 47 and 72)

### 2. Project-Specific Test Commands

- **fraud-or-not** has very specific test commands that should potentially be:
  - Moved to script files
  - Generalized as patterns
  - Or removed if they're one-time commands

### 3. Language-Specific Commands

- **fraud-or-not** has hardcoded language copying commands that appear to be one-time setup

### 4. Formatting Differences

- **people-cards** has better formatting with empty lines between sections
- Other projects lack this visual separation

## Recommendations

### 1. Create a Unified Base Configuration

Create a shared base configuration file that all projects can inherit from, containing the common permissions.

### 2. Remove Project-Specific One-Time Commands

Move these to documentation or setup scripts:

- Language copying commands in fraud-or-not
- Specific test execution commands

### 3. Fix Duplicate Entries

Remove the duplicate `find` permission in fraud-or-not.

### 4. Standardize Formatting

Apply the clean formatting from people-cards to all projects for better readability.

### 5. Consider Additional Common Permissions

Based on the projects' needs, consider adding:

- `Bash(npm run build:*)` - for build scripts
- `Bash(npm run dev:*)` - for development servers
- `Bash(aws logs:*)` - for CloudWatch logs access

### 6. Document Permission Rationale

Add comments explaining why certain unique permissions exist in specific projects.

### 7. Version Control Best Practices

Consider tracking a base `.claude/settings.json` in version control and using `.claude/settings.local.json` only for developer-specific overrides.

## Summary

The three projects share 95% of their permissions, with fraud-or-not having the most customizations. The main inconsistencies are:

- Duplicate entries
- One-time setup commands that shouldn't be permanent permissions
- Formatting differences

By consolidating to a shared base configuration and cleaning up project-specific anomalies, the team can maintain these settings more efficiently while ensuring consistent security policies across all projects.
