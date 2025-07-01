#!/usr/bin/env python3
"""
Test S3 tagging permissions for the CI/CD user.
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError

def test_s3_tagging_permission():
    """Test if the CI/CD user can tag S3 buckets."""
    # Create S3 client using CI/CD credentials
    # This assumes AWS credentials are configured for the CI/CD user
    s3 = boto3.client('s3')
    iam = boto3.client('iam')
    
    try:
        # Get current user info
        try:
            user_info = iam.get_user()
            username = user_info['User']['UserName']
            user_arn = user_info['User']['Arn']
            print(f"👤 Running as: {username}")
            print(f"🔑 ARN: {user_arn}")
        except:
            # If get_user fails, we might be using assumed role or other credentials
            sts = boto3.client('sts')
            caller = sts.get_caller_identity()
            print(f"👤 Running as: {caller.get('UserId', 'Unknown')}")
            print(f"🔑 ARN: {caller['Arn']}")
    except Exception as e:
        print(f"⚠️  Could not determine current identity: {e}")
    
    # Test bucket name
    test_bucket = "people-cards-test-tagging-permissions"
    
    print(f"\n🧪 Testing S3 tagging permissions...")
    
    # Try to create a test bucket with tags
    try:
        print(f"📦 Creating test bucket: {test_bucket}")
        
        # First create the bucket
        s3.create_bucket(
            Bucket=test_bucket,
            CreateBucketConfiguration={'LocationConstraint': 'us-west-1'}
        )
        print("✅ Bucket created successfully")
        
        # Now try to add tags
        print("🏷️  Adding tags to bucket...")
        s3.put_bucket_tagging(
            Bucket=test_bucket,
            Tagging={
                'TagSet': [
                    {
                        'Key': 'Environment',
                        'Value': 'test'
                    },
                    {
                        'Key': 'Purpose',
                        'Value': 'permission-test'
                    }
                ]
            }
        )
        print("✅ Tags added successfully!")
        
        # Verify tags
        response = s3.get_bucket_tagging(Bucket=test_bucket)
        print("📋 Current tags:")
        for tag in response['TagSet']:
            print(f"   - {tag['Key']}: {tag['Value']}")
        
        # Clean up
        print("\n🧹 Cleaning up test bucket...")
        s3.delete_bucket(Bucket=test_bucket)
        print("✅ Test bucket deleted")
        
        print("\n✅ S3 tagging permissions are working correctly!")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        print(f"\n❌ Error: {error_code}")
        print(f"📝 Message: {error_message}")
        
        if error_code == 'AccessDenied':
            print("\n🔍 Troubleshooting suggestions:")
            print("1. The policy might not have propagated yet (wait 5-10 seconds)")
            print("2. There might be an explicit deny somewhere")
            print("3. The credentials might not be using the expected user/role")
        
        # Try to clean up if bucket was created
        try:
            s3.delete_bucket(Bucket=test_bucket)
            print("\n🧹 Cleaned up test bucket")
        except:
            pass
        
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

def check_policy_simulator():
    """Use IAM policy simulator to test permissions."""
    print("\n🔬 Testing with IAM Policy Simulator...")
    
    iam = boto3.client('iam')
    
    try:
        # Simulate the s3:PutBucketTagging action
        response = iam.simulate_principal_policy(
            PolicySourceArn='arn:aws:iam::332087884612:user/people-cards-cicd',
            ActionNames=['s3:PutBucketTagging'],
            ResourceArns=['arn:aws:s3:::people-cards-staging-frontend-staging']
        )
        
        for result in response['EvaluationResults']:
            print(f"\n📋 Action: {result['EvalActionName']}")
            print(f"🎯 Resource: {result['EvalResourceName']}")
            print(f"✅ Decision: {result['EvalDecision']}")
            
            if result['EvalDecision'] != 'allowed':
                print(f"❌ Reason: {result.get('MatchedStatements', 'No matching statements')}")
                
    except Exception as e:
        print(f"⚠️  Could not run policy simulator: {e}")

def main():
    """Main function."""
    print("🧪 Testing S3 tagging permissions for CI/CD user...")
    
    # Check who we're running as
    test_s3_tagging_permission()
    
    # Try policy simulator
    check_policy_simulator()

if __name__ == "__main__":
    main()