#!/usr/bin/env python3
"""Git submodule management commands."""

import os
import subprocess
import sys
from pathlib import Path

import click
from colorama import Fore, Style, init
from typing import List, Any

# Initialize colorama for cross-platform colored output
init()

# Pre-push hook content
PRE_PUSH_HOOK = """#!/bin/bash
# Pre-push hook to ensure submodule changes are pushed

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

echo "Checking submodules..."

# Check if there are any submodules
if [ -f .gitmodules ]; then
    # Get list of submodules
    submodules=$(git config --file .gitmodules --get-regexp path | awk '{ print $2 }')

    for submodule in $submodules; do
        echo "Checking submodule: $submodule"

        # Check if submodule has uncommitted changes
        cd "$submodule" 2>/dev/null
        if [ $? -eq 0 ]; then
            if ! git diff-index --quiet HEAD --; then
                echo -e "${RED}Error: Submodule '$submodule' has uncommitted changes${NC}"
                echo "Please commit changes in the submodule first:"
                echo "  cd $submodule"
                echo "  git add -A && git commit -m 'Your commit message'"
                cd - > /dev/null
                exit 1
            fi

            # Check if submodule has unpushed commits
            if [ -n "$(git log @{u}.. 2>/dev/null)" ]; then
                echo -e "${YELLOW}Warning: Submodule '$submodule' has unpushed commits${NC}"
                echo "Attempting to push submodule changes..."

                # Try to push submodule
                git push
                if [ $? -ne 0 ]; then
                    echo -e "${RED}Failed to push submodule '$submodule'${NC}"
                    echo "Please push the submodule manually:"
                    echo "  cd $submodule"
                    echo "  git push"
                    cd - > /dev/null
                    exit 1
                fi
                echo -e "${GREEN}Successfully pushed submodule '$submodule'${NC}"
            fi

            cd - > /dev/null
        fi
    done

    # Update submodule references in parent repo if needed
    if ! git diff-index --quiet HEAD -- $submodules; then
        echo -e "${YELLOW}Submodule references have changed, updating parent repository${NC}"
    fi
fi

echo -e "${GREEN}Submodule check complete${NC}"
exit 0
"""


def run_command(cmd, cwd=None, check=True) -> None:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=check
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return (
            e.returncode,
            e.stdout.strip() if e.stdout else "",
            e.stderr.strip() if e.stderr else "",
        )


def setup_pre_push_hook() -> None:
    """Set up the pre-push git hook."""
    hook_path = Path(".git/hooks/pre-push")
    hook_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the hook content
    hook_path.write_text(PRE_PUSH_HOOK)

    # Make it executable
    hook_path.chmod(0o755)

    return hook_path


def setup_git_aliases() -> None:
    """Set up useful git aliases for submodule management."""
    aliases = {
        "pushall": '!f() { echo "Checking for submodule changes..."; git submodule foreach "git add -A && git diff-index --quiet HEAD -- || git commit -m \\"Auto-commit from parent repo\\" && git push || true"; echo "Committing parent repository..."; git add -A && git commit -m "$1" && git push; }; f',
        "sall": '!git status && echo "" && git submodule foreach "echo \\"Submodule: $path\\" && git status -s && echo"',
        "pullall": "!git pull && git submodule update --remote --merge",
        "addall": '!git submodule foreach "git add -A" && git add -A',
    }

    for alias, command in aliases.items():
        run_command(f"git config --local alias.{alias} '{command}'")

    return aliases.keys()


def configure_submodule(submodule_name, branch="master", update_method="merge") -> None:
    """Configure a specific submodule."""
    run_command(
        f"git config --file .gitmodules submodule.{submodule_name}.branch {branch}"
    )
    run_command(
        f"git config --file .gitmodules submodule.{submodule_name}.update {update_method}"
    )


def get_submodules() -> None:
    """Get list of submodules in the repository."""
    ret, stdout, _ = run_command(
        "git config --file .gitmodules --get-regexp path", check=False
    )
    if ret != 0:
        return []

    submodules: List[Any] = []
    for line in stdout.splitlines():
        if line.strip():
            # Format: submodule.name.path value
            parts = line.split()
            if len(parts) >= 2:
                submodules.append(parts[1])

    return submodules


@click.group()
def main() -> None:
    """Git submodule management commands."""
    pass


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing hooks and aliases")
def submodules_setup(force) -> None:
    """Set up git submodule configuration, hooks, and aliases."""
    print(f"{Fore.CYAN}Setting up git submodule configuration...{Style.RESET_ALL}")

    # Check if we're in a git repository
    ret, _, _ = run_command("git rev-parse --git-dir", check=False)
    if ret != 0:
        print(f"{Fore.RED}Error: Not in a git repository{Style.RESET_ALL}")
        sys.exit(1)

    # Set up pre-push hook
    hook_path = Path(".git/hooks/pre-push")
    if hook_path.exists() and not force:
        print(
            f"{Fore.YELLOW}Pre-push hook already exists. Use --force to overwrite.{Style.RESET_ALL}"
        )
    else:
        setup_pre_push_hook()
        print(f"{Fore.GREEN}✓ Pre-push hook installed{Style.RESET_ALL}")

    # Set up git aliases
    aliases = setup_git_aliases()
    print(f"{Fore.GREEN}✓ Git aliases configured{Style.RESET_ALL}")

    # Configure submodules
    submodules = get_submodules()
    for submodule in submodules:
        configure_submodule(Path(submodule).name)
        print(f"{Fore.GREEN}✓ Configured submodule: {submodule}{Style.RESET_ALL}")

    # Display available commands
    print(f"\n{Fore.CYAN}Git submodule configuration complete!{Style.RESET_ALL}")
    print("\nAvailable commands:")
    print(
        f"  {Fore.GREEN}git sall{Style.RESET_ALL}      - Show status of parent repo and all submodules"
    )
    print(
        f"  {Fore.GREEN}git addall{Style.RESET_ALL}    - Add all changes in parent repo and submodules"
    )
    print(
        f"  {Fore.GREEN}git pushall{Style.RESET_ALL}   - Commit and push parent repo and all submodules"
    )
    print(
        f"  {Fore.GREEN}git pullall{Style.RESET_ALL}   - Pull parent repo and update all submodules"
    )
    print("\nThe pre-push hook will automatically check submodules before pushing.")


@main.command()
def status() -> None:
    """Show status of repository and all submodules."""
    # Show main repo status
    print(f"{Fore.CYAN}=== Main Repository ==={Style.RESET_ALL}")
    run_command("git status", check=False)

    # Show submodule status
    submodules = get_submodules()
    if submodules:
        print(f"\n{Fore.CYAN}=== Submodules ==={Style.RESET_ALL}")
        for submodule in submodules:
            print(f"\n{Fore.YELLOW}Submodule: {submodule}{Style.RESET_ALL}")
            ret, stdout, _ = run_command("git status -s", cwd=submodule, check=False)
            if stdout:
                print(stdout)
            else:
                print(f"{Fore.GREEN}Clean{Style.RESET_ALL}")


@main.command()
@click.argument("message", required=False)
def pushall(message) -> None:
    """Commit and push changes in repository and all submodules."""
    if not message:
        message = click.prompt("Commit message")

    # Check and push submodules
    submodules = get_submodules()
    for submodule in submodules:
        print(f"\n{Fore.CYAN}Checking submodule: {submodule}{Style.RESET_ALL}")

        # Check for changes
        ret, stdout, _ = run_command(
            "git status --porcelain", cwd=submodule, check=False
        )
        if stdout:
            print(f"  {Fore.YELLOW}Changes detected, committing...{Style.RESET_ALL}")
            run_command("git add -A", cwd=submodule)
            run_command(
                f'git commit -m "Auto-commit from parent repo"',
                cwd=submodule,
                check=False,
            )

            # Push changes
            ret, _, stderr = run_command("git push", cwd=submodule, check=False)
            if ret == 0:
                print(f"  {Fore.GREEN}✓ Pushed successfully{Style.RESET_ALL}")
            else:
                print(f"  {Fore.RED}✗ Push failed: {stderr}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.GREEN}No changes{Style.RESET_ALL}")

    # Commit and push main repo
    print(f"\n{Fore.CYAN}Committing parent repository...{Style.RESET_ALL}")
    run_command("git add -A")
    ret, _, _ = run_command(f'git commit -m "{message}"', check=False)
    if ret == 0:
        ret, _, stderr = run_command("git push", check=False)
        if ret == 0:
            print(
                f"{Fore.GREEN}✓ Successfully pushed parent repository{Style.RESET_ALL}"
            )
        else:
            print(f"{Fore.RED}✗ Push failed: {stderr}{Style.RESET_ALL}")
    else:
        print(
            f"{Fore.YELLOW}No changes to commit in parent repository{Style.RESET_ALL}"
        )


@main.command()
def pullall() -> None:
    """Pull changes for repository and update all submodules."""
    print(f"{Fore.CYAN}Pulling parent repository...{Style.RESET_ALL}")
    ret, stdout, stderr = run_command("git pull", check=False)
    if ret == 0:
        print(f"{Fore.GREEN}✓ Parent repository updated{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Pull failed: {stderr}{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}Updating submodules...{Style.RESET_ALL}")
    ret, stdout, stderr = run_command(
        "git submodule update --remote --merge", check=False
    )
    if ret == 0:
        print(f"{Fore.GREEN}✓ Submodules updated{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Submodule update failed: {stderr}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
