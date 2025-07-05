#!/usr/bin/env python3
"""
Deploy infrastructure script - Generic infrastructure deployment

This script provides generic infrastructure deployment functionality
that can be used by any project with proper configuration.
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from deployment.infrastructure import InfrastructureDeployer


def main():
    """Main deployment function."""
    # Get project info from environment or defaults
    project_name = os.environ.get("PROJECT_NAME", "my-project")
    project_root = Path(os.environ.get("PROJECT_ROOT", Path.cwd()))
    default_region = os.environ.get("AWS_REGION", "us-west-1")

    parser = argparse.ArgumentParser(
        description=f"Deploy {project_name} infrastructure"
    )
    parser.add_argument(
        "environment",
        nargs="?",
        default="dev",
        choices=["dev", "staging", "prod", "production"],
        help="Deployment environment (default: dev)",
    )
    parser.add_argument(
        "--project",
        default=project_name,
        help=f"Project name (default: {project_name})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Generate template without deploying"
    )
    parser.add_argument(
        "--auto-approve", action="store_true", help="Skip confirmation prompts"
    )
    parser.add_argument(
        "--region",
        default=default_region,
        help=f"AWS region (default: {default_region})",
    )
    parser.add_argument(
        "--template",
        help="CloudFormation template path (auto-detected if not specified)",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=project_root / "config",
        help="Configuration directory (default: config/)",
    )

    args = parser.parse_args()

    # Normalize environment name
    environment = args.environment
    if environment == "production":
        environment = "prod"

    # Look for template if not specified
    template_path = args.template
    if not template_path:
        # Try common locations
        possible_templates = [
            project_root / "deployments" / environment / "template.json",
            project_root / "deployments" / environment / "template.yaml",
            project_root / f"cloudformation-{environment}.yaml",
            project_root / f"cloudformation-{environment}.json",
            project_root / "cloudformation.yaml",
            project_root / "cloudformation.json",
            project_root / "template.yaml",
            project_root / "template.json",
        ]

        for possible in possible_templates:
            if possible.exists():
                template_path = str(possible)
                break

    # Create deployer
    deployer = InfrastructureDeployer(
        project_name=args.project,
        environment=environment,
        template_path=template_path,
        region=args.region,
    )

    # If no template found, try to generate one
    if not template_path or not Path(template_path).exists():
        print(f"No template found. Attempting to generate from constructs...")

        # Check if we have a deploy.py that can generate templates
        deploy_script = project_root / "deploy_generate.py"
        if not deploy_script.exists():
            # Try to use constructs directly
            try:
                # Import project-specific constructs
                sys.path.insert(0, str(project_root))
                from constructs import generate_template

                template = generate_template(environment, args.config_dir)

                # Save template
                output_dir = project_root / "deployments" / environment
                output_dir.mkdir(parents=True, exist_ok=True)
                template_path = output_dir / "template.json"

                import json

                with open(template_path, "w") as f:
                    json.dump(template, f, indent=2)

                deployer.template_path = template_path

            except ImportError:
                print("Error: No template found and unable to generate one.")
                print(
                    "Please provide a template with --template or ensure constructs are available."
                )
                sys.exit(1)

    # Deploy
    if args.dry_run:
        print(f"Dry run mode - would deploy {args.project}-{environment}")
        if template_path and Path(template_path).exists():
            print(f"Using template: {template_path}")
        return 0

    # Run deployment
    result = deployer.deploy(
        parameters={},  # Could be loaded from config
        tags={
            "Project": args.project,
            "Environment": environment,
            "ManagedBy": "deploy-infrastructure",
        },
        capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
        wait=True,
    )

    if result.status == "success":
        print(f"\n✅ Deployment successful!")
        if result.outputs:
            print("\nOutputs:")
            for key, value in result.outputs.items():
                print(f"  {key}: {value}")
        return 0
    else:
        print(f"\n❌ Deployment failed: {result.error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
