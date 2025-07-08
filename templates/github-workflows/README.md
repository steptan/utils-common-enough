# GitHub Workflow Templates

This directory contains standardized GitHub Actions workflow templates with best practices for concurrency control, timeouts, and job configuration.

## Available Templates

### 1. pr-checks-template.yml
**Purpose**: Validate pull requests with comprehensive checks

**When to use**:
- For all pull requests to ensure code quality
- When you need automated PR feedback
- To enforce coding standards and security policies

**Key features**:
- Commit message validation
- Code quality checks (linting, formatting, type checking)
- Unit and integration tests with coverage
- Security scanning
- Build validation
- Automated PR comments with results

### 2. ci-cd-template.yml
**Purpose**: Continuous integration and deployment pipeline

**When to use**:
- For main branch deployments to staging
- For automated production deployments
- When you need a complete CI/CD pipeline

**Key features**:
- Build and test stages
- Security and quality checks
- Infrastructure validation
- Automated staging deployments
- Manual production deployments
- Deployment notifications

### 3. deploy-template.yml
**Purpose**: Production deployment with safety controls

**When to use**:
- For manual production deployments
- When you need deployment approvals
- For deployments requiring validation and rollback

**Key features**:
- Pre-flight validation
- Deployment windows enforcement
- Build artifact management
- Post-deployment validation
- Automated rollback capability
- Comprehensive notifications

### 4. scheduled-template.yml
**Purpose**: Recurring automated tasks

**When to use**:
- For daily/weekly/monthly automated tasks
- For data synchronization
- For cleanup and maintenance operations

**Key features**:
- Data synchronization
- Cleanup operations
- Backup procedures
- Report generation
- System maintenance
- Task summary notifications

## Concurrency Control Guide

### Basic Concurrency (CI/CD, PR Checks)
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```
- **Use for**: Most workflows where newer runs should replace older ones
- **Behavior**: Cancels in-progress runs when a new commit is pushed
- **Example**: PR checks, CI builds

### Deployment-Safe Concurrency
```yaml
concurrency:
  group: deploy-${{ inputs.environment }}
  cancel-in-progress: false
```
- **Use for**: Production deployments, critical operations
- **Behavior**: Queues deployments, never cancels in-progress ones
- **Example**: Production deployments, database migrations

### Scheduled Task Concurrency
```yaml
concurrency:
  group: scheduled-${{ github.workflow }}-${{ github.run_id }}
  cancel-in-progress: false
```
- **Use for**: Scheduled/cron jobs
- **Behavior**: Each run gets unique group, allows parallel execution
- **Example**: Daily backups, weekly reports

### PR/Issue Specific Concurrency
```yaml
concurrency:
  group: ${{ github.workflow }}-pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true
```
- **Use for**: PR-specific workflows
- **Behavior**: One run per PR at a time
- **Example**: PR checks, automated reviews

## Recommended Timeout Values

### Quick Operations (5-10 minutes)
- Linting and formatting checks
- Commit message validation
- Documentation checks
- API calls and notifications
- Permission checks

### Standard Operations (15-20 minutes)
- Unit tests
- Build processes
- Code coverage analysis
- Security scans
- Report generation

### Extended Operations (25-30 minutes)
- Integration tests
- Infrastructure deployment
- Database operations
- Data synchronization
- Multiple service deployments

### Special Cases
- **No timeout**: Use for workflows that must complete (with caution)
- **Extended timeout (45-60 minutes)**: Large deployments, data migrations

## Usage Examples

### Basic PR Checks
```yaml
name: PR Checks
on:
  pull_request:
    types: [opened, synchronize]

concurrency:
  group: pr-${{ github.head_ref }}
  cancel-in-progress: true

jobs:
  checks:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - run: npm test
```

### Safe Production Deployment
```yaml
name: Deploy Production
on:
  workflow_dispatch:

concurrency:
  group: deploy-production
  cancel-in-progress: false  # Never cancel deployments

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: production
    steps:
      - uses: actions/checkout@v4
      - run: ./deploy.sh
```

### Daily Scheduled Task
```yaml
name: Daily Cleanup
on:
  schedule:
    - cron: '0 2 * * *'

concurrency:
  group: cleanup-${{ github.run_id }}
  cancel-in-progress: false

jobs:
  cleanup:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - run: ./cleanup.sh
```

## Best Practices

### 1. Always Set Timeouts
- Prevents runaway jobs that consume resources
- Provides faster feedback on stuck jobs
- Saves money on GitHub Actions minutes

### 2. Choose Appropriate Concurrency
- Use `cancel-in-progress: true` for most workflows
- Use `cancel-in-progress: false` for deployments
- Consider unique groups for scheduled tasks

### 3. Environment Protection
- Use GitHub environments for production
- Require approvals for sensitive deployments
- Implement deployment windows

### 4. Artifact Management
- Set retention periods for artifacts
- Clean up old artifacts regularly
- Use appropriate storage classes

### 5. Notification Strategy
- Always notify on production deployments
- Use different channels for different severity
- Include relevant context in notifications

### 6. Security Considerations
- Never expose secrets in logs
- Use OIDC for cloud authentication when possible
- Regularly rotate credentials
- Implement least-privilege access

## Customization Guide

### Adding New Jobs
1. Copy the most similar template
2. Adjust timeout based on expected duration
3. Update concurrency group if needed
4. Add job-specific steps
5. Update documentation

### Modifying Timeouts
```yaml
# Job-level timeout (recommended)
jobs:
  my-job:
    timeout-minutes: 20

# Step-level timeout (optional)
    steps:
      - name: Long operation
        timeout-minutes: 15
        run: ./long-script.sh
```

### Environment Variables
```yaml
# Workflow-level (all jobs)
env:
  NODE_VERSION: '20.x'

# Job-level (single job)
jobs:
  build:
    env:
      BUILD_ENV: production

# Step-level (single step)
    steps:
      - run: npm build
        env:
          API_URL: ${{ secrets.API_URL }}
```

## Troubleshooting

### Workflow Timing Out
1. Check if timeout is appropriate for the operation
2. Look for stuck processes or infinite loops
3. Consider breaking up into smaller jobs
4. Add progress indicators for long operations

### Concurrency Conflicts
1. Verify concurrency group is correctly scoped
2. Check if cancel-in-progress is appropriate
3. Consider using different groups for different triggers
4. Review workflow triggers for conflicts

### Failed Deployments
1. Check pre-deployment validation
2. Verify environment secrets are set
3. Review deployment logs
4. Check post-deployment validation
5. Use rollback procedures if available

## Migration Guide

To migrate existing workflows to use these templates:

1. **Identify workflow type** (PR checks, CI/CD, deployment, scheduled)
2. **Copy appropriate template**
3. **Merge existing steps** into template structure
4. **Update environment variables** and secrets
5. **Test in a branch** before merging
6. **Monitor initial runs** for issues

## Contributing

When adding new templates:
1. Follow existing naming conventions
2. Include comprehensive documentation
3. Add timeout and concurrency controls
4. Provide usage examples
5. Update this README

## Support

For questions or issues with these templates:
1. Check the troubleshooting section
2. Review GitHub Actions documentation
3. Check workflow run logs
4. Open an issue in the utils repository