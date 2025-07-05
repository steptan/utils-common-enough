# CLAUDE.md and .claude/settings.local.json Analysis

## Overview

This document analyzes the CLAUDE.md project instructions and .claude/settings.local.json configuration files across all projects to identify patterns, best practices, and areas for improvement.

## Project Comparison Table

| Project                                  | CLAUDE.md Status          | Key Content                                                                                                                                                                                        | .claude/settings.local.json Status | Key Settings                                                                           | Missing/Needs Improvement                                                                  |
| ---------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **analysis**                             | ✅ Exists                 | - Multi-project analysis instructions<br>- Priorities (10/10 simplicity, 7/10 best practices)<br>- Git submodule guidance<br>- Local shell commands preference                                     | ✅ Exists                          | - Basic permissions<br>- Git operations allowed<br>- Python/bash allowed               | - No project-specific vocabulary<br>- No architecture details<br>- No development commands |
| **fraud-or-not**                         | ✅ Exists (comprehensive) | - Clear project overview & vocabulary<br>- Detailed features & qualities<br>- Complete architecture (AWS, Next.js)<br>- Development commands<br>- Anti-patterns<br>- L2/L3 implementation strategy | ✅ Exists                          | - Extensive permissions<br>- AWS operations<br>- Project scripts<br>- Testing commands | Well-documented, minimal gaps                                                              |
| **media-register**                       | ✅ Exists (comprehensive) | - Clear project overview & vocabulary<br>- User personas (Fred, Sally)<br>- Complete architecture (AWS, Next.js)<br>- Git submodule commands<br>- Similar structure to fraud-or-not                | ✅ Exists                          | - Similar to fraud-or-not<br>- Project-specific scripts<br>- AWS operations            | Well-documented, minimal gaps                                                              |
| **people-cards**                         | ✅ Exists (comprehensive) | - Clear vocabulary (hexagons, POIs)<br>- Interface design details<br>- Complete architecture<br>- AI integration plans<br>- Code style guidelines                                                  | ✅ Exists                          | - Similar permissions<br>- AWS operations<br>- Lambda bucket operations                | Well-documented, minimal gaps                                                              |
| **people-cards/utils**                   | ✅ Exists                 | - Project-utils overview<br>- Python-focused guidelines<br>- CLI patterns<br>- Development standards                                                                                               | ❌ Not needed                      | N/A                                                                                    | Appropriate for submodule                                                                  |
| **people-cards/utils/github-build-logs** | ❌ Missing                | N/A                                                                                                                                                                                                | ✅ Exists (minimal)                | Only ls permission                                                                     | Needs CLAUDE.md if active project                                                          |

## Key Findings

### 1. Common Patterns Across Projects

#### Architecture Consistency

All three main projects share:

- **Frontend**: Next.js 15.3.3+, React 19+, Tailwind 4.x+
- **Backend**: AWS stack (Lambda, DynamoDB, API Gateway, CloudFront, S3, Cognito)
- **Language**: TypeScript for frontend/backend/lambdas
- **Region**: us-west-1
- **CI/CD**: GitHub Actions with project-specific IAM users

#### Shared Best Practices

- L2/L3 construct patterns for infrastructure
- Anti-patterns to avoid (Hero Pattern, Fork & Forget, etc.)
- Static file preference with S3/CloudFront
- Utils submodule for shared scripts (Python-only)

#### Configuration Patterns

All settings.local.json files include:

- `includeCoAuthoredBy: false`
- Extensive bash permissions for AWS and development operations
- Project-specific script permissions

### 2. Unique Aspects by Project

#### fraud-or-not

- Lambda runs **outside VPC** for cost optimization (~$45/month savings)
- Focus on fraud rating system (danger level X-XXXXX, cost level $-$$$$$)
- Community-driven features

#### media-register

- Lambda runs **without VPC** for cost optimization and performance
- User personas documented (Fred, Sally)
- Focus on provenance and ownership proof

#### people-cards

- Lambda runs **inside VPC** (different from other projects)
- Hexagonal UI concept with complex navigation
- AI integration for political action analysis

### 3. Missing or Inconsistent Elements

#### Analysis Project

Missing in CLAUDE.md:

- No project-specific vocabulary section
- No development commands section (npm scripts)
- No architectural details
- No features/qualities section
- No anti-patterns section

#### All Projects

Could benefit from:

- Shared vocabulary/terminology across projects
- Consistent Lambda VPC strategy (currently mixed)
- Unified testing approach documentation
- Shared security best practices section

### 4. Best Practices to Apply Consistently

#### From Well-Documented Projects

1. **Structure**: Clear sections for Overview, Vocabulary, Features, Architecture, Development
2. **User Personas**: Document target users and their goals
3. **Anti-Patterns**: Explicitly state what to avoid
4. **Commands**: Include all relevant development commands
5. **Checklists**: Implementation phases with checkboxes

#### Security & Operations

1. Never hardcode credentials
2. Use IAM roles with least privilege
3. Tag all AWS resources
4. Cost optimization strategies
5. Rollback protection

## Recommendations

### 1. Standardize CLAUDE.md Structure

Create a template with these sections:

```markdown
# CLAUDE.md

## Project Overview

### Purpose

### Vocabulary

### Qualities

### Features

### User Personas (if applicable)

## Development Commands

### Local Shell Commands

### Application Commands

### Git Commands (if submodules)

## Application Architecture

### Frontend

### Backend

### CI/CD

### Deployment Stages

## Development Guidelines

### Best Practices

### Anti-Patterns

### Code Style

### Testing

## AWS-Specific Notes

### Cost Optimization

### Security

### Infrastructure Patterns
```

### 2. Unify Lambda VPC Strategy

- **Recommendation**: Use Lambda outside VPC for all projects unless specific VPC resources needed
- **Benefits**: ~$45/month savings per project, reduced cold starts
- **Action**: Update people-cards to match fraud-or-not and media-register

### 3. Create Shared Documentation

Add to utils repository:

- `SHARED-VOCABULARY.md` for common terms
- `AWS-BEST-PRACTICES.md` for consistent AWS patterns
- `TESTING-STANDARDS.md` for unified testing approach

### 4. Enhance Analysis Project Documentation

Update `/Users/sj/projects/analysis/CLAUDE.md` with:

- Project structure and purpose clarification
- Development commands
- How it relates to the three main projects

### 5. Settings.local.json Best Practices

- Keep permissions minimal and specific
- Group related permissions with comments
- Regularly audit and remove unused permissions
- Consider extracting common permissions to utils

## Implementation Priority

1. **High Priority**
   - Unify Lambda VPC configuration across projects
   - Update analysis project CLAUDE.md
   - Create shared vocabulary document

2. **Medium Priority**
   - Standardize CLAUDE.md structure with template
   - Extract common AWS patterns to utils
   - Document unified testing approach

3. **Low Priority**
   - Audit and optimize settings.local.json permissions
   - Create detailed user persona documentation
   - Add cost tracking/monitoring documentation
