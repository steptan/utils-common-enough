"""Cost monitoring and alerts."""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from config import ProjectConfig

from .analyzer import CostAnalyzer


class CostMonitor:
    """Monitor AWS costs and set up alerts."""

    def __init__(self, config: ProjectConfig, aws_profile: Optional[str] = None):
        """
        Initialize cost monitor.

        Args:
            config: Project configuration
            aws_profile: AWS profile to use
        """
        self.config = config
        self.project_name = config.name

        # Initialize AWS clients
        session_args = {"region_name": config.aws_region}
        if aws_profile:
            session_args["profile_name"] = aws_profile

        session = boto3.Session(**session_args)
        self.cloudwatch = session.client("cloudwatch")
        self.sns = session.client("sns")
        self.budgets = session.client("budgets")

        # Initialize cost analyzer
        self.analyzer = CostAnalyzer(config, aws_profile)

        # Get account ID
        sts = session.client("sts")
        self.account_id = sts.get_caller_identity()["Account"]

    def create_budget_alert(
        self,
        budget_amount: float,
        environment: str = "prod",
        notification_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a budget alert for the project.

        Args:
            budget_amount: Monthly budget amount in USD
            environment: Environment to monitor
            notification_email: Email for notifications

        Returns:
            Budget creation result
        """
        budget_name = f"{self.project_name}-{environment}-budget"

        print(f"💸 Creating budget alert: ${budget_amount}/month for {budget_name}")

        # Create or get SNS topic
        topic_arn = self._get_or_create_sns_topic(f"{self.project_name}-cost-alerts")

        if notification_email:
            self._subscribe_email_to_topic(topic_arn, notification_email)

        try:
            # Create budget
            response = self.budgets.create_budget(
                AccountId=self.account_id,
                Budget={
                    "BudgetName": budget_name,
                    "BudgetLimit": {"Amount": str(budget_amount), "Unit": "USD"},
                    "TimeUnit": "MONTHLY",
                    "BudgetType": "COST",
                    "CostFilters": {"TagKeyValue": [f"Project${self.project_name}"]},
                    "CostTypes": {
                        "IncludeTax": True,
                        "IncludeSubscription": True,
                        "UseBlended": False,
                        "IncludeRefund": False,
                        "IncludeCredit": False,
                    },
                },
                NotificationsWithSubscribers=[
                    {
                        "Notification": {
                            "NotificationType": "ACTUAL",
                            "ComparisonOperator": "GREATER_THAN",
                            "Threshold": 80,
                            "ThresholdType": "PERCENTAGE",
                        },
                        "Subscribers": [
                            {"SubscriptionType": "SNS", "Address": topic_arn}
                        ],
                    },
                    {
                        "Notification": {
                            "NotificationType": "ACTUAL",
                            "ComparisonOperator": "GREATER_THAN",
                            "Threshold": 100,
                            "ThresholdType": "PERCENTAGE",
                        },
                        "Subscribers": [
                            {"SubscriptionType": "SNS", "Address": topic_arn}
                        ],
                    },
                ],
            )

            print("✅ Budget alert created successfully")
            return {
                "budget_name": budget_name,
                "amount": budget_amount,
                "topic_arn": topic_arn,
                "status": "created",
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "DuplicateRecordException":
                print(f"⚠️  Budget {budget_name} already exists")
                return {
                    "budget_name": budget_name,
                    "amount": budget_amount,
                    "topic_arn": topic_arn,
                    "status": "exists",
                }
            raise

    def create_anomaly_detector(
        self, threshold_percentage: float = 50, notification_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create cost anomaly detector.

        Args:
            threshold_percentage: Anomaly threshold percentage
            notification_email: Email for notifications

        Returns:
            Anomaly detector details
        """
        print(f"🔍 Creating anomaly detector for {self.project_name}")

        # Create CloudWatch alarm for cost anomalies
        alarm_name = f"{self.project_name}-cost-anomaly"

        # Get or create SNS topic
        topic_arn = self._get_or_create_sns_topic(f"{self.project_name}-cost-alerts")

        if notification_email:
            self._subscribe_email_to_topic(topic_arn, notification_email)

        # Create custom metric for cost tracking
        self._put_cost_metric()

        # Create alarm
        try:
            self.cloudwatch.put_metric_alarm(
                AlarmName=alarm_name,
                ComparisonOperator="GreaterThanThreshold",
                EvaluationPeriods=1,
                MetricName=f"{self.project_name}-daily-cost",
                Namespace="ProjectCosts",
                Period=86400,  # Daily
                Statistic="Average",
                Threshold=threshold_percentage,
                ActionsEnabled=True,
                AlarmActions=[topic_arn],
                AlarmDescription=f"Cost anomaly detection for {self.project_name}",
                TreatMissingData="notBreaching",
            )

            print("✅ Anomaly detector created")
            return {
                "alarm_name": alarm_name,
                "threshold": threshold_percentage,
                "topic_arn": topic_arn,
                "status": "created",
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceAlreadyExists":
                print("⚠️  Anomaly detector already exists")
                return {
                    "alarm_name": alarm_name,
                    "threshold": threshold_percentage,
                    "topic_arn": topic_arn,
                    "status": "exists",
                }
            raise

    def create_resource_alerts(
        self, thresholds: Dict[str, Dict[str, float]], environment: str = "prod"
    ) -> List[Dict[str, Any]]:
        """
        Create alerts for specific resource costs.

        Args:
            thresholds: Resource thresholds (e.g., {"lambda": {"invocations": 1000000}})
            environment: Environment to monitor

        Returns:
            List of created alerts
        """
        alerts = []

        for resource_type, metrics in thresholds.items():
            for metric_name, threshold in metrics.items():
                alert = self._create_resource_alert(
                    resource_type, metric_name, threshold, environment
                )
                alerts.append(alert)

        return alerts

    def get_budget_status(self, environment: str = "prod") -> Dict[str, Any]:
        """
        Get current budget status.

        Args:
            environment: Environment to check

        Returns:
            Budget status information
        """
        budget_name = f"{self.project_name}-{environment}-budget"

        try:
            response = self.budgets.describe_budget(
                AccountId=self.account_id, BudgetName=budget_name
            )

            budget = response["Budget"]

            # Get current spend
            current_costs = self.analyzer.get_project_costs(
                start_date=datetime.now().replace(day=1), end_date=datetime.now()
            )

            budget_amount = float(budget["BudgetLimit"]["Amount"])
            current_spend = current_costs["total_cost"]
            percentage_used = (
                (current_spend / budget_amount * 100) if budget_amount > 0 else 0
            )

            return {
                "budget_name": budget_name,
                "budget_amount": budget_amount,
                "current_spend": current_spend,
                "percentage_used": round(percentage_used, 2),
                "remaining": round(budget_amount - current_spend, 2),
                "status": self._get_budget_status(percentage_used),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                return {"error": f"Budget {budget_name} not found"}
            raise

    def _get_or_create_sns_topic(self, topic_name: str) -> str:
        """Get or create SNS topic."""
        try:
            response = self.sns.create_topic(Name=topic_name)
            return response["TopicArn"]
        except ClientError:
            # Topic might already exist
            response = self.sns.list_topics()
            for topic in response["Topics"]:
                if topic_name in topic["TopicArn"]:
                    return topic["TopicArn"]
            raise

    def _subscribe_email_to_topic(self, topic_arn: str, email: str) -> None:
        """Subscribe email to SNS topic."""
        try:
            self.sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
            print(f"📧 Subscription request sent to {email}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidParameter":
                raise

    def _put_cost_metric(self) -> None:
        """Put custom cost metric to CloudWatch."""
        # Get yesterday's cost
        yesterday = datetime.now() - timedelta(days=1)
        costs = self.analyzer.get_project_costs(
            start_date=yesterday, end_date=datetime.now(), granularity="DAILY"
        )

        if costs["daily_costs"]:
            daily_cost = costs["daily_costs"][-1]["cost"]

            self.cloudwatch.put_metric_data(
                Namespace="ProjectCosts",
                MetricData=[
                    {
                        "MetricName": f"{self.project_name}-daily-cost",
                        "Value": daily_cost,
                        "Unit": "Count",
                        "Timestamp": datetime.now(),
                    }
                ],
            )

    def _create_resource_alert(
        self, resource_type: str, metric_name: str, threshold: float, environment: str
    ) -> Dict[str, Any]:
        """Create alert for specific resource metric."""
        alarm_name = f"{self.project_name}-{environment}-{resource_type}-{metric_name}"

        # Map resource types to CloudWatch namespaces
        namespace_map = {
            "lambda": "AWS/Lambda",
            "dynamodb": "AWS/DynamoDB",
            "s3": "AWS/S3",
            "cloudfront": "AWS/CloudFront",
            "apigateway": "AWS/ApiGateway",
        }

        namespace = namespace_map.get(resource_type, "AWS/Lambda")

        # Create alarm
        self.cloudwatch.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator="GreaterThanThreshold",
            EvaluationPeriods=1,
            MetricName=metric_name,
            Namespace=namespace,
            Period=3600,  # Hourly
            Statistic="Sum",
            Threshold=threshold,
            ActionsEnabled=True,
            AlarmDescription=f"Alert for {resource_type} {metric_name}",
            TreatMissingData="notBreaching",
        )

        return {
            "alarm_name": alarm_name,
            "resource_type": resource_type,
            "metric": metric_name,
            "threshold": threshold,
        }

    def _get_budget_status(self, percentage: float) -> str:
        """Get budget status based on percentage used."""
        if percentage >= 100:
            return "EXCEEDED"
        elif percentage >= 80:
            return "WARNING"
        elif percentage >= 50:
            return "NORMAL"
        else:
            return "GOOD"
