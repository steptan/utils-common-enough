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

### 4. deploy-blue-green-template.yml
**Purpose**: Advanced blue-green deployment with automated rollback

**When to use**:
- For zero-downtime production deployments
- When you need instant rollback capabilities
- For high-traffic applications requiring safety
- When you want traffic shifting strategies

**Key features**:
- Blue-green deployment with Lambda aliases
- Canary deployment option with gradual traffic shift
- Automated health checks and monitoring
- Error threshold-based automatic rollback
- Traffic shifting strategies (blue-green, canary, all-at-once)
- Emergency manual rollback workflow
- CloudWatch metrics monitoring
- Version cleanup and management

### 5. canary-deployment-template.yml
**Purpose**: Progressive canary deployment for staging environments

**When to use**:
- For testing new versions with real traffic
- When you want gradual rollout in staging
- For catching issues before full deployment
- When you need detailed metrics comparison

**Key features**:
- Configurable traffic shifting (5%, 10%, 25% initial)
- Progressive traffic increases with bake time
- Baseline metrics collection
- Real-time error and latency monitoring
- Automatic rollback on threshold breach
- Detailed deployment notifications

### 6. scheduled-template.yml
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

## Deployment Strategies

### Blue-Green Deployment
**How it works**:
1. Deploy new version to "green" environment
2. Run health checks on green environment
3. Switch all traffic instantly from "blue" to "green"
4. Keep blue environment as instant rollback option

**Best for**:
- Production deployments requiring zero downtime
- Applications with strict SLAs
- When instant rollback is critical

**Configuration**:
```yaml
deployment_strategy: blue-green
auto_rollback: true
error_threshold: 5  # Percentage
```

### Canary Deployment
**How it works**:
1. Deploy new version alongside current version
2. Route small percentage of traffic to new version
3. Monitor metrics and gradually increase traffic
4. Rollback automatically if thresholds exceeded

**Best for**:
- Testing with real production traffic
- Gradual rollouts to minimize risk
- Detecting issues early with minimal impact

**Configuration**:
```yaml
deployment_strategy: canary
initial_percentage: 10
increment_percentage: 20
bake_time: 10  # minutes
error_threshold: 5  # percentage
latency_threshold: 1000  # milliseconds
```

### All-at-Once Deployment
**How it works**:
1. Deploy new version
2. Switch all traffic immediately
3. Monitor for issues

**Best for**:
- Development environments
- Low-risk changes
- Emergency fixes

## Rollback Capabilities

### Automatic Rollback
Triggers when:
- Error rate exceeds threshold (default: 5%)
- Latency exceeds threshold (default: 2000ms)
- Health checks fail
- Deployment validation fails

### Manual Rollback
Two options:
1. **Emergency rollback**: Specify exact version to rollback to
2. **Standard rollback**: Revert to previous stable version

### Rollback Process
1. Revert Lambda alias to previous version
2. Clear weighted routing configurations
3. Restore previous static assets (if versioned)
4. Verify rollback with health checks
5. Send notifications

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

### Blue-Green Deployment
```yaml
name: Blue-Green Deploy
on:
  workflow_dispatch:
    inputs:
      deployment_strategy:
        type: choice
        options: [blue-green, canary]
        default: blue-green

jobs:
  deploy:
    uses: ./.github/workflows/deploy-blue-green-template.yml
    with:
      environment: production
      deployment_strategy: ${{ inputs.deployment_strategy }}
    secrets: inherit
```

### Canary Deployment
```yaml
name: Canary Release
on:
  workflow_dispatch:

jobs:
  canary:
    uses: ./.github/workflows/canary-deployment-template.yml
    with:
      environment: staging
      initial_percentage: '10'
      increment_percentage: '20'
      bake_time: '10'
    secrets: inherit
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

### 7. Deployment Best Practices
- Always test in staging before production
- Use blue-green for critical production deployments
- Start canary deployments with small percentages
- Monitor key metrics during deployments
- Have rollback plans ready
- Document deployment procedures

### 8. Monitoring During Deployment
- Error rates and counts
- Response latency (p50, p95, p99)
- Success rates
- Resource utilization
- Custom application metrics

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