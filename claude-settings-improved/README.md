# Claude Settings Improved - Hybrid Security Approach

<<<<<<< HEAD
This directory contains security-hardened Claude settings files for the media-register project.

## Files

- `media-register-settings.local.json` - Settings for the media-register project
=======
This directory contains improved Claude settings that balance security with usability using a hybrid approach.

## Philosophy

Instead of removing all wildcards (which makes files very long), we use a **hybrid approach**:
- ✅ Keep wildcards for safe read operations (`ls:*`, `cat:*`, `grep:*`)
- ✅ Keep wildcards for safe dev tools (`npm test:*`, `jest:*`)
- 🔒 Be specific for dangerous operations (no `rm:*`, `python:*`)
- 🔒 Scope operations to project directories and resources

## Files

### Settings Files (Hybrid Approach)
- `fraud-or-not-settings-hybrid.local.json` - Fraud detection project settings
- `media-register-settings-hybrid.local.json` - Media registration with submodule support
- `people-cards-settings-hybrid.local.json` - People cards project settings
- `github-build-logs-settings-hybrid.local.json` - CI/CD monitoring tool settings

### Scripts
- `deploy-improved-settings.sh` - Deploy improved settings to all projects
- `rollback-settings.sh` - Rollback to original settings if needed

### Original Strict Settings (Reference)
- `fraud-or-not-settings.local.json` - Fully explicit permissions (no wildcards)
- `media-register-settings.local.json` - Fully explicit permissions
- `people-cards-settings.local.json` - Fully explicit permissions
>>>>>>> 489ac89c83ce8b93df96fa009f6c582146ba8a05

## Key Security Improvements

### 1. Project-Scoped AWS Operations
```json
"Bash(aws s3:* s3://fraud-or-not-*)",  // Only project buckets
"Bash(aws cloudformation:* --stack-name fraud-or-not-*)",  // Only project stacks
```

### 2. Directory-Scoped File Operations
```json
"Bash(rm ./dist/*)",  // Can only delete in specific directories
"Bash(python ./scripts/*.py)",  // Can only run project scripts
```

### 3. Comprehensive Deny Rules
- System modifications blocked (`sudo`, `brew`, `apt-get`)
- Credential access blocked (`~/.aws/*`, `~/.ssh/*`)
- Destructive operations blocked (`rm -rf`, `git push --force`)
- Cross-project access blocked

### 4. Safe Wildcards Retained
- Read operations: `ls:*`, `cat:*`, `grep:*`
- Git info: `git log:*`, `git diff:*`, `git status`
- Testing: `npm test:*`, `jest:*`

## Usage

### Deploy Improved Settings
```bash
./deploy-improved-settings.sh
```

### Rollback if Needed
```bash
./rollback-settings.sh
```

### Test After Deployment
1. Try running tests: `npm test`
2. Try building: `npm run build`
3. Try Git operations: `git status`, `git diff`
4. Try AWS operations: `aws s3 ls s3://project-name-*`

### Adding New Permissions
If Claude needs a permission that's blocked:
1. Add the SPECIFIC command needed (avoid wildcards)
2. Document why it's needed
3. Consider if a corresponding deny rule should be added

## Security Benefits

1. **Reduced Attack Surface**: Can't run arbitrary scripts or access system files
2. **Project Isolation**: Can't accidentally affect other projects
3. **Accident Prevention**: Can't run destructive commands by mistake
4. **Audit Trail**: Clear documentation of what operations are allowed
5. **Balanced Usability**: Common operations still work smoothly with safe wildcards

## Maintenance

- Review settings quarterly
- Remove permissions for deprecated features
- Add new permissions as specifically as possible
- Keep deny rules updated with new dangerous patterns