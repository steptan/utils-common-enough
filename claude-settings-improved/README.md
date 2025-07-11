# Claude Settings - Improved Security

This directory contains security-hardened Claude settings files for the media-register project.

## Files

- `media-register-settings.local.json` - Settings for the media-register project

## Key Security Improvements

1. **No Wildcards** - All permissions specify exact commands or limited patterns
2. **Explicit Deny Rules** - Dangerous operations are explicitly blocked
3. **Project Isolation** - Commands limited to project directories and resources
4. **Minimal Permissions** - Only necessary operations are allowed

## Usage

1. Back up existing settings files before replacing
2. Copy the appropriate file to your project's `.claude/settings.local.json`
3. Test Claude functionality after updating
4. Add specific permissions as needed (avoid wildcards)

## Permission Philosophy

- Start with minimal permissions
- Add only what's necessary for the task
- Be specific about allowed operations
- Use deny rules as a safety net
- Document why permissions are needed
