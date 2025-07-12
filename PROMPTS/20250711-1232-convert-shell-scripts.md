# Convert Shell Scripts to Python - Critical CLAUDE.md Compliance

**Created**: 2025-07-11 12:32
**Priority**: CRITICAL - BLOCKING
**Status**: Pending

## Problem Statement

The utils project has shell scripts that directly violate CLAUDE.md standards:
- **3 shell scripts** found in utils directory that should be Python
- **setup-git-submodules.sh** in root directory
- **Shell scripts in claude-settings-improved/** directory
- Violation of CLAUDE.md rule: "ALL Python scripts MUST be in utils, NOT in individual projects"

These violations are **BLOCKING** per CLAUDE.md: "CRITICAL: Python Script Location Rule - ALL Python scripts MUST be in utils, NOT in individual projects: Convert all shell scripts to Python and place in utils"

## Research → Plan → Implement Workflow

### 1. Research Phase
First, identify all shell scripts and understand their functionality:

```bash
cd /Users/sj/projects/analysis/utils

# Find all shell scripts in utils
find . -name "*.sh" -type f

# Analyze each shell script's functionality
echo "=== setup-git-submodules.sh ===" 
cat setup-git-submodules.sh

echo "=== claude-settings-improved scripts ==="
ls -la claude-settings-improved/*.sh
cat claude-settings-improved/deploy-improved-settings.sh
cat claude-settings-improved/rollback-settings.sh

# Check if any other projects have shell scripts that should be here
find /Users/sj/projects/analysis/ -name "*.sh" -not -path "*/utils/*" -type f
```

### 2. Plan Phase
Convert each shell script to Python following CLAUDE.md standards:

**Scripts to Convert:**

1. **setup-git-submodules.sh** → `src/scripts/setup_git_submodules.py`
   - Convert to Python with proper error handling
   - Add type annotations
   - Include proper logging
   - Add to CLI interface

2. **claude-settings-improved/deploy-improved-settings.sh** → `src/scripts/deploy_claude_settings.py`
   - Convert file operations to Python
   - Add validation and rollback capabilities
   - Include proper error handling

3. **claude-settings-improved/rollback-settings.sh** → `src/scripts/rollback_claude_settings.py`
   - Convert to Python with safety checks
   - Add logging and confirmation prompts
   - Include backup verification

**Python Conversion Standards:**
- Use `pathlib` instead of shell path operations
- Use `subprocess` for external command execution
- Add comprehensive error handling with try/except
- Include type annotations for all functions
- Add docstrings following Google style
- Create CLI entry points in `src/cli/`

### 3. Implementation Commands

Execute these commands in sequence:

```bash
# Step 1: Create the Python script replacements
cd /Users/sj/projects/analysis/utils

# Convert setup-git-submodules.sh
cat > src/scripts/setup_git_submodules.py << 'EOF'
#!/usr/bin/env python3
"""
Git submodules setup script - Python replacement for setup-git-submodules.sh
Follows CLAUDE.md standards for Python scripts in utils.
"""
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

def setup_git_submodules(project_path: Path) -> bool:
    """Set up git submodules for a project."""
    # Implementation here following shell script logic
    pass

if __name__ == "__main__":
    # CLI interface
    pass
EOF

# Convert deploy-improved-settings.sh  
cat > src/scripts/deploy_claude_settings.py << 'EOF'
#!/usr/bin/env python3
"""
Claude settings deployment script - Python replacement for deploy-improved-settings.sh
Follows CLAUDE.md standards for Python scripts in utils.
"""
import shutil
from pathlib import Path
from typing import Dict, List

def deploy_claude_settings(target_projects: List[str]) -> bool:
    """Deploy improved Claude settings to target projects."""
    # Implementation here following shell script logic
    pass

if __name__ == "__main__":
    # CLI interface
    pass
EOF

# Convert rollback-settings.sh
cat > src/scripts/rollback_claude_settings.py << 'EOF'  
#!/usr/bin/env python3
"""
Claude settings rollback script - Python replacement for rollback-settings.sh
Follows CLAUDE.md standards for Python scripts in utils.
"""
import shutil
from pathlib import Path
from typing import Optional

def rollback_claude_settings(backup_path: Optional[Path] = None) -> bool:
    """Rollback Claude settings from backup."""
    # Implementation here following shell script logic
    pass

if __name__ == "__main__":
    # CLI interface
    pass
EOF

# Step 2: Add CLI commands for these scripts
cat >> src/cli/__main__.py << 'EOF'

# Add new commands for converted scripts
@click.command()
@click.argument('project_path', type=click.Path(exists=True))
def setup_submodules(project_path: str) -> None:
    """Set up git submodules for a project."""
    from ..scripts.setup_git_submodules import setup_git_submodules
    success = setup_git_submodules(Path(project_path))
    if success:
        click.echo("✅ Git submodules setup completed")
    else:
        click.echo("❌ Git submodules setup failed")
        sys.exit(1)

@click.command()  
@click.option('--projects', multiple=True, help='Target projects for settings deployment')
def deploy_settings(projects: List[str]) -> None:
    """Deploy Claude settings to projects."""
    from ..scripts.deploy_claude_settings import deploy_claude_settings
    success = deploy_claude_settings(list(projects))
    if success:
        click.echo("✅ Claude settings deployed")
    else:
        click.echo("❌ Claude settings deployment failed")
        sys.exit(1)

@click.command()
@click.option('--backup-path', type=click.Path(), help='Path to backup directory')
def rollback_settings(backup_path: Optional[str]) -> None:
    """Rollback Claude settings from backup."""
    from ..scripts.rollback_claude_settings import rollback_claude_settings
    backup = Path(backup_path) if backup_path else None
    success = rollback_claude_settings(backup)
    if success:
        click.echo("✅ Claude settings rolled back")
    else:
        click.echo("❌ Claude settings rollback failed")
        sys.exit(1)

# Register commands
cli.add_command(setup_submodules)
cli.add_command(deploy_settings)
cli.add_command(rollback_settings)
EOF

# Step 3: Implement the actual Python logic (detailed implementation needed)
# This requires analyzing each shell script and converting logic

# Step 4: Remove shell scripts after Python versions are tested
# rm setup-git-submodules.sh
# rm claude-settings-improved/deploy-improved-settings.sh
# rm claude-settings-improved/rollback-settings.sh

# Step 5: Update documentation and references
grep -r "setup-git-submodules.sh" . --exclude-dir=.git
grep -r "deploy-improved-settings.sh" . --exclude-dir=.git  
grep -r "rollback-settings.sh" . --exclude-dir=.git
```

### 4. Detailed Python Implementation Requirements

Each converted script must include:

```python
# ✅ ALWAYS: Proper imports and type annotations
from pathlib import Path
from typing import List, Optional, Dict, Union
import subprocess
import logging

# ✅ ALWAYS: Comprehensive error handling  
def safe_operation() -> bool:
    """Execute operation with proper error handling."""
    try:
        # Operation logic
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e}")
        return False
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False

# ✅ ALWAYS: Validation functions
def validate_inputs(path: Path) -> bool:
    """Validate input parameters."""
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    return True

# ✅ ALWAYS: Logging and progress reporting
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

## Validation Steps

After implementation, verify CLAUDE.md compliance:

```bash
# Test all converted Python scripts
python -m src.scripts.setup_git_submodules --help
python -m src.scripts.deploy_claude_settings --help  
python -m src.scripts.rollback_claude_settings --help

# Verify CLI integration
python -m src.cli setup-submodules --help
python -m src.cli deploy-settings --help
python -m src.cli rollback-settings --help

# Run Python quality checks on new scripts
mypy src/scripts/
black src/scripts/ --check
isort src/scripts/ --check
flake8 src/scripts/

# Test functionality matches original shell scripts
# (Test each converted script with sample data)

# Verify no shell scripts remain (except in templates)
find . -name "*.sh" -not -path "./templates/*" | wc -l  # Should be 0
```

## Expected Outcomes

After completion:
- **0 shell scripts** in utils (except templates)
- **3 new Python modules** in `src/scripts/`
- **CLI commands** for all converted functionality
- **Type-annotated, tested Python code** following CLAUDE.md standards
- **Comprehensive error handling** and logging
- **Updated documentation** referencing Python commands

## Cross-Project Impact

Check other projects for shell scripts that should be moved to utils:
1. **fraud-or-not**: Search for any .sh files that should be in utils
2. **media-register**: Search for any .sh files that should be in utils  
3. **people-cards**: Search for any .sh files that should be in utils
4. **Update all documentation** to reference Python commands instead of shell scripts

## Critical Note

This conversion is **MANDATORY** per CLAUDE.md standards. No shell scripts should remain in the utils project except for template examples. All deployment, CI/CD, and infrastructure scripts must be Python-based and located in the utils project.