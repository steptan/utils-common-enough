#!/usr/bin/env python3
"""
Migration script to transition AWS resources to 3-letter naming convention.

This script helps identify resources using the old naming convention and
provides commands to migrate them to the new convention.
"""

import argparse
import json
import sys
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.naming import NamingConvention


class ResourceMigrator:
    """Handles migration of AWS resources to new naming convention."""
    
    def __init__(self, region: str, profile: Optional[str] = None, dry_run: bool = True):
        """Initialize the migrator."""
        self.region = region
        self.dry_run = dry_run
        
        session_args = {"region_name": region}
        if profile:
            session_args["profile_name"] = profile
        
        session = boto3.Session(**session_args)
        self.s3 = session.client("s3")
        self.dynamodb = session.client("dynamodb")
        self.lambda_client = session.client("lambda")
        self.cloudformation = session.client("cloudformation")
        self.iam = session.client("iam")
        
        self.migration_report: Dict[str, List[Dict]] = {
            "s3_buckets": [],
            "dynamodb_tables": [],
            "lambda_functions": [],
            "cloudformation_stacks": [],
            "iam_roles": [],
        }
    
    def scan_s3_buckets(self) -> List[Dict]:
        """Scan S3 buckets for legacy naming."""
        legacy_buckets = []
        
        try:
            response = self.s3.list_buckets()
            
            for bucket in response.get("Buckets", []):
                bucket_name = bucket["Name"]
                
                if NamingConvention.is_legacy_name(bucket_name):
                    new_name = NamingConvention.convert_legacy_name(bucket_name)
                    
                    legacy_buckets.append({
                        "current_name": bucket_name,
                        "new_name": new_name,
                        "type": "s3_bucket",
                        "creation_date": bucket.get("CreationDate"),
                        "migration_note": "S3 bucket names are globally unique. New bucket required."
                    })
        
        except Exception as e:
            print(f"Error scanning S3 buckets: {e}")
        
        self.migration_report["s3_buckets"] = legacy_buckets
        return legacy_buckets
    
    def scan_dynamodb_tables(self) -> List[Dict]:
        """Scan DynamoDB tables for legacy naming."""
        legacy_tables = []
        
        try:
            paginator = self.dynamodb.get_paginator("list_tables")
            
            for page in paginator.paginate():
                for table_name in page.get("TableNames", []):
                    if NamingConvention.is_legacy_name(table_name):
                        new_name = NamingConvention.convert_legacy_name(table_name)
                        
                        # Get table details
                        try:
                            table_info = self.dynamodb.describe_table(TableName=table_name)
                            item_count = table_info["Table"].get("ItemCount", 0)
                            
                            legacy_tables.append({
                                "current_name": table_name,
                                "new_name": new_name,
                                "type": "dynamodb_table",
                                "item_count": item_count,
                                "migration_note": f"Table has {item_count} items. Data migration required."
                            })
                        except Exception as e:
                            print(f"Error describing table {table_name}: {e}")
        
        except Exception as e:
            print(f"Error scanning DynamoDB tables: {e}")
        
        self.migration_report["dynamodb_tables"] = legacy_tables
        return legacy_tables
    
    def scan_lambda_functions(self) -> List[Dict]:
        """Scan Lambda functions for legacy naming."""
        legacy_functions = []
        
        try:
            paginator = self.lambda_client.get_paginator("list_functions")
            
            for page in paginator.paginate():
                for function in page.get("Functions", []):
                    function_name = function["FunctionName"]
                    
                    if NamingConvention.is_legacy_name(function_name):
                        new_name = NamingConvention.convert_legacy_name(function_name)
                        
                        legacy_functions.append({
                            "current_name": function_name,
                            "new_name": new_name,
                            "type": "lambda_function",
                            "runtime": function.get("Runtime"),
                            "last_modified": function.get("LastModified"),
                            "migration_note": "Update environment variables and API Gateway integrations."
                        })
        
        except Exception as e:
            print(f"Error scanning Lambda functions: {e}")
        
        self.migration_report["lambda_functions"] = legacy_functions
        return legacy_functions
    
    def scan_cloudformation_stacks(self) -> List[Dict]:
        """Scan CloudFormation stacks for legacy naming."""
        legacy_stacks = []
        
        try:
            paginator = self.cloudformation.get_paginator("list_stacks")
            
            for page in paginator.paginate(
                StackStatusFilter=[
                    "CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"
                ]
            ):
                for stack in page.get("StackSummaries", []):
                    stack_name = stack["StackName"]
                    
                    if NamingConvention.is_legacy_name(stack_name):
                        new_name = NamingConvention.convert_legacy_name(stack_name)
                        
                        legacy_stacks.append({
                            "current_name": stack_name,
                            "new_name": new_name,
                            "type": "cloudformation_stack",
                            "status": stack.get("StackStatus"),
                            "last_updated": stack.get("LastUpdatedTime"),
                            "migration_note": "Requires stack update or recreation with new template."
                        })
        
        except Exception as e:
            print(f"Error scanning CloudFormation stacks: {e}")
        
        self.migration_report["cloudformation_stacks"] = legacy_stacks
        return legacy_stacks
    
    def generate_migration_plan(self) -> str:
        """Generate a migration plan with commands."""
        plan = []
        plan.append("# AWS Resource Migration Plan")
        plan.append("# From legacy naming to 3-letter convention")
        plan.append("")
        
        if self.dry_run:
            plan.append("## DRY RUN MODE - No changes will be made")
        else:
            plan.append("## LIVE MODE - Changes will be applied")
        
        plan.append("")
        
        # S3 Buckets
        if self.migration_report["s3_buckets"]:
            plan.append("## S3 Buckets")
            plan.append("Note: S3 bucket names are globally unique. Migration requires creating new buckets.")
            plan.append("")
            
            for bucket in self.migration_report["s3_buckets"]:
                if bucket["new_name"]:
                    plan.append(f"### {bucket['current_name']} → {bucket['new_name']}")
                    plan.append("```bash")
                    plan.append(f"# Create new bucket")
                    plan.append(f"aws s3 mb s3://{bucket['new_name']} --region {self.region}")
                    plan.append(f"# Copy data")
                    plan.append(f"aws s3 sync s3://{bucket['current_name']} s3://{bucket['new_name']}")
                    plan.append(f"# Update application configuration to use new bucket")
                    plan.append(f"# After verification, delete old bucket")
                    plan.append(f"# aws s3 rb s3://{bucket['current_name']} --force")
                    plan.append("```")
                    plan.append("")
        
        # DynamoDB Tables
        if self.migration_report["dynamodb_tables"]:
            plan.append("## DynamoDB Tables")
            plan.append("Note: Table migration requires data export/import or use of DynamoDB Streams.")
            plan.append("")
            
            for table in self.migration_report["dynamodb_tables"]:
                if table["new_name"]:
                    plan.append(f"### {table['current_name']} → {table['new_name']}")
                    plan.append(f"Items: {table['item_count']}")
                    plan.append("```bash")
                    plan.append(f"# Option 1: Use AWS Data Pipeline or DMS")
                    plan.append(f"# Option 2: Use DynamoDB export to S3, then import")
                    plan.append(f"# Option 3: Use custom script with scan/write")
                    plan.append("```")
                    plan.append("")
        
        # Lambda Functions
        if self.migration_report["lambda_functions"]:
            plan.append("## Lambda Functions")
            plan.append("")
            
            for func in self.migration_report["lambda_functions"]:
                if func["new_name"]:
                    plan.append(f"### {func['current_name']} → {func['new_name']}")
                    plan.append(f"Runtime: {func['runtime']}")
                    plan.append("Migration steps:")
                    plan.append("1. Create new function with new name")
                    plan.append("2. Copy function code and configuration")
                    plan.append("3. Update environment variables")
                    plan.append("4. Update API Gateway integrations")
                    plan.append("5. Update event source mappings")
                    plan.append("6. Test thoroughly")
                    plan.append("7. Delete old function")
                    plan.append("")
        
        # CloudFormation Stacks
        if self.migration_report["cloudformation_stacks"]:
            plan.append("## CloudFormation Stacks")
            plan.append("")
            
            for stack in self.migration_report["cloudformation_stacks"]:
                if stack["new_name"]:
                    plan.append(f"### {stack['current_name']} → {stack['new_name']}")
                    plan.append(f"Status: {stack['status']}")
                    plan.append("```bash")
                    plan.append(f"# Update template to use new naming convention")
                    plan.append(f"# Deploy with new stack name")
                    plan.append(f"aws cloudformation create-stack \\")
                    plan.append(f"  --stack-name {stack['new_name']} \\")
                    plan.append(f"  --template-body file://template.yaml \\")
                    plan.append(f"  --capabilities CAPABILITY_IAM")
                    plan.append("```")
                    plan.append("")
        
        return "\n".join(plan)
    
    def generate_summary(self) -> str:
        """Generate a summary of resources to migrate."""
        summary = []
        summary.append("Migration Summary")
        summary.append("=" * 50)
        
        total_resources = 0
        
        for resource_type, resources in self.migration_report.items():
            count = len(resources)
            total_resources += count
            
            if count > 0:
                summary.append(f"{resource_type.replace('_', ' ').title()}: {count}")
        
        summary.append(f"\nTotal resources to migrate: {total_resources}")
        
        return "\n".join(summary)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate AWS resources to 3-letter naming convention"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--profile",
        help="AWS profile to use"
    )
    parser.add_argument(
        "--output",
        choices=["summary", "plan", "json"],
        default="summary",
        help="Output format (default: summary)"
    )
    parser.add_argument(
        "--scan",
        choices=["all", "s3", "dynamodb", "lambda", "cloudformation"],
        default="all",
        help="Resource types to scan (default: all)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply migrations (DANGEROUS - default is dry run)"
    )
    
    args = parser.parse_args()
    
    # Initialize migrator
    migrator = ResourceMigrator(
        region=args.region,
        profile=args.profile,
        dry_run=not args.apply
    )
    
    print(f"Scanning AWS resources in region {args.region}...")
    print("")
    
    # Scan resources based on selection
    if args.scan == "all":
        migrator.scan_s3_buckets()
        migrator.scan_dynamodb_tables()
        migrator.scan_lambda_functions()
        migrator.scan_cloudformation_stacks()
    elif args.scan == "s3":
        migrator.scan_s3_buckets()
    elif args.scan == "dynamodb":
        migrator.scan_dynamodb_tables()
    elif args.scan == "lambda":
        migrator.scan_lambda_functions()
    elif args.scan == "cloudformation":
        migrator.scan_cloudformation_stacks()
    
    # Generate output
    if args.output == "summary":
        print(migrator.generate_summary())
    elif args.output == "plan":
        print(migrator.generate_migration_plan())
    elif args.output == "json":
        print(json.dumps(migrator.migration_report, indent=2, default=str))


if __name__ == "__main__":
    from pathlib import Path
    main()