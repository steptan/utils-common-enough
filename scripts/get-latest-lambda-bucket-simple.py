#!/usr/bin/env python3
"""
Simple script to get the latest Lambda bucket name using the rotation pattern.
This version has minimal dependencies to work in CI/CD environments.
"""

import sys
import os
import re
import boto3
from typing import Optional, Tuple, List, Dict

BUCKET_PATTERN = r"^(.+)-lambda-(.+)-(\d{3})-(\d{3})$"


def parse_bucket_name(bucket_name: str) -> Optional[Tuple[str, str, int, int]]:
    """Parse bucket name to extract components."""
    match = re.match(BUCKET_PATTERN, bucket_name)
    if match:
        project, env, thousands, number = match.groups()
        return project, env, int(thousands), int(number)
    return None


def get_bucket_number(thousands: int, number: int) -> int:
    """Convert thousands and number to single integer."""
    return thousands * 1000 + number


def format_bucket_name(
    project: str, environment: str, thousands: int, number: int
) -> str:
    """Format bucket name with given numbers."""
    return f"{project}-lambda-{environment}-{thousands:03d}-{number:03d}"


def list_project_buckets(
    s3_client, project_name: str, environment: str
) -> List[Dict[str, any]]:
    """List all buckets matching the project pattern."""
    matching_buckets = []

    try:
        response = s3_client.list_buckets()

        for bucket in response.get("Buckets", []):
            bucket_name = bucket["Name"]
            parsed = parse_bucket_name(bucket_name)

            if parsed and parsed[0] == project_name and parsed[1] == environment:
                _, _, thousands, number = parsed
                total = get_bucket_number(thousands, number)

                matching_buckets.append(
                    {
                        "name": bucket_name,
                        "thousands": thousands,
                        "number": number,
                        "total": total,
                    }
                )

        # Sort by total number
        matching_buckets.sort(key=lambda x: x["total"])

    except Exception as e:
        print(f"Warning: Could not list buckets: {e}", file=sys.stderr)
        # If we can't list buckets, try to probe for existing ones
        for i in range(10):  # Check first 10 possible buckets
            bucket_name = format_bucket_name(project_name, environment, 0, i)
            try:
                s3_client.head_bucket(Bucket=bucket_name)
                print(f"Found existing bucket: {bucket_name}", file=sys.stderr)
                matching_buckets.append(
                    {"name": bucket_name, "thousands": 0, "number": i, "total": i}
                )
            except:
                # Bucket doesn't exist or not accessible
                pass

    return matching_buckets


def create_bucket(s3_client, bucket_name: str, region: str) -> bool:
    """Create S3 bucket in the specified region."""
    try:
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )

        # Enable versioning
        s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )

        print(f"Created bucket: {bucket_name}", file=sys.stderr)
        return True

    except Exception as e:
        print(f"Error creating bucket {bucket_name}: {e}", file=sys.stderr)
        return False


def main():
    """Main function."""
    # Get configuration from environment
    project_name = os.environ.get("PROJECT_NAME", "people-cards")
    environment = os.environ.get("ENVIRONMENT", "staging")
    region = os.environ.get("AWS_REGION", "us-west-1")

    # Create S3 client
    s3_client = boto3.client("s3", region_name=region)

    # List existing buckets
    buckets = list_project_buckets(s3_client, project_name, environment)

    if buckets:
        # Return the latest bucket
        latest = buckets[-1]["name"]
        print(latest)
    else:
        # No buckets exist, create the first one
        print(
            f"No Lambda buckets found for {project_name}-{environment}", file=sys.stderr
        )
        first_bucket = format_bucket_name(project_name, environment, 0, 0)

        if create_bucket(s3_client, first_bucket, region):
            print(first_bucket)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
