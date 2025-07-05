# Git Submodules Setup Script

## Overview

The `setup-git-submodules.sh` script provides centralized configuration for git submodules across all projects (fraud-or-not, media-register, people-cards). This replaces the individual `setup-git-submodules.sh` scripts in each project.

## Features

- Initializes and updates git submodules
- Configures utils submodule to track master branch
- Sets up helpful git aliases for submodule management
- Creates pre-push hooks to ensure submodules are committed and pushed
- Configures local git settings for better submodule handling

## Usage

### From Project Root

Run from your project root directory (e.g., fraud-or-not, media-register, or people-cards):

```bash
# From project root
./utils/setup-git-submodules.sh
```

### From Utils Directory

If you're already in the utils directory:

```bash
# Go back to parent project
cd ..
./utils/setup-git-submodules.sh
```

## Git Aliases Created

The script sets up these helpful aliases:

- `git sall` - Show status of parent repo and all submodules
- `git addall` - Add all changes in parent repo and submodules  
- `git pushall` - Commit and push parent repo and all submodules
- `git pullall` - Pull parent repo and update all submodules
- `git update-subs` - Pull and update all submodules
- `git push-all` - Push main repo and all submodules
- `git status-all` - Check status of main repo and submodules

## Pre-push Hook

The script creates a pre-push hook that:

1. Checks for uncommitted changes in submodules
2. Attempts to push unpushed commits in submodules
3. Prevents pushing if submodules have issues
4. Shows helpful error messages with commands to fix issues

## Migration from Individual Scripts

To migrate from individual project scripts:

1. Run the centralized setup script:
   ```bash
   ./utils/setup-git-submodules.sh
   ```

2. Remove the old script from your project:
   ```bash
   rm setup-git-submodules.sh
   ```

3. Commit the removal:
   ```bash
   git add -A
   git commit -m "Remove local setup-git-submodules.sh in favor of centralized version"
   ```

## Python Alternative

There's also a Python version available at `src/scripts/setup_git_submodules.py` with the same functionality:

```bash
python utils/src/scripts/setup_git_submodules.py
```

Both scripts provide the same functionality - use whichever you prefer.