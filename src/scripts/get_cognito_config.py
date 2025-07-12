#!/usr/bin/env python3
"""
Get Cognito configuration - Python replacement for scripts/get-cognito-config.sh

Retrieves Cognito configuration from CloudFormation outputs.
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cloudformation.stack_manager import StackManager


def main():
    """Get Cognito configuration from CloudFormation."""
    parser = argparse.ArgumentParser(
        description="Get Cognito configuration from CloudFormation stack"
    )
    parser.add_argument(
        "environment",
        nargs="?",
        default="dev",
        choices=["dev", "staging", "prod", "production"],
        help="Environment (default: dev)",
    )
    parser.add_argument(
        "--region", default="us-west-1", help="AWS region (default: us-west-1)"
    )
    parser.add_argument(
        "--format",
        choices=["env", "json", "shell"],
        default="env",
        help="Output format (default: env)",
    )

    args = parser.parse_args()

    # Normalize environment
    environment = args.environment
    if environment == "production":
        environment = "prod"

    # Get stack info
    stack_name = f"fraud-or-not-{environment}"
    stack_manager = StackManager(region=args.region)

    try:
        stack = stack_manager.describe_stack(stack_name)
        if not stack:
            print(f"Error: Stack {stack_name} not found", file=sys.stderr)
            sys.exit(1)

        # Extract Cognito outputs
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}

        cognito_config = {
            "NEXT_PUBLIC_AWS_REGION": args.region,
            "NEXT_PUBLIC_USER_POOL_ID": outputs.get("UserPoolId", ""),
            "NEXT_PUBLIC_USER_POOL_CLIENT_ID": outputs.get("UserPoolClientId", ""),
            "NEXT_PUBLIC_API_URL": outputs.get("ApiUrl", ""),
            "NEXT_PUBLIC_CLOUDFRONT_URL": outputs.get("CloudFrontUrl", ""),
        }

        # Output in requested format
        if args.format == "json":
            print(json.dumps(cognito_config, indent=2))
        elif args.format == "shell":
            for key, value in cognito_config.items():
                print(f'export {key}="{value}"')
        else:  # env format
            print("# Add these to your .env.local file:")
            for key, value in cognito_config.items():
                print(f"{key}={value}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
