"""
CloudFormation stack diagnostics and troubleshooting.
"""

import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from .stack_manager import StackManager


class StackDiagnostics:
    """Diagnose CloudFormation stack issues."""
    
    def __init__(self, stack_manager: StackManager):
        """Initialize diagnostics with a stack manager."""
        self.stack_manager = stack_manager
        self.cloudformation = stack_manager.cloudformation
    
    def generate_report(self, stack_name: str) -> str:
        """Generate a comprehensive diagnostic report for a stack."""
        report = []
        report.append(f"🔍 CloudFormation Stack Diagnostic Report")
        report.append(f"Stack: {stack_name}")
        report.append(f"Time: {datetime.now().isoformat()}")
        report.append("=" * 80)
        
        # Get basic diagnosis
        diagnosis = self.stack_manager.diagnose_stack_failure(stack_name)
        
        if not diagnosis["status"]:
            report.append("\n❌ Stack does not exist")
            return "\n".join(report)
        
        # Stack status
        report.append(f"\n📊 Stack Status: {diagnosis['status']}")
        
        # Get detailed stack info
        try:
            stack_info = self.cloudformation.describe_stacks(StackName=stack_name)
            if stack_info["Stacks"]:
                stack = stack_info["Stacks"][0]
                
                # Basic info
                report.append(f"\nStack Information:")
                report.append(f"  Created: {stack['CreationTime']}")
                if "LastUpdatedTime" in stack:
                    report.append(f"  Last Updated: {stack['LastUpdatedTime']}")
                if "StatusReason" in stack:
                    report.append(f"  Status Reason: {stack['StatusReason']}")
                
                # Parameters
                if stack.get("Parameters"):
                    report.append(f"\nParameters:")
                    for param in stack["Parameters"]:
                        report.append(f"  {param['ParameterKey']}: {param['ParameterValue']}")
                
                # Tags
                if stack.get("Tags"):
                    report.append(f"\nTags:")
                    for tag in stack["Tags"]:
                        report.append(f"  {tag['Key']}: {tag['Value']}")
        except Exception as e:
            report.append(f"\n⚠️  Error getting stack details: {e}")
        
        # Failed resources
        if diagnosis["failed_resources"]:
            report.append(f"\n❌ Failed Resources ({len(diagnosis['failed_resources'])})")
            for resource in diagnosis["failed_resources"]:
                report.append(f"\n  Resource: {resource['logical_id']}")
                report.append(f"  Type: {resource['resource_type']}")
                report.append(f"  Status: {resource['status']}")
                report.append(f"  Reason: {resource['reason']}")
                report.append(f"  Time: {resource['timestamp']}")
        
        # Resources preventing deletion
        if diagnosis["rollback_triggers"]:
            report.append(f"\n🚫 Resources Preventing Deletion:")
            for trigger in diagnosis["rollback_triggers"]:
                report.append(f"\n  Resource: {trigger['logical_id']}")
                report.append(f"  Type: {trigger['resource_type']}")
                report.append(f"  Physical ID: {trigger['physical_id']}")
        
        # Recent events timeline
        report.append("\n📅 Recent Events (Last 10):")
        events = self.get_recent_events(stack_name, limit=10)
        for event in events:
            status_emoji = self._get_status_emoji(event["ResourceStatus"])
            report.append(
                f"  {status_emoji} {event['Timestamp'].strftime('%H:%M:%S')} - "
                f"{event['LogicalResourceId']} ({event['ResourceStatus']})"
            )
            if event.get("ResourceStatusReason"):
                report.append(f"    → {event['ResourceStatusReason']}")
        
        # Recommendations
        if diagnosis["recommendations"]:
            report.append(f"\n💡 Recommendations:")
            for i, rec in enumerate(diagnosis["recommendations"], 1):
                report.append(f"  {i}. {rec}")
        
        # Common solutions
        report.extend(self._get_common_solutions(diagnosis["status"]))
        
        return "\n".join(report)
    
    def get_recent_events(
        self,
        stack_name: str,
        limit: int = 20,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get recent stack events."""
        events = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        try:
            paginator = self.cloudformation.get_paginator("describe_stack_events")
            
            for page in paginator.paginate(StackName=stack_name):
                for event in page["StackEvents"]:
                    # Convert timestamp for comparison
                    event_time = event["Timestamp"].replace(tzinfo=None)
                    if event_time < cutoff_time:
                        break
                    
                    events.append({
                        "Timestamp": event["Timestamp"],
                        "LogicalResourceId": event["LogicalResourceId"],
                        "ResourceType": event["ResourceType"],
                        "ResourceStatus": event["ResourceStatus"],
                        "ResourceStatusReason": event.get("ResourceStatusReason"),
                        "PhysicalResourceId": event.get("PhysicalResourceId")
                    })
                    
                    if len(events) >= limit:
                        return events
                        
        except Exception as e:
            print(f"Error getting events: {e}")
        
        return events[:limit]
    
    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for resource status."""
        if "COMPLETE" in status and "ROLLBACK" not in status:
            return "✅"
        elif "FAILED" in status:
            return "❌"
        elif "IN_PROGRESS" in status:
            return "🔄"
        elif "ROLLBACK" in status:
            return "↩️"
        else:
            return "•"
    
    def _get_common_solutions(self, status: str) -> List[str]:
        """Get common solutions based on stack status."""
        solutions = ["\n🛠️  Common Solutions:"]
        
        if status == "ROLLBACK_COMPLETE":
            solutions.extend([
                "  1. The stack failed during creation and rolled back",
                "  2. Run: project-cfn fix-rollback --stack-name <name>",
                "  3. Or delete with: project-cfn delete --stack-name <name>"
            ])
        
        elif status == "ROLLBACK_FAILED":
            solutions.extend([
                "  1. Manual intervention required",
                "  2. Check failed resources above",
                "  3. Fix or skip resources: project-cfn fix-rollback --stack-name <name> --skip-resources <id1,id2>",
                "  4. May need to manually delete resources in AWS console"
            ])
        
        elif status == "DELETE_FAILED":
            solutions.extend([
                "  1. Resources are preventing deletion",
                "  2. Common causes: non-empty S3 buckets, ENIs from Lambda",
                "  3. Force delete: project-cfn delete --stack-name <name> --force",
                "  4. Or manually clean up resources listed above"
            ])
        
        elif status == "UPDATE_ROLLBACK_COMPLETE":
            solutions.extend([
                "  1. The last update failed and was rolled back",
                "  2. Review the failed resources above",
                "  3. Fix the issues and try updating again",
                "  4. Consider updating in smaller batches"
            ])
        
        elif "IN_PROGRESS" in status:
            solutions.extend([
                "  1. Operation is still in progress",
                "  2. Monitor with: project-cfn status --stack-name <name> --watch",
                "  3. Check CloudWatch logs for Lambda functions",
                "  4. Some resources (like CloudFront) can take 15-30 minutes"
            ])
        
        return solutions
    
    def analyze_drift(self, stack_name: str) -> Dict[str, Any]:
        """Analyze stack drift (differences between template and actual resources)."""
        drift_info = {
            "stack_name": stack_name,
            "drift_status": "UNKNOWN",
            "drifted_resources": []
        }
        
        try:
            # Initiate drift detection
            print("🔍 Initiating drift detection...")
            response = self.cloudformation.detect_stack_drift(StackName=stack_name)
            drift_id = response["StackDriftDetectionId"]
            
            # Wait for drift detection to complete
            print("⏳ Waiting for drift detection to complete...")
            while True:
                status_response = self.cloudformation.describe_stack_drift_detection_status(
                    StackDriftDetectionId=drift_id
                )
                
                status = status_response["DetectionStatus"]
                if status == "DETECTION_COMPLETE":
                    drift_info["drift_status"] = status_response["StackDriftStatus"]
                    break
                elif status == "DETECTION_FAILED":
                    drift_info["error"] = status_response.get("DetectionStatusReason", "Unknown error")
                    return drift_info
                
                time.sleep(5)
            
            # Get drift details if drifted
            if drift_info["drift_status"] == "DRIFTED":
                resources = self.cloudformation.describe_stack_resource_drifts(
                    StackName=stack_name,
                    StackResourceDriftStatusFilters=["MODIFIED", "DELETED"]
                )
                
                for resource in resources["StackResourceDrifts"]:
                    drift_detail = {
                        "logical_id": resource["LogicalResourceId"],
                        "resource_type": resource["ResourceType"],
                        "drift_status": resource["StackResourceDriftStatus"],
                        "differences": []
                    }
                    
                    # Parse property differences
                    if resource.get("PropertyDifferences"):
                        for diff in resource["PropertyDifferences"]:
                            drift_detail["differences"].append({
                                "property": diff["PropertyPath"],
                                "expected": diff["ExpectedValue"],
                                "actual": diff["ActualValue"],
                                "change_type": diff["DifferenceType"]
                            })
                    
                    drift_info["drifted_resources"].append(drift_detail)
            
        except Exception as e:
            drift_info["error"] = str(e)
        
        return drift_info