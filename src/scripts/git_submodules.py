#!/usr/bin/env python3
"""
Git submodule management utilities.

Replaces setup-git-submodules.sh with Python implementation.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional


class GitSubmoduleManager:
    """Manages git submodule operations."""
    
    def __init__(self, repo_path: Path = Path.cwd()):
        self.repo_path = repo_path
        self.git_dir = repo_path / '.git'
        self.hooks_dir = self.git_dir / 'hooks' if self.git_dir.exists() else None
        
    def setup_pre_push_hook(self) -> bool:
        """Create pre-push hook for submodule checking."""
        if not self.hooks_dir or not self.hooks_dir.exists():
            print("Warning: .git/hooks directory not found")
            return False
            
        hook_content = '''#!/usr/bin/env python3
import subprocess
import sys
import os

RED = '\\033[0;31m'
GREEN = '\\033[0;32m'
YELLOW = '\\033[1;33m'
NC = '\\033[0m'  # No Color

def check_submodules():
    """Check if submodules have uncommitted or unpushed changes."""
    print("Checking submodules...")
    
    # Check if there are any submodules
    if not os.path.exists('.gitmodules'):
        return True
        
    # Get list of submodules
    result = subprocess.run(
        ['git', 'config', '--file', '.gitmodules', '--get-regexp', 'path'],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        return True
        
    submodules = [line.split()[1] for line in result.stdout.strip().split('\\n') if line]
    
    for submodule in submodules:
        print(f"Checking submodule: {submodule}")
        
        if not os.path.exists(submodule):
            continue
            
        # Save current directory
        original_dir = os.getcwd()
        os.chdir(submodule)
        
        try:
            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'diff-index', '--quiet', 'HEAD', '--'],
                capture_output=True
            )
            
            if result.returncode != 0:
                print(f"{RED}Error: Submodule '{submodule}' has uncommitted changes{NC}")
                print("Please commit changes in the submodule first:")
                print(f"  cd {submodule}")
                print("  git add -A && git commit -m 'Your commit message'")
                return False
                
            # Check for unpushed commits
            result = subprocess.run(
                ['git', 'log', '@{u}..'],
                capture_output=True, text=True
            )
            
            if result.stdout.strip():
                print(f"{YELLOW}Warning: Submodule '{submodule}' has unpushed commits{NC}")
                print("Attempting to push submodule changes...")
                
                # Try to push submodule
                result = subprocess.run(['git', 'push'])
                if result.returncode != 0:
                    print(f"{RED}Failed to push submodule '{submodule}'{NC}")
                    print("Please push the submodule manually:")
                    print(f"  cd {submodule}")
                    print("  git push")
                    return False
                    
                print(f"{GREEN}Successfully pushed submodule '{submodule}'{NC}")
                
        finally:
            os.chdir(original_dir)
            
    print(f"{GREEN}Submodule check complete{NC}")
    return True

if __name__ == '__main__':
    if not check_submodules():
        sys.exit(1)
    sys.exit(0)
'''
        
        hook_path = self.hooks_dir / 'pre-push'
        hook_path.write_text(hook_content)
        hook_path.chmod(0o755)
        
        print(f"✅ Created pre-push hook at {hook_path}")
        return True
        
    def setup_git_aliases(self) -> bool:
        """Set up helpful git aliases for submodule management."""
        aliases = {
            'pushall': '!f() { echo "Checking for submodule changes..."; git submodule foreach "git add -A && git diff-index --quiet HEAD -- || git commit -m \\"Auto-commit from parent repo\\" && git push || true"; echo "Committing parent repository..."; git add -A && git commit -m "$1" && git push; }; f',
            'sall': '!git status && echo "" && git submodule foreach "echo \\"Submodule: $path\\" && git status -s && echo"',
            'pullall': '!git pull && git submodule update --remote --merge',
            'addall': '!git submodule foreach "git add -A" && git add -A'
        }
        
        for alias, command in aliases.items():
            try:
                subprocess.run(
                    ['git', 'config', '--local', f'alias.{alias}', command],
                    check=True,
                    cwd=self.repo_path
                )
                print(f"✅ Set up git alias: {alias}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to set up alias {alias}: {e}")
                return False
                
        return True
        
    def configure_submodule(self, submodule_path: str = "utils", branch: str = "master") -> bool:
        """Configure submodule to track branch and use merge strategy."""
        try:
            subprocess.run(
                ['git', 'config', '--file', '.gitmodules', f'submodule.{submodule_path}.branch', branch],
                check=True,
                cwd=self.repo_path
            )
            subprocess.run(
                ['git', 'config', '--file', '.gitmodules', f'submodule.{submodule_path}.update', 'merge'],
                check=True,
                cwd=self.repo_path
            )
            print(f"✅ Configured submodule {submodule_path} to track {branch} with merge strategy")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to configure submodule: {e}")
            return False
            
    def push_with_submodules(self, commit_message: str) -> bool:
        """Push changes including submodule updates."""
        try:
            # First, check if there are changes in the submodule
            submodule_path = self.repo_path / 'utils'
            if submodule_path.exists():
                # Check for changes in submodule
                result = subprocess.run(
                    ['git', 'status', '--porcelain'],
                    capture_output=True,
                    text=True,
                    cwd=submodule_path
                )
                
                if result.stdout.strip():
                    print("📦 Found changes in utils submodule")
                    subprocess.run(['git', 'add', '-A'], check=True, cwd=submodule_path)
                    subprocess.run(
                        ['git', 'commit', '-m', 'chore: update from media-register'],
                        cwd=submodule_path
                    )
                    subprocess.run(['git', 'push', 'origin', 'master'], check=True, cwd=submodule_path)
                    
            # Now handle the main repository
            print("📄 Updating main repository...")
            subprocess.run(['git', 'add', '-A'], check=True, cwd=self.repo_path)
            
            # Check if there are changes to commit
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                cwd=self.repo_path
            )
            
            if result.stdout.strip():
                subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=self.repo_path)
                
            # Push main repository
            subprocess.run(['git', 'push', 'origin', 'main'], check=True, cwd=self.repo_path)
            
            print("✅ Successfully pushed main repository and submodules!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Push failed: {e}")
            return False
            
    def pull_with_submodules(self) -> bool:
        """Pull changes including submodule updates."""
        try:
            print("📄 Pulling main repository...")
            subprocess.run(['git', 'pull', 'origin', 'main'], check=True, cwd=self.repo_path)
            
            print("📦 Updating submodules...")
            subprocess.run(
                ['git', 'submodule', 'update', '--init', '--recursive', '--remote'],
                check=True,
                cwd=self.repo_path
            )
            
            print("✅ Successfully pulled main repository and submodules!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Pull failed: {e}")
            return False


def main():
    """Main entry point for git submodule setup."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Git submodule management for media-register')
    parser.add_argument('command', choices=['setup', 'push', 'pull'], 
                        help='Command to execute')
    parser.add_argument('-m', '--message', help='Commit message for push command')
    
    args = parser.parse_args()
    
    manager = GitSubmoduleManager()
    
    if args.command == 'setup':
        print("Setting up git submodule configuration...")
        manager.setup_pre_push_hook()
        manager.setup_git_aliases()
        manager.configure_submodule()
        
        print("\n✨ Git submodule configuration complete!")
        print("\nAvailable commands:")
        print("  git sall      - Show status of parent repo and all submodules")
        print("  git addall    - Add all changes in parent repo and submodules")
        print("  git pushall   - Commit and push parent repo and all submodules")
        print("  git pullall   - Pull parent repo and update all submodules")
        print("\nThe pre-push hook will automatically check submodules before pushing.")
        
    elif args.command == 'push':
        if not args.message:
            print("❌ Commit message required for push command")
            sys.exit(1)
        manager.push_with_submodules(args.message)
        
    elif args.command == 'pull':
        manager.pull_with_submodules()


if __name__ == '__main__':
    main()