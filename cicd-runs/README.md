# CI/CD Auto-Fix Scripts

This directory contains scripts for automatically running CI/CD workflows and fixing issues using Claude AI.

## Scripts Overview

### 1. `github-actions-output-claude-auto-fix.sh`
**Purpose**: Monitor GitHub Actions runs and automatically fix failures by pushing to GitHub
- Monitors remote GitHub Actions runs
- Downloads failure logs when CI fails
- Sends logs to Claude for analysis and fixes
- **Pushes fixes to GitHub** to trigger new CI runs
- Runs continuously in a loop

### 2. `local-cicd-auto-fix.sh` ⭐ **NEW**
**Purpose**: Run GitHub Actions locally using ACT and fix issues with local commits only
- Runs GitHub workflows locally using [ACT](https://github.com/nektos/act)
- Analyzes failures with Claude AI
- **Commits fixes locally** (does NOT push to remote)
- Supports multiple iterations until CI passes
- Saves all logs to `logs/` directory

### 3. `act-fix-once.sh` ⭐ **NEW** 
**Purpose**: One-shot ACT run with Claude analysis
- Runs a single ACT job (test, build, etc.)
- If it fails, sends logs to Claude for analysis
- Commits any fixes locally
- Perfect for quick CI debugging

## Usage

### Quick Start (Recommended)

```bash
# Run a single test and fix issues
./act-fix-once.sh test

# Run build job and fix issues  
./act-fix-once.sh build

# Run with default job (test)
./act-fix-once.sh
```

### Continuous Local CI/CD Fixing

```bash
# Run with defaults (test job, 3 iterations max)
./local-cicd-auto-fix.sh

# Run build job with 5 iterations
./local-cicd-auto-fix.sh --job build --iterations 5

# Use different model and custom sleep time
./local-cicd-auto-fix.sh --model haiku --sleep 600
```

### GitHub Actions Monitoring (Original)

```bash
# Monitor GitHub Actions continuously
./github-actions-output-claude-auto-fix.sh

# Set custom monitoring interval
SLEEP_BETWEEN=300 ./github-actions-output-claude-auto-fix.sh
```

## Prerequisites

### Required Tools

1. **ACT** - For running GitHub Actions locally
   ```bash
   # macOS
   brew install act
   
   # Other platforms: https://github.com/nektos/act
   ```

2. **Claude CLI** - For AI-powered analysis
   ```bash
   # Install from: https://claude.ai/code
   ```

3. **GitHub CLI** (for original script only)
   ```bash
   brew install gh
   gh auth login
   ```

### Project Setup

1. **ACT Configuration**: Ensure your project has proper `.actrc` and workflow files
2. **Docker**: ACT requires Docker to run workflows
3. **Git Repository**: Must be run from within a git repository

## Configuration

### Environment Variables

```bash
# Model selection
export MODEL=sonnet          # Default
export MODEL=haiku          # Faster, less capable
export MODEL=opus           # More capable, slower

# Local CI/CD settings
export ACT_JOB=test         # Default job to run
export MAX_ITERATIONS=3     # Maximum fix attempts
export SLEEP_BETWEEN=300    # Seconds between iterations

# Safety settings  
export NO_DANGEROUS=1       # Disable auto-permissions for Claude
```

### Command Line Options

```bash
# local-cicd-auto-fix.sh options
--job JOB               # ACT job to run (test, build, etc.)
--model MODEL           # Claude model (sonnet, haiku, opus)
--iterations N          # Maximum iterations (default: 3)
--sleep SECONDS         # Sleep between iterations (default: 300)
--no-dangerous          # Disable dangerous permissions
--help                  # Show help message
```

## Output Files

All logs and responses are saved to `logs/` directory:

```
logs/
├── act-test-people-cards-20240101-120000.log        # ACT output
├── claude-response-people-cards-20240101-120000.txt # Claude analysis
├── act-output-people-cards-iteration-1.log          # Multi-iteration logs
└── claude-response-people-cards-iteration-1.txt     # Multi-iteration responses
```

## How It Works

### Local CI/CD Process

1. **ACT Execution**: Runs GitHub workflows locally using Docker containers
2. **Log Capture**: Captures all output (stdout/stderr) to log files
3. **Failure Analysis**: If ACT fails, sends logs to Claude for analysis
4. **Auto-Fix**: Claude analyzes errors and implements fixes
5. **Local Commit**: Changes are committed locally with descriptive messages
6. **Iteration**: Process repeats until CI passes or max iterations reached

### Benefits of Local Approach

- ✅ **Faster feedback** - No waiting for GitHub runners
- ✅ **No CI/CD quota usage** - Runs entirely locally
- ✅ **Better control** - Review commits before pushing
- ✅ **Offline capable** - Works without internet (except Claude API)
- ✅ **Cost effective** - No GitHub Actions minutes consumed

## Example Workflow

```bash
# 1. Start with failing tests
./act-fix-once.sh test
# ❌ ACT job failed. Analyzing with Claude...
# 📝 Committing Claude's fixes...
# ✅ Changes committed successfully

# 2. Run again to verify fixes
./act-fix-once.sh test  
# ✅ ACT job passed! No fixes needed.

# 3. Push when ready
git push origin main
```

## Troubleshooting

### Common Issues

1. **ACT fails to start**
   - Ensure Docker is running
   - Check `.actrc` configuration
   - Verify workflow files exist

2. **Claude doesn't make changes**
   - Check if the issue requires manual intervention
   - Try different Claude model
   - Review the logs for environment-specific issues

3. **Permission errors**
   - Use `--no-dangerous` flag for safer operation
   - Review Claude's suggested commands before applying

### Debug Mode

```bash
# Enable verbose output
export DEBUG=1
./local-cicd-auto-fix.sh --job test

# Check ACT directly
act --list                    # List available workflows
act -j test --dry-run        # Dry run to check configuration
```

## Safety Notes

- ⚠️ **Local commits only**: Scripts commit locally but never push automatically
- ⚠️ **Review changes**: Always review Claude's changes before pushing
- ⚠️ **Backup work**: Ensure your work is backed up before running
- ⚠️ **Dangerous mode**: `--dangerously-skip-permissions` bypasses Claude safety checks

## Contributing

When adding new scripts:

1. Follow the existing naming convention
2. Include comprehensive help text
3. Support both CLI args and environment variables
4. Save all outputs to `logs/` directory
5. Update this README with usage examples