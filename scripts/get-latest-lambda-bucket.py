#!/usr/bin/env python3
"""
Get the latest Lambda bucket name using the rotation pattern.
Used by CI/CD pipeline to find where to upload Lambda code.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from deployment.bucket_rotation import BucketRotationManager
import boto3


def main():
    """Main function."""
    # Get configuration from environment
    project_name = os.environ.get("PROJECT_NAME", "people-cards")
    environment = os.environ.get("ENVIRONMENT", "staging")
    region = os.environ.get("AWS_REGION", "us-west-1")

    # Get account ID
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    # Create rotation manager
    manager = BucketRotationManager(
        project_name=project_name,
        environment=environment,
        region=region,
        account_id=account_id,
    )

    # Get latest bucket or create first one
    latest_bucket = manager.get_latest_bucket()

    if not latest_bucket:
        print(
            f"No Lambda buckets found for {project_name}-{environment}", file=sys.stderr
        )
        print("Creating first bucket...", file=sys.stderr)
        latest_bucket = manager.rotate_and_create()

    # Output just the bucket name for use in scripts
    print(latest_bucket)


if __name__ == "__main__":
    main()
