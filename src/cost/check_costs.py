#!/usr/bin/env python3
"""
Simple AWS cost checker for any project.
This script directly uses boto3 to check costs without complex dependencies.
"""

import boto3
import json
from datetime import datetime, timedelta
import sys
import os
from typing import Optional, Dict, List, Tuple

class ProjectCostChecker:
    """Check AWS costs for a specific project."""
    
    def __init__(self, project_name: str, region: str = "us-west-1", profile: Optional[str] = None):
        self.project_name = project_name
        self.region = region
        self.profile = profile
        
        # Initialize AWS clients
        session_args = {"region_name": "us-east-1"}  # Cost Explorer only works in us-east-1
        if profile:
            session_args["profile_name"] = profile
        
        self.session = boto3.Session(**session_args)
        self.ce = self.session.client("ce")
        self.sts = self.session.client("sts")
        
        # Get account ID
        self.account_id = self.sts.get_caller_identity()["Account"]
    
    def get_costs(self, days: int = 7, budget: Optional[float] = None) -> Dict:
        """Get AWS costs for the specified project."""
        
        print(f"📊 AWS Account: {self.account_id}")
        print(f"🏷️  Project: {self.project_name}")
        print("=" * 60)
        
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        print(f"📅 Period: {start_date} to {end_date} ({days} days)")
        print()
        
        results = {
            "project": self.project_name,
            "account_id": self.account_id,
            "period": {"start": str(start_date), "end": str(end_date)},
            "total_cost": 0,
            "daily_average": 0,
            "services": {},
            "daily_costs": []
        }
        
        try:
            # Get total costs
            response = self.ce.get_cost_and_usage(
                TimePeriod={
                    'Start': str(start_date),
                    'End': str(end_date)
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                Filter=self._get_cost_filter()
            )
            
            # Calculate total cost
            total_cost = 0
            daily_costs = []
            
            for result in response['ResultsByTime']:
                daily_cost = float(result['Total']['UnblendedCost']['Amount'])
                total_cost += daily_cost
                daily_costs.append({
                    'date': result['TimePeriod']['Start'],
                    'cost': daily_cost
                })
            
            results["total_cost"] = total_cost
            results["daily_average"] = total_cost / days if days > 0 else 0
            results["daily_costs"] = daily_costs
            
            print(f"💰 Total Cost: ${total_cost:.2f}")
            print(f"📊 Daily Average: ${results['daily_average']:.2f}")
            print()
            
            # Show daily breakdown if less than 14 days
            if days <= 14:
                print("📈 Daily Costs:")
                for day in daily_costs:
                    if day['cost'] > 0:
                        print(f"  {day['date']}: ${day['cost']:.2f}")
                print()
            
            # Get costs by service
            response = self.ce.get_cost_and_usage(
                TimePeriod={
                    'Start': str(start_date),
                    'End': str(end_date)
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[{
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }],
                Filter=self._get_cost_filter()
            )
            
            print("💵 Cost by Service:")
            services = []
            for result in response['ResultsByTime']:
                for group in result['Groups']:
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    if cost > 0:
                        services.append((service, cost))
                        results["services"][service] = cost
            
            # Sort by cost descending
            services.sort(key=lambda x: x[1], reverse=True)
            for service, cost in services:
                print(f"  {service}: ${cost:.2f}")
            
            # Monthly projection
            if days >= 7:
                print()
                monthly_projection = results['daily_average'] * 30
                results["monthly_projection"] = monthly_projection
                print(f"🔮 30-Day Projection: ${monthly_projection:.2f}")
            
            # Get current month's costs (for budget comparison)
            self._check_monthly_budget(budget)
            
            # Cost optimization tips based on services used
            self._print_optimization_tips(results["services"])
            
            return results
            
        except self.ce.exceptions.DataUnavailableException:
            print("⚠️  Cost data not yet available for this time period")
            print("   AWS Cost Explorer data may take up to 24 hours to appear")
            return results
        except Exception as e:
            print(f"❌ Error retrieving costs: {e}")
            print("\nTroubleshooting:")
            print(f"  1. Ensure your AWS resources are tagged with Project={self.project_name}")
            print("  2. Check you have Cost Explorer API permissions")
            print("  3. Verify your AWS credentials are valid")
            return results
    
    def check_untagged_resources(self) -> List[str]:
        """Check for resources that might be missing project tags."""
        print(f"\n🏷️  Checking for potentially untagged {self.project_name} resources...")
        
        untagged = []
        
        # Check Lambda functions
        untagged.extend(self._check_lambda_tags())
        
        # Check DynamoDB tables
        untagged.extend(self._check_dynamodb_tags())
        
        # Check S3 buckets
        untagged.extend(self._check_s3_tags())
        
        if untagged:
            print("\n⚠️  Resources potentially missing Project tags:")
            for resource in untagged:
                print(f"  • {resource}")
            print("\n  Add tags to ensure accurate cost tracking!")
        else:
            print("  ✅ All checked resources appear to be tagged correctly")
        
        return untagged
    
    def _get_cost_filter(self) -> Dict:
        """Get cost filter for the project."""
        return {
            'Tags': {
                'Key': 'Project',
                'Values': [self.project_name]
            }
        }
    
    def _check_monthly_budget(self, budget: Optional[float]) -> None:
        """Check current month's spending against budget."""
        current_month_start = datetime.now().replace(day=1).date()
        current_date = datetime.now().date()
        
        if current_date <= current_month_start:
            return
        
        try:
            response = self.ce.get_cost_and_usage(
                TimePeriod={
                    'Start': str(current_month_start),
                    'End': str(current_date)
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                Filter=self._get_cost_filter()
            )
            
            month_cost = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
            print(f"\n📅 Current Month-to-Date: ${month_cost:.2f}")
            
            if budget:
                percentage = (month_cost / budget) * 100
                
                if percentage > 100:
                    print(f"🚨 BUDGET EXCEEDED: {percentage:.0f}% of ${budget:.0f} monthly budget")
                elif percentage > 80:
                    print(f"⚠️  Budget Warning: {percentage:.0f}% of ${budget:.0f} monthly budget")
                else:
                    print(f"✅ Budget Status: {percentage:.0f}% of ${budget:.0f} monthly budget")
        except Exception as e:
            print(f"⚠️  Could not check monthly budget: {e}")
    
    def _check_lambda_tags(self) -> List[str]:
        """Check Lambda functions for missing tags."""
        untagged = []
        try:
            lambda_client = self.session.client('lambda', region_name=self.region)
            paginator = lambda_client.get_paginator('list_functions')
            
            for page in paginator.paginate():
                for func in page.get('Functions', []):
                    func_name = func['FunctionName']
                    # Check if function name contains project name (case-insensitive)
                    if self.project_name.lower() in func_name.lower():
                        try:
                            tags_response = lambda_client.list_tags(Resource=func['FunctionArn'])
                            tags = tags_response.get('Tags', {})
                            if tags.get('Project') != self.project_name:
                                untagged.append(f"Lambda: {func_name} (missing/incorrect Project tag)")
                        except:
                            pass
        except Exception as e:
            print(f"  ⚠️  Could not check Lambda functions: {e}")
        
        return untagged
    
    def _check_dynamodb_tags(self) -> List[str]:
        """Check DynamoDB tables for missing tags."""
        untagged = []
        try:
            dynamodb = self.session.client('dynamodb', region_name=self.region)
            paginator = dynamodb.get_paginator('list_tables')
            
            for page in paginator.paginate():
                for table_name in page.get('TableNames', []):
                    if self.project_name.lower() in table_name.lower():
                        try:
                            # Get table ARN
                            table_desc = dynamodb.describe_table(TableName=table_name)
                            table_arn = table_desc['Table']['TableArn']
                            
                            # Check tags
                            tags_response = dynamodb.list_tags_of_resource(ResourceArn=table_arn)
                            tags = {tag['Key']: tag['Value'] for tag in tags_response.get('Tags', [])}
                            
                            if tags.get('Project') != self.project_name:
                                untagged.append(f"DynamoDB: {table_name} (missing/incorrect Project tag)")
                        except:
                            pass
        except Exception as e:
            print(f"  ⚠️  Could not check DynamoDB tables: {e}")
        
        return untagged
    
    def _check_s3_tags(self) -> List[str]:
        """Check S3 buckets for missing tags."""
        untagged = []
        try:
            s3 = self.session.client('s3')
            
            # List all buckets
            buckets_response = s3.list_buckets()
            
            for bucket in buckets_response.get('Buckets', []):
                bucket_name = bucket['Name']
                if self.project_name.lower() in bucket_name.lower():
                    try:
                        # Get bucket tags
                        tags_response = s3.get_bucket_tagging(Bucket=bucket_name)
                        tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagSet', [])}
                        
                        if tags.get('Project') != self.project_name:
                            untagged.append(f"S3: {bucket_name} (missing/incorrect Project tag)")
                    except s3.exceptions.NoSuchTagSet:
                        untagged.append(f"S3: {bucket_name} (no tags)")
                    except:
                        pass
        except Exception as e:
            print(f"  ⚠️  Could not check S3 buckets: {e}")
        
        return untagged
    
    def _print_optimization_tips(self, services: Dict[str, float]) -> None:
        """Print cost optimization tips based on services used."""
        print("\n💡 Cost Optimization Tips:")
        
        tips = []
        
        # Lambda tips
        if 'AWSLambda' in services or 'Lambda' in services:
            tips.extend([
                "Review Lambda function memory settings and execution times",
                "Consider using Lambda Reserved Concurrency for predictable workloads",
                "Enable Lambda function URL instead of API Gateway for simple APIs"
            ])
        
        # DynamoDB tips
        if 'AmazonDynamoDB' in services or 'DynamoDB' in services:
            tips.extend([
                "Check for unused DynamoDB capacity or consider on-demand pricing",
                "Review DynamoDB auto-scaling settings",
                "Consider using DynamoDB TTL to automatically delete old items"
            ])
        
        # S3 tips
        if 'AmazonS3' in services or 'S3' in services:
            tips.extend([
                "Clean up old S3 objects and enable lifecycle policies",
                "Use S3 Intelligent-Tiering for infrequently accessed data",
                "Enable S3 Transfer Acceleration only where needed"
            ])
        
        # CloudFront tips
        if 'AmazonCloudFront' in services or 'CloudFront' in services:
            tips.extend([
                "Monitor CloudFront cache hit ratios",
                "Review CloudFront distribution settings and remove unused ones",
                "Consider using CloudFront compression"
            ])
        
        # CloudWatch tips
        if 'AmazonCloudWatch' in services or 'CloudWatch' in services:
            tips.extend([
                "Review CloudWatch Logs retention periods",
                "Remove unused CloudWatch dashboards and alarms",
                "Consider using CloudWatch Logs Insights instead of third-party tools"
            ])
        
        # API Gateway tips
        if 'AmazonAPIGateway' in services or 'APIGateway' in services:
            tips.extend([
                "Consider caching API Gateway responses",
                "Review API Gateway throttling settings",
                "Use Lambda function URLs for simple APIs instead of API Gateway"
            ])
        
        # General tips
        tips.extend([
            "Tag all resources consistently for better cost allocation",
            "Set up AWS Budgets with alerts for cost control",
            "Use AWS Cost Anomaly Detection to catch unusual spending",
            "Review and remove unused resources regularly"
        ])
        
        # Print unique tips (max 5)
        seen = set()
        count = 0
        for tip in tips:
            if tip not in seen and count < 5:
                print(f"  • {tip}")
                seen.add(tip)
                count += 1


def main():
    """Main entry point for the cost checker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check AWS costs for a project")
    parser.add_argument("project", nargs="?", help="Project name (or use --project)")
    parser.add_argument("--project", "-p", dest="project_flag", help="Project name")
    parser.add_argument("--days", "-d", type=int, default=7, help="Number of days to analyze (default: 7)")
    parser.add_argument("--profile", dest="aws_profile", help="AWS profile to use")
    parser.add_argument("--region", "-r", default="us-west-1", help="AWS region (default: us-west-1)")
    parser.add_argument("--budget", "-b", type=float, help="Monthly budget for comparison")
    parser.add_argument("--check-tags", "-t", action="store_true", help="Check for untagged resources")
    parser.add_argument("--json", "-j", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    # Get project name from either positional or flag argument
    project_name = args.project or args.project_flag
    if not project_name:
        # Try to detect from current directory
        cwd = os.getcwd()
        if 'people-cards' in cwd:
            project_name = 'people-cards'
        elif 'fraud-or-not' in cwd:
            project_name = 'fraud-or-not'
        elif 'media-register' in cwd:
            project_name = 'media-register'
        else:
            print("❌ Error: Project name required")
            print("Usage: check-costs <project-name> [options]")
            print("   or: check-costs --project <project-name> [options]")
            sys.exit(1)
    
    if not args.json:
        print(f"🔍 AWS Cost Monitor")
        print("=" * 60)
    
    try:
        # Create cost checker
        checker = ProjectCostChecker(
            project_name=project_name,
            region=args.region,
            profile=args.aws_profile
        )
        
        # Get costs
        results = checker.get_costs(days=args.days, budget=args.budget)
        
        # Check tags if requested
        if args.check_tags:
            untagged = checker.check_untagged_resources()
            results["untagged_resources"] = untagged
        
        # Output JSON if requested
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print("\n✨ Done!")
            
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}")
            print("\nMake sure you have AWS credentials configured:")
            print("  - Run: aws configure")
            print("  - Or set AWS_PROFILE environment variable")
            print("  - Or use --profile option")
        sys.exit(1)


if __name__ == "__main__":
    main()