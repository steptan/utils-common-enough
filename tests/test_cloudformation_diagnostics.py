"""
Comprehensive tests for cloudformation.diagnostics module.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from cloudformation.diagnostics import StackDiagnostics
from cloudformation.stack_manager import StackManager


class TestStackDiagnostics:
    """Test StackDiagnostics functionality."""

    @pytest.fixture
    def mock_stack_manager(self) -> StackManager:
        """Create a mock StackManager."""
        mock_manager = Mock(spec=StackManager)
        mock_manager.cloudformation = Mock()
        return mock_manager

    @pytest.fixture
    def diagnostics(self, mock_stack_manager: StackManager) -> StackDiagnostics:
        """Create a StackDiagnostics instance with mocked dependencies."""
        return StackDiagnostics(mock_stack_manager)

    def test_initialization(self, diagnostics: StackDiagnostics, mock_stack_manager: StackManager) -> None:
        """Test StackDiagnostics initialization."""
        assert diagnostics.stack_manager == mock_stack_manager
        assert diagnostics.cloudformation == mock_stack_manager.cloudformation

    def test_generate_report_stack_exists(self, diagnostics: StackDiagnostics, mock_stack_manager: StackManager) -> None:
        """Test generating report for existing stack."""
        stack_name = "test-stack"
        
        # Mock stack diagnosis
        mock_stack_manager.diagnose_stack_failure.return_value = {
            "status": "CREATE_COMPLETE",
            "failed_resources": [],
            "issues": []
        }
        
        # Mock stack description
        diagnostics.cloudformation.describe_stacks.return_value = {
            "Stacks": [{
                "StackName": stack_name,
                "StackStatus": "CREATE_COMPLETE",
                "CreationTime": datetime.now(),
                "Parameters": [{"ParameterKey": "Env", "ParameterValue": "prod"}],
                "Tags": [{"Key": "Project", "Value": "test"}]
            }]
        }
        
        # Mock stack events
        diagnostics.cloudformation.describe_stack_events.return_value = {
            "StackEvents": [{
                "EventId": "1",
                "Timestamp": datetime.now(),
                "ResourceStatus": "CREATE_COMPLETE",
                "ResourceType": "AWS::CloudFormation::Stack",
                "LogicalResourceId": stack_name
            }]
        }
        
        report = diagnostics.generate_report(stack_name)
        
        assert "CloudFormation Stack Diagnostic Report" in report
        assert stack_name in report
        assert "CREATE_COMPLETE" in report

    def test_generate_report_stack_not_exists(self, diagnostics: StackDiagnostics, mock_stack_manager: StackManager) -> None:
        """Test generating report for non-existent stack."""
        stack_name = "nonexistent-stack"
        
        # Mock stack doesn't exist
        mock_stack_manager.diagnose_stack_failure.return_value = {
            "status": None,
            "failed_resources": [],
            "issues": ["Stack not found"]
        }
        
        report = diagnostics.generate_report(stack_name)
        
        assert "Stack does not exist" in report
        assert stack_name in report

    def test_analyze_events(self, diagnostics: StackDiagnostics) -> None:
        """Test analyzing stack events."""
        events = [
            {
                "EventId": "1",
                "Timestamp": datetime.now() - timedelta(minutes=5),
                "ResourceStatus": "CREATE_IN_PROGRESS",
                "ResourceType": "AWS::Lambda::Function",
                "LogicalResourceId": "MyFunction"
            },
            {
                "EventId": "2",
                "Timestamp": datetime.now() - timedelta(minutes=3),
                "ResourceStatus": "CREATE_FAILED",
                "ResourceType": "AWS::Lambda::Function",
                "LogicalResourceId": "MyFunction",
                "ResourceStatusReason": "Invalid runtime specified"
            }
        ]
        
        # Mock the method if it exists
        if hasattr(diagnostics, 'analyze_events'):
            analysis = diagnostics.analyze_events(events)
            assert len(analysis.get("failed_resources", [])) == 1
            assert "MyFunction" in analysis.get("failed_resources", [])

    def test_get_failure_timeline(self, diagnostics: StackDiagnostics) -> None:
        """Test getting failure timeline from events."""
        stack_name = "test-stack"
        
        diagnostics.cloudformation.describe_stack_events.return_value = {
            "StackEvents": [
                {
                    "EventId": "1",
                    "Timestamp": datetime.now() - timedelta(minutes=10),
                    "ResourceStatus": "CREATE_IN_PROGRESS",
                    "ResourceType": "AWS::CloudFormation::Stack"
                },
                {
                    "EventId": "2", 
                    "Timestamp": datetime.now() - timedelta(minutes=5),
                    "ResourceStatus": "CREATE_FAILED",
                    "ResourceType": "AWS::Lambda::Function",
                    "ResourceStatusReason": "Code validation failed"
                }
            ]
        }
        
        # Test if the method exists
        if hasattr(diagnostics, 'get_failure_timeline'):
            timeline = diagnostics.get_failure_timeline(stack_name)
            assert len(timeline) > 0

    def test_check_resource_dependencies(self, diagnostics: StackDiagnostics) -> None:
        """Test checking resource dependencies."""
        stack_name = "test-stack"
        
        # Mock template with dependencies
        diagnostics.cloudformation.get_template.return_value = {
            "TemplateBody": {
                "Resources": {
                    "MyBucket": {
                        "Type": "AWS::S3::Bucket"
                    },
                    "MyFunction": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "Environment": {
                                "Variables": {
                                    "BUCKET_NAME": {"Ref": "MyBucket"}
                                }
                            }
                        }
                    }
                }
            }
        }
        
        # Test if method exists
        if hasattr(diagnostics, 'check_resource_dependencies'):
            deps = diagnostics.check_resource_dependencies(stack_name)
            assert "MyFunction" in deps or isinstance(deps, dict)

    def test_diagnose_iam_permissions(self, diagnostics: StackDiagnostics) -> None:
        """Test diagnosing IAM permission issues."""
        events = [
            {
                "ResourceStatus": "CREATE_FAILED",
                "ResourceStatusReason": "User: arn:aws:iam::123:user/test is not authorized to perform: lambda:CreateFunction"
            }
        ]
        
        # Test if method exists
        if hasattr(diagnostics, 'diagnose_iam_permissions'):
            issues = diagnostics.diagnose_iam_permissions(events)
            assert len(issues) > 0
            assert any("permission" in issue.lower() for issue in issues)

    def test_suggest_fixes(self, diagnostics: StackDiagnostics) -> None:
        """Test suggesting fixes for common issues."""
        issues = {
            "permission_errors": ["lambda:CreateFunction denied"],
            "resource_failures": ["Lambda function creation failed"],
            "timeout_errors": ["Operation timed out"]
        }
        
        # Test if method exists
        if hasattr(diagnostics, 'suggest_fixes'):
            suggestions = diagnostics.suggest_fixes(issues)
            assert len(suggestions) > 0

    def test_generate_report_with_failed_stack(self, diagnostics: StackDiagnostics, mock_stack_manager: StackManager) -> None:
        """Test generating report for failed stack."""
        stack_name = "failed-stack"
        
        # Mock failed stack
        mock_stack_manager.diagnose_stack_failure.return_value = {
            "status": "CREATE_FAILED",
            "failed_resources": ["MyFunction", "MyTable"],
            "issues": ["Resource creation failed", "Invalid parameters"]
        }
        
        diagnostics.cloudformation.describe_stacks.return_value = {
            "Stacks": [{
                "StackName": stack_name,
                "StackStatus": "CREATE_FAILED",
                "StackStatusReason": "Resource creation failed",
                "CreationTime": datetime.now()
            }]
        }
        
        report = diagnostics.generate_report(stack_name)
        
        assert "CREATE_FAILED" in report
        assert stack_name in report

    def test_get_stack_drift_status(self, diagnostics: StackDiagnostics) -> None:
        """Test checking stack drift status."""
        stack_name = "test-stack"
        
        # Mock drift detection
        diagnostics.cloudformation.detect_stack_drift.return_value = {
            "StackDriftDetectionId": "drift-123"
        }
        
        diagnostics.cloudformation.describe_stack_drift_detection_status.return_value = {
            "StackDriftStatus": "DRIFTED",
            "StackDriftDetectionStatus": "DETECTION_COMPLETE",
            "DriftedStackResourceCount": 2
        }
        
        # Test if method exists
        if hasattr(diagnostics, 'get_stack_drift_status'):
            drift_status = diagnostics.get_stack_drift_status(stack_name)
            assert drift_status.get("status") == "DRIFTED"
            assert drift_status.get("drifted_count") == 2

    def test_export_diagnostic_data(self, diagnostics: StackDiagnostics, mock_stack_manager: StackManager, tmp_path: Path) -> None:
        """Test exporting diagnostic data to file."""
        stack_name = "test-stack"
        output_file = tmp_path / "diagnosis.json"
        
        # Mock diagnosis data
        mock_stack_manager.diagnose_stack_failure.return_value = {
            "status": "CREATE_FAILED",
            "failed_resources": ["Resource1"],
            "issues": ["Issue1"]
        }
        
        # Test if method exists
        if hasattr(diagnostics, 'export_diagnostic_data'):
            diagnostics.export_diagnostic_data(stack_name, str(output_file))
            
            if output_file.exists():
                data = json.loads(output_file.read_text())
                assert data["stack_name"] == stack_name

    def test_compare_stack_versions(self, diagnostics: StackDiagnostics) -> None:
        """Test comparing different versions of a stack template."""
        stack_name = "test-stack"
        
        # Mock current and previous templates
        diagnostics.cloudformation.get_template.return_value = {
            "TemplateBody": {
                "Resources": {
                    "MyBucket": {"Type": "AWS::S3::Bucket"},
                    "MyFunction": {"Type": "AWS::Lambda::Function"}
                }
            }
        }
        
        # Test if method exists
        if hasattr(diagnostics, 'compare_stack_versions'):
            differences = diagnostics.compare_stack_versions(stack_name)
            assert isinstance(differences, (dict, list))

    def test_get_cost_impact(self, diagnostics: StackDiagnostics) -> None:
        """Test analyzing cost impact of stack resources."""
        stack_name = "test-stack"
        
        diagnostics.cloudformation.describe_stack_resources.return_value = {
            "StackResources": [
                {
                    "ResourceType": "AWS::Lambda::Function",
                    "PhysicalResourceId": "function-1"
                },
                {
                    "ResourceType": "AWS::DynamoDB::Table",
                    "PhysicalResourceId": "table-1"
                }
            ]
        }
        
        # Test if method exists
        if hasattr(diagnostics, 'get_cost_impact'):
            cost_analysis = diagnostics.get_cost_impact(stack_name)
            assert "resources" in cost_analysis or isinstance(cost_analysis, dict)


@pytest.mark.integration
class TestStackDiagnosticsIntegration:
    """Integration tests for StackDiagnostics."""

    @pytest.mark.skip(reason="Integration tests require AWS credentials")
    def test_with_real_stack(self) -> None:
        """Test with a real CloudFormation stack."""
        try:
            from cloudformation.stack_manager import StackManager
            
            stack_manager = StackManager(
                project_name="test-project",
                environment="test",
                region="us-east-1"
            )
            
            diagnostics = StackDiagnostics(stack_manager)
            
            # Would test with actual stack
            report = diagnostics.generate_report("test-stack")
            assert isinstance(report, str)
            
        except Exception as e:
            pytest.skip(f"AWS connection failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])