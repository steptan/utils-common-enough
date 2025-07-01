#!/usr/bin/env python3
"""
Setup script for project-utils.

This script helps set up the utils project and verify everything is working.
"""

import os
import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check Python version is 3.11+."""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 or higher is required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} is supported")


def check_pip():
    """Check pip is available."""
    try:
        import pip
        print("✅ pip is installed")
    except ImportError:
        print("❌ pip is not installed")
        print("   Install pip: python -m ensurepip --upgrade")
        sys.exit(1)


def install_package():
    """Install the package in development mode."""
    print("\n📦 Installing project-utils in development mode...")
    
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Package installed successfully")
    else:
        print("❌ Failed to install package")
        print(result.stderr)
        sys.exit(1)


def verify_commands():
    """Verify CLI commands are available."""
    print("\n🔍 Verifying CLI commands...")
    
    commands = [
        "project-utils",
        "project-deploy",
        "project-iam",
        "project-lambda",
        "project-test",
        "project-cfn",
        "project-db"
    ]
    
    all_found = True
    for cmd in commands:
        result = subprocess.run(
            ["which", cmd],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {cmd} is available")
        else:
            print(f"❌ {cmd} not found in PATH")
            all_found = False
    
    if not all_found:
        print("\n⚠️  Some commands are not in PATH")
        print("   You may need to add the pip scripts directory to your PATH")
        print("   Or use 'python -m cli.<command>' instead")


def check_aws_cli():
    """Check AWS CLI is installed."""
    result = subprocess.run(
        ["which", "aws"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ AWS CLI is installed")
    else:
        print("⚠️  AWS CLI not found (optional but recommended)")
        print("   Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")


def check_node():
    """Check Node.js is installed."""
    result = subprocess.run(
        ["which", "node"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        # Get version
        version_result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True
        )
        print(f"✅ Node.js is installed ({version_result.stdout.strip()})")
    else:
        print("⚠️  Node.js not found (required for Lambda projects)")
        print("   Install: https://nodejs.org/")


def check_config_files():
    """Check configuration files exist."""
    print("\n📋 Checking configuration files...")
    
    config_dir = Path(__file__).parent / "config"
    expected_configs = ["fraud-or-not.yaml", "media-register.yaml", "people-cards.yaml"]
    
    for config_file in expected_configs:
        config_path = config_dir / config_file
        if config_path.exists():
            print(f"✅ {config_file} found")
        else:
            print(f"❌ {config_file} not found")


def main():
    """Run setup checks."""
    print("🚀 Setting up project-utils\n")
    
    # Check prerequisites
    check_python_version()
    check_pip()
    
    # Install package
    install_package()
    
    # Verify installation
    verify_commands()
    
    # Check optional dependencies
    print("\n📦 Checking optional dependencies...")
    check_aws_cli()
    check_node()
    
    # Check configuration
    check_config_files()
    
    print("\n✨ Setup complete!")
    print("\nNext steps:")
    print("1. Configure AWS credentials: project-utils setup")
    print("2. Validate your environment: project-utils validate --project <name> --environment dev")
    print("3. Estimate costs: project-utils estimate-cost --project <name> --environment dev")
    print("4. Deploy infrastructure: project-deploy deploy --project <name> --environment dev")
    print("\nNew commands available:")
    print("  project-utils setup          - Interactive setup wizard")
    print("  project-utils validate       - Pre-deployment validation")
    print("  project-utils audit-security - Security audit")
    print("  project-utils check-compliance - Well-Architected compliance")
    print("  project-utils estimate-cost  - Cost estimation")
    print("  project-utils analyze-cost   - Actual cost analysis")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()