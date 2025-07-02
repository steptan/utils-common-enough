#!/usr/bin/env python3
"""
Fix Lambda deployment bucket region issue.
Ensures the bucket exists in the correct region.
"""

import boto3
import sys
import os
from botocore.exceptions import ClientError

def get_bucket_region(s3_client, bucket_name):
    """Get the region of an S3 bucket."""
    try:
        response = s3_client.get_bucket_location(Bucket=bucket_name)
        region = response.get('LocationConstraint')
        # get_bucket_location returns None for us-east-1
        return region if region else 'us-east-1'
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            return None
        raise

def delete_bucket(s3_client, bucket_name):
    """Delete an S3 bucket and all its contents."""
    print(f"🗑️  Deleting bucket {bucket_name}...")
    
    # First, delete all objects in the bucket
    try:
        # List and delete all objects
        paginator = s3_client.get_paginator('list_object_versions')
        for page in paginator.paginate(Bucket=bucket_name):
            objects_to_delete = []
            
            # Add all versions
            for version in page.get('Versions', []):
                objects_to_delete.append({
                    'Key': version['Key'],
                    'VersionId': version['VersionId']
                })
            
            # Add all delete markers
            for marker in page.get('DeleteMarkers', []):
                objects_to_delete.append({
                    'Key': marker['Key'],
                    'VersionId': marker['VersionId']
                })
            
            if objects_to_delete:
                s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': objects_to_delete}
                )
        
        # Now delete the bucket
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"✅ Successfully deleted bucket {bucket_name}")
        
        # Wait a bit for deletion to propagate
        import time
        print("⏳ Waiting for deletion to propagate...")
        time.sleep(10)
        return True
        
    except Exception as e:
        print(f"❌ Error deleting bucket: {e}")
        return False

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
    
    # Bucket name
    bucket_name = f"people-cards-lambda-{environment}-{account_id}"
    
    print(f"🔍 Checking Lambda deployment bucket: {bucket_name}")
    print(f"🎯 Target region: {region}")
    
    # Check if bucket exists and get its region
    current_region = get_bucket_region(s3_client, bucket_name)
    
    if current_region is None:
        print(f"❌ Bucket {bucket_name} does not exist")
        # Create it in the correct region
        if create_bucket_in_region(s3_client, bucket_name, region):
            print("✅ Bucket created successfully!")
        else:
            sys.exit(1)
    elif current_region != region:
        print(f"⚠️  Bucket exists in wrong region: {current_region} (should be {region})")
        
        # Automatically fix the region mismatch
        print("🔧 Fixing bucket region mismatch...")
        fix_mismatch = True
        if fix_mismatch:
            # Delete the bucket
            if delete_bucket(s3_client, bucket_name):
                # Recreate in correct region
                if create_bucket_in_region(s3_client, bucket_name, region):
                    print("✅ Bucket recreated in correct region!")
                else:
                    print("❌ Failed to recreate bucket")
                    sys.exit(1)
            else:
                print("❌ Failed to delete bucket")
                sys.exit(1)
        else:
            print("❌ Bucket region mismatch not fixed")
            sys.exit(1)
    else:
        print(f"✅ Bucket exists in correct region: {region}")
    
    # Verify the bucket is accessible
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket {bucket_name} is accessible")
    except Exception as e:
        print(f"❌ Error accessing bucket: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()