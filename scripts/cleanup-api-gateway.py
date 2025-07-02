#!/usr/bin/env python3
"""
Clean up orphaned API Gateway resources from failed CloudFormation deployments.
"""

import boto3
import sys
import re
from typing import Optional

def get_stack_prefix(project_name: str, environment: str) -> str:
    """Get the expected stack name prefix."""
    return f"{project_name}-{environment}"

def find_orphaned_api_gateways(api_client, stack_prefix: str):
    """Find API Gateway REST APIs that might be orphaned."""
    orphaned_apis = []
    
    try:
        # List all REST APIs
        paginator = api_client.get_paginator('get_rest_apis')
        
        for page in paginator.paginate():
            for api in page.get('items', []):
                api_name = api.get('name', '')
                api_id = api.get('id')
                
                # Check if this API matches our stack pattern
                if stack_prefix in api_name:
                    print(f"Found API: {api_name} (ID: {api_id})")
                    
                    # Check if it has deployments/stages
                    try:
                        deployments = api_client.get_deployments(restApiId=api_id)
                        stages = api_client.get_stages(restApiId=api_id)
                        
                        print(f"  - Deployments: {len(deployments.get('items', []))}")
                        print(f"  - Stages: {len(stages.get('item', []))}")
                        
                        # Check for the specific stage that's causing issues
                        for stage in stages.get('item', []):
                            if stage.get('stageName') == 'api':
                                print(f"  - Found 'api' stage - this might be the orphaned resource")
                                orphaned_apis.append({
                                    'api_id': api_id,
                                    'api_name': api_name,
                                    'stage_name': 'api'
                                })
                                
                    except Exception as e:
                        print(f"  - Error checking deployments/stages: {e}")
                        
    except Exception as e:
        print(f"Error listing APIs: {e}")
        
    return orphaned_apis

def delete_api_gateway_stage(api_client, api_id: str, stage_name: str) -> bool:
    """Delete a specific API Gateway stage."""
    try:
        print(f"\nDeleting stage '{stage_name}' from API {api_id}...")
        api_client.delete_stage(
            restApiId=api_id,
            stageName=stage_name
        )
        print(f"✅ Successfully deleted stage '{stage_name}'")
        return True
    except Exception as e:
        print(f"❌ Error deleting stage: {e}")
        return False

def delete_api_gateway(api_client, api_id: str, api_name: str) -> bool:
    """Delete an entire API Gateway REST API."""
    try:
        print(f"\nDeleting API Gateway: {api_name} ({api_id})...")
        
        # First delete all stages
        stages = api_client.get_stages(restApiId=api_id)
        for stage in stages.get('item', []):
            stage_name = stage.get('stageName')
            delete_api_gateway_stage(api_client, api_id, stage_name)
        
        # Then delete the API itself
        api_client.delete_rest_api(restApiId=api_id)
        print(f"✅ Successfully deleted API Gateway: {api_name}")
        return True
    except Exception as e:
        print(f"❌ Error deleting API: {e}")
        return False

def main():
    """Main function."""
    # Configuration
    project_name = 'people-cards'
    environment = 'staging'
    region = 'us-west-1'
    
    # Parse command line args
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            print("Usage: cleanup-api-gateway.py [--delete-stage-only] [--force-delete-api]")
            print("  --delete-stage-only: Only delete the 'api' stage, not the entire API")
            print("  --force-delete-api: Delete the entire API Gateway")
            sys.exit(0)
    
    delete_stage_only = '--delete-stage-only' in sys.argv
    force_delete_api = '--force-delete-api' in sys.argv
    
    # Create API Gateway client
    api_client = boto3.client('apigateway', region_name=region)
    
    print(f"🔍 Looking for orphaned API Gateway resources...")
    print(f"   Project: {project_name}")
    print(f"   Environment: {environment}")
    print(f"   Region: {region}")
    print()
    
    # Find orphaned APIs
    stack_prefix = get_stack_prefix(project_name, environment)
    orphaned_apis = find_orphaned_api_gateways(api_client, stack_prefix)
    
    if not orphaned_apis:
        print("\n✅ No orphaned API Gateway resources found!")
        return
    
    print(f"\n⚠️  Found {len(orphaned_apis)} potentially orphaned API Gateway resources")
    
    # Handle cleanup
    for api_info in orphaned_apis:
        api_id = api_info['api_id']
        api_name = api_info['api_name']
        stage_name = api_info['stage_name']
        
        if delete_stage_only:
            # Only delete the problematic stage
            response = input(f"\nDelete stage '{stage_name}' from {api_name}? (y/N): ")
            if response.lower() == 'y':
                delete_api_gateway_stage(api_client, api_id, stage_name)
        elif force_delete_api:
            # Delete the entire API
            response = input(f"\nDelete entire API Gateway {api_name}? (y/N): ")
            if response.lower() == 'y':
                delete_api_gateway(api_client, api_id, api_name)
        else:
            print(f"\nFound orphaned resource: {api_name}")
            print("Run with --delete-stage-only to delete just the 'api' stage")
            print("Run with --force-delete-api to delete the entire API Gateway")

if __name__ == "__main__":
    main()