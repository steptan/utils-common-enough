# Claude Settings Implementation Guide

## Summary of Changes

### Key Security Improvements

1. **Removed Wildcard Permissions**
   - Replaced `python:*`, `node:*`, `npm:*`, `git:*` with specific allowed commands
   - Limited AWS operations to project-specific resources
   - Restricted file operations to project directories

2. **Added Explicit Deny Rules**
   - Block dangerous file operations (rm -rf, chmod 777)
   - Prevent system-wide changes (brew, apt-get, sudo)
   - Restrict access to sensitive files (.env, ~/.aws, ~/.ssh)
   - Prevent dangerous git operations (force push, hard reset)
   - Block AWS account-wide operations

3. **Made Permissions Project-Specific**
   - AWS stack names must match project prefix (fraud-or-not-*, media-register-*, people-cards-*)
   - S3 operations limited to project-specific buckets
   - Scripts limited to project's ./scripts directory

4. **Removed Unnecessary Permissions**
   - Removed duplicate entries
   - Removed unused commands (e.g., sed, source, cat for general use)
   - Removed system package installation (brew install)

## Implementation Steps

### 1. Backup Current Settings
```bash
# For each project, backup the current settings
cp /Users/sj/projects/fraud-or-not/.claude/settings.local.json /Users/sj/projects/fraud-or-not/.claude/settings.local.json.backup
cp /Users/sj/projects/media-register/.claude/settings.local.json /Users/sj/projects/media-register/.claude/settings.local.json.backup
cp /Users/sj/projects/people-cards/.claude/settings.local.json /Users/sj/projects/people-cards/.claude/settings.local.json.backup
cp /Users/sj/projects/people-cards/utils/github-build-logs/.claude/settings.local.json /Users/sj/projects/people-cards/utils/github-build-logs/.claude/settings.local.json.backup
```

### 2. Copy New Settings Files
```bash
# Copy the improved settings to each project
cp /Users/sj/projects/utils/claude-settings-improved/fraud-or-not-settings.local.json /Users/sj/projects/fraud-or-not/.claude/settings.local.json
cp /Users/sj/projects/utils/claude-settings-improved/media-register-settings.local.json /Users/sj/projects/media-register/.claude/settings.local.json
cp /Users/sj/projects/utils/claude-settings-improved/people-cards-settings.local.json /Users/sj/projects/people-cards/.claude/settings.local.json
cp /Users/sj/projects/utils/claude-settings-improved/github-build-logs-settings.local.json /Users/sj/projects/people-cards/utils/github-build-logs/.claude/settings.local.json
```

### 3. Test Claude Functionality
After updating settings, test that Claude can still:
- Run build scripts
- Execute tests
- Deploy to staging
- Perform necessary git operations
- Access required AWS resources

### 4. Adjust as Needed
If Claude needs additional permissions:
1. Add specific commands to the allow list (avoid wildcards)
2. Document why the permission is needed
3. Consider if a deny rule should also be added to prevent misuse

## Ongoing Maintenance

### Regular Reviews
- Review settings quarterly
- After adding new functionality, check if permissions need updating
- Remove permissions for deprecated features

### Permission Request Guidelines
When Claude requests a new permission:
1. Verify it's necessary for the task
2. Make it as specific as possible
3. Add to allow list only if truly needed
4. Consider adding related deny rules

### Security Best Practices
1. Never use wildcards unless absolutely necessary
2. Always specify full command paths for scripts
3. Limit AWS operations to specific resources
4. Regularly audit what permissions are actually used
5. Keep deny rules updated with new dangerous patterns

## Benefits of These Changes

1. **Reduced Attack Surface**: Limiting permissions reduces potential for accidental or malicious damage
2. **Better Compliance**: Follows principle of least privilege
3. **Clearer Intent**: Specific permissions document what Claude is expected to do
4. **Easier Auditing**: Can track exactly what operations are allowed
5. **Safer Development**: Prevents accidental system-wide changes or data loss

## Notes

- The improved settings are more verbose but much more secure
- Some legitimate operations may initially be blocked - add them specifically as needed
- The deny rules act as a safety net even if allow rules are too broad
- Consider using environment-specific settings files for production vs development