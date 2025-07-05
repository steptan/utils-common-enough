# Deployment Patterns

This document describes the deployment patterns used by Project Utils across the three supported projects.

## Blue-Green Deployment Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer / CloudFront               │
└─────────────────────┬───────────────────┬───────────────────┘
                      │      100%         │      0%
              ┌───────▼────────┐  ┌──────▼────────┐
              │  Blue (Live)   │  │ Green (New)   │
              │  Environment   │  │ Environment   │
              └────────────────┘  └───────────────┘
                      │                   │
                      ▼                   ▼
              ┌────────────────┐  ┌───────────────┐
              │   Database     │  │   Database    │
              │   (Shared)     │  │   (Shared)    │
              └────────────────┘  └───────────────┘
```

### Implementation Steps

1. **Deploy to Green Environment**

   ```bash
   project-deploy deploy --project media-register --environment green
   ```

2. **Run Validation Tests**

   ```bash
   project-test smoke --project media-register --environment green
   ```

3. **Switch Traffic**

   ```bash
   project-deploy switch-traffic --project media-register --from blue --to green
   ```

4. **Monitor and Rollback if Needed**
   ```bash
   project-deploy rollback --project media-register --to blue
   ```

## Canary Deployment Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                         CloudFront                           │
└─────────────────────┬───────────────────┬───────────────────┘
                      │      90%          │      10%
              ┌───────▼────────┐  ┌──────▼────────┐
              │    Stable      │  │    Canary     │
              │    Version     │  │    Version    │
              └────────────────┘  └───────────────┘
                                          │
                                          ▼
                                  ┌───────────────┐
                                  │   Metrics     │
                                  │  Collection   │
                                  └───────────────┘
```

### Progressive Rollout

```python
# Canary deployment configuration
canary_config = {
    "stages": [
        {"traffic": 10, "duration": "10m", "metric_threshold": 0.01},
        {"traffic": 25, "duration": "30m", "metric_threshold": 0.05},
        {"traffic": 50, "duration": "1h", "metric_threshold": 0.05},
        {"traffic": 100, "duration": "stable", "metric_threshold": 0.05}
    ]
}
```

## Lambda Alias-Based Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
              ┌───────▼────────┐
              │  Lambda Alias  │
              │    (live)      │
              └───────┬────────┘
                      │ Weighted Routing
        ┌─────────────┼─────────────┐
        │ 90%         │        10%  │
┌───────▼────────┐  ┌─▼─────────────┐
│   Version 1    │  │   Version 2   │
│   (Stable)     │  │   (New)       │
└────────────────┘  └───────────────┘
```

### Deployment Commands

```bash
# Deploy new version
project-lambda deploy --project fraud-or-not --function api-handler

# Update alias weights
project-lambda update-alias --project fraud-or-not \
  --alias live \
  --version-weights "1:90,2:10"

# Promote to 100%
project-lambda promote --project fraud-or-not --alias live --version 2
```

## Multi-Region Deployment Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    Route 53 (Geolocation)                   │
└──────┬──────────────────┬────────────────────┬──────────────┘
       │ North America    │ Europe             │ Asia Pacific
┌──────▼───────┐  ┌──────▼───────┐  ┌────────▼────────┐
│  us-east-1   │  │  eu-west-1   │  │  ap-southeast-1 │
│  CloudFront  │  │  CloudFront  │  │   CloudFront    │
└──────┬───────┘  └──────┬───────┘  └────────┬────────┘
       │                 │                    │
┌──────▼───────┐  ┌──────▼───────┐  ┌────────▼────────┐
│   Regional   │  │   Regional   │  │    Regional     │
│   Resources  │  │   Resources  │  │    Resources    │
└──────────────┘  └──────────────┘  └─────────────────┘
```

### Cross-Region Replication

```yaml
replication_config:
  primary_region: us-east-1
  replica_regions:
    - region: eu-west-1
      replication_type: active-active
      latency_threshold: 100ms
    - region: ap-southeast-1
      replication_type: active-passive
      failover_priority: 2
```

## Feature Flag Deployment Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Code                         │
├─────────────────────────────────────────────────────────────┤
│  if (featureFlag.isEnabled("new-feature")) {               │
│      // New feature code                                    │
│  } else {                                                   │
│      // Existing code                                       │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               Feature Flag Service (SSM/AppConfig)          │
├─────────────────────────────────────────────────────────────┤
│  {                                                          │
│    "new-feature": {                                         │
│      "enabled": true,                                       │
│      "percentage": 50,                                      │
│      "allowlist": ["user1", "user2"]                       │
│    }                                                        │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

## Database Migration Pattern

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Schema     │────▶│   Migrate    │────▶│   Validate   │
│   Version 1  │     │   Data       │     │   Version 2  │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       ▼                     ▼                     ▼
   Read/Write          Dual Write             Read/Write
   Version 1          Both Versions           Version 2
```

### Migration Steps

1. **Dual Write Mode**
   - Application writes to both old and new schema
   - Ensures data consistency during migration

2. **Background Migration**
   - Migrate historical data
   - Validate data integrity

3. **Switch Primary**
   - Change application to read from new schema
   - Keep dual write for rollback capability

4. **Cleanup**
   - Remove old schema references
   - Archive old data

## Zero-Downtime Deployment Checklist

### Pre-Deployment

- [ ] Database migrations are backwards compatible
- [ ] API changes are backwards compatible
- [ ] Feature flags configured for new features
- [ ] Load tests completed
- [ ] Rollback plan documented

### During Deployment

- [ ] Health checks passing on new version
- [ ] Metrics within acceptable thresholds
- [ ] No increase in error rates
- [ ] Response times stable
- [ ] Database connections healthy

### Post-Deployment

- [ ] Remove feature flags for stable features
- [ ] Clean up old Lambda versions
- [ ] Update documentation
- [ ] Review deployment metrics
- [ ] Update runbooks

## Rollback Strategies

### Instant Rollback (Lambda Alias)

```bash
# Immediate rollback to previous version
project-lambda update-alias --project media-register \
  --alias live \
  --version $PREVIOUS_VERSION
```

### CloudFormation Stack Rollback

```bash
# Rollback to previous stack state
project-cfn rollback --stack-name media-register-prod \
  --rollback-triggers "ErrorRate>5%,Latency>1000ms"
```

### Database Rollback

```bash
# Restore from point-in-time backup
project-db restore --project people-cards \
  --environment prod \
  --restore-time "2024-01-20T10:00:00Z"
```

## Deployment Automation

### GitOps Pipeline

```yaml
on:
  push:
    branches: [main]

jobs:
  deploy:
    steps:
      - name: Deploy to Dev
        run: project-deploy full --project $PROJECT --environment dev

      - name: Run Tests
        run: project-test smoke --project $PROJECT --environment dev

      - name: Deploy to Staging
        if: success()
        run: project-deploy full --project $PROJECT --environment staging

      - name: Approval Gate
        uses: trstringer/manual-approval@v1

      - name: Deploy to Production
        if: success()
        run: project-deploy full --project $PROJECT --environment prod
```

### Monitoring Integration

```python
# Deployment monitoring
monitors = {
    "deployment_success_rate": {
        "metric": "DeploymentSuccess",
        "threshold": 0.95,
        "action": "alert"
    },
    "rollback_frequency": {
        "metric": "RollbackCount",
        "threshold": 2,
        "period": "1h",
        "action": "page"
    },
    "deployment_duration": {
        "metric": "DeploymentDuration",
        "threshold": 900,  # 15 minutes
        "action": "warn"
    }
}
```
