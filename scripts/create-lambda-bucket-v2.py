#!/usr/bin/env python3
"""
Create a new Lambda deployment bucket with a versioned name.
This avoids conflicts with buckets being deleted.
"""

import boto3
import sys
import os
from datetime import datetime

def create_bucket_in_region(s3_client, bucket_name, region):
    """Create S3 bucket in the specified region."""
    print(f"📦 Creating bucket {bucket_name} in region {region}...")
    
    try:
        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        
        # Enable versioning
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        
        # Add tags
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {'Key': 'Project', 'Value': 'people-cards'},
                    {'Key': 'Environment', 'Value': os.environ.get('ENVIRONMENT', 'staging')},
                    {'Key': 'Purpose', 'Value': 'lambda-deployment'}
                ]
            }
        )
        
        print(f"✅ Successfully created bucket {bucket_name} in region {region}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating bucket: {e}")
        return False

def main():
    """Main function."""
    # Get configuration from environment or defaults
    region = os.environ.get('AWS_REGION', 'us-west-1')
    environment = os.environ.get('ENVIRONMENT', 'staging')
    
    # Create S3 client for the target region
    s3_client = boto3.client('s3', region_name=region)
    
    # Get account ID
    sts = boto3.client('sts')
    account_id = sts.get_caller_identity()['Account']
    
    # Generate bucket name with timestamp to avoid conflicts
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    bucket_name = f"people-cards-lambda-{environment}-{account_id}-v{timestamp}"
    
    print(f"🔍 Creating new Lambda deployment bucket: {bucket_name}")
    print(f"🎯 Target region: {region}")
    
    # Create the bucket
    if create_bucket_in_region(s3_client, bucket_name, region):
        print("✅ Bucket created successfully!")
        print(f"\n📋 New bucket name: {bucket_name}")
        print("\n⚠️  IMPORTANT: Update your CI/CD configuration to use this new bucket name")
        
        # Export the bucket name for CI/CD
        print(f"\nFor GitHub Actions, add this to your workflow:")
        print(f"LAMBDA_BUCKET={bucket_name}")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()