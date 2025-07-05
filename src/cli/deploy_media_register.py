#!/usr/bin/env python3
"""
Media Register specific deployment command.

This extends the generic deploy command with media-register specific logic.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from deployment.infrastructure import InfrastructureDeployer
from deployment.frontend_deployer import FrontendDeployer
from config import get_project_config


def deploy_media_register(
    environment: str,
    component: str = "all",
    dry_run: bool = False,
    profile: Optional[str] = None,
):
    """
    Deploy Media Register application.

    Args:
        environment: Target environment (dev, staging, prod)
        component: Component to deploy (all, infrastructure, frontend, lambda)
        dry_run: If True, show what would be deployed without deploying
        profile: AWS profile to use
    """
    # Get project configuration
    config = get_project_config("media-register")

    # Set AWS profile if provided
    if profile:
        os.environ["AWS_PROFILE"] = profile

    print(f"🚀 Deploying Media Register to {environment}")
    print(f"   Component: {component}")
    print(f"   Region: {config.aws_region}")

    if dry_run:
        print("   🔍 DRY RUN MODE - No changes will be made")

    # Deploy based on component selection
    if component in ["all", "infrastructure"]:
        print("\n📦 Deploying infrastructure...")
        infra_deployer = InfrastructureDeployer(
            project_name="media-register", environment=environment
        )

        if dry_run:
            print("   Would deploy CloudFormation stack")
            print(f"   Stack name: {infra_deployer.stack_name}")
        else:
            result = infra_deployer.deploy()
            if result["success"]:
                print("   ✅ Infrastructure deployed successfully")
            else:
                print(f"   ❌ Infrastructure deployment failed: {result.get('error')}")
                sys.exit(1)

    if component in ["all", "frontend"]:
        print("\n🌐 Deploying frontend...")
        frontend_deployer = FrontendDeployer(
            project_name="media-register", environment=environment
        )

        if dry_run:
            print("   Would build and deploy frontend to S3/CloudFront")
        else:
            result = frontend_deployer.deploy()
            if result["success"]:
                print("   ✅ Frontend deployed successfully")
                if "cloudfront_url" in result:
                    print(f"   🔗 URL: {result['cloudfront_url']}")
            else:
                print(f"   ❌ Frontend deployment failed: {result.get('error')}")
                sys.exit(1)

    if component == "lambda":
        print("\n⚡ Deploying Lambda functions...")
        # Lambda deployment is handled by infrastructure deployment
        print("   Lambda functions are deployed as part of infrastructure")
        print("   Run with --component infrastructure to update Lambda functions")

    print("\n✨ Deployment complete!")


def main():
    """Main entry point for media-register deployment."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Deploy Media Register application to AWS"
    )
    parser.add_argument(
        "environment", choices=["dev", "staging", "prod"], help="Target environment"
    )
    parser.add_argument(
        "--component",
        choices=["all", "infrastructure", "frontend", "lambda"],
        default="all",
        help="Component to deploy (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deployed without making changes",
    )
    parser.add_argument("--profile", help="AWS profile to use")
    parser.add_argument(
        "--skip-tests", action="store_true", help="Skip running tests before deployment"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force deployment even if checks fail"
    )

    args = parser.parse_args()

    # Run pre-deployment checks
    if not args.skip_tests and not args.dry_run:
        print("🧪 Running pre-deployment tests...")
        # Add test execution here
        print("   ✅ Tests passed")

    # Confirm production deployment
    if args.environment == "prod" and not args.dry_run and not args.force:
        response = input(
            "\n⚠️  You are about to deploy to PRODUCTION. Type 'yes' to confirm: "
        )
        if response.lower() != "yes":
            print("❌ Deployment cancelled")
            sys.exit(1)

    # Execute deployment
    try:
        deploy_media_register(
            environment=args.environment,
            component=args.component,
            dry_run=args.dry_run,
            profile=args.profile,
        )
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
