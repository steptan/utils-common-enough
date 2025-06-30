"""Cost analysis for AWS resources."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

import boto3
from botocore.exceptions import ClientError

from ..config import ProjectConfig


class CostAnalyzer:
    """Analyze AWS costs for projects."""
    
    def __init__(
        self,
        config: ProjectConfig,
        aws_profile: Optional[str] = None
    ):
        """
        Initialize cost analyzer.
        
        Args:
            config: Project configuration
            aws_profile: AWS profile to use
        """
        self.config = config
        self.project_name = config.name
        
        # Initialize AWS clients
        session_args = {"region_name": "us-east-1"}  # Cost Explorer only works in us-east-1
        if aws_profile:
            session_args["profile_name"] = aws_profile
            
        session = boto3.Session(**session_args)
        self.ce = session.client("ce")
        self.cloudwatch = session.client("cloudwatch", region_name=config.aws_region)
        self.pricing = session.client("pricing", region_name="us-east-1")
        
    def get_project_costs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "DAILY"
    ) -> Dict[str, Any]:
        """
        Get costs for the project.
        
        Args:
            start_date: Start date for cost analysis
            end_date: End date for cost analysis
            granularity: Cost granularity (DAILY, MONTHLY)
            
        Returns:
            Cost data for the project
        """
        # Default to last 30 days
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        # Format dates
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        print(f"💰 Analyzing costs for {self.project_name} ({start_str} to {end_str})")
        
        try:
            # Get cost and usage
            response = self.ce.get_cost_and_usage(
                TimePeriod={
                    "Start": start_str,
                    "End": end_str
                },
                Granularity=granularity,
                Metrics=["UnblendedCost", "UsageQuantity"],
                Filter={
                    "Tags": {
                        "Key": "Project",
                        "Values": [self.project_name]
                    }
                },
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "DIMENSION", "Key": "USAGE_TYPE"}
                ]
            )
            
            return self._process_cost_data(response)
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "DataUnavailable":
                print("⚠️  Cost data not yet available for this time period")
                return {"total_cost": 0, "services": {}, "daily_costs": []}
            raise
    
    def get_service_breakdown(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Get cost breakdown by AWS service.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Dictionary of service costs
        """
        costs = self.get_project_costs(start_date, end_date, "MONTHLY")
        return costs.get("services", {})
    
    def get_resource_costs(self, environment: str = "prod") -> Dict[str, Dict[str, float]]:
        """
        Get costs for specific resources.
        
        Args:
            environment: Environment to analyze
            
        Returns:
            Resource-level cost breakdown
        """
        print(f"📊 Analyzing resource costs for {self.project_name}-{environment}")
        
        # Get tagged resources
        resources = self._get_tagged_resources(environment)
        
        # Analyze costs for each resource type
        resource_costs = {
            "lambda": self._analyze_lambda_costs(resources.get("lambda", []), environment),
            "dynamodb": self._analyze_dynamodb_costs(resources.get("dynamodb", []), environment),
            "s3": self._analyze_s3_costs(resources.get("s3", []), environment),
            "cloudfront": self._analyze_cloudfront_costs(resources.get("cloudfront", []), environment),
            "api_gateway": self._analyze_apigateway_costs(resources.get("apigateway", []), environment)
        }
        
        return resource_costs
    
    def get_cost_forecast(self, days: int = 30) -> Dict[str, Any]:
        """
        Forecast future costs based on historical data.
        
        Args:
            days: Number of days to forecast
            
        Returns:
            Cost forecast data
        """
        print(f"🔮 Forecasting costs for next {days} days")
        
        # Get historical data for trend analysis
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 3 months of history
        
        historical = self.get_project_costs(start_date, end_date, "DAILY")
        
        # Simple linear regression for forecast
        daily_costs = historical.get("daily_costs", [])
        if len(daily_costs) < 7:
            return {"error": "Insufficient historical data for forecast"}
        
        # Calculate average daily cost and trend
        recent_costs = [day["cost"] for day in daily_costs[-30:]]
        avg_daily_cost = sum(recent_costs) / len(recent_costs)
        
        # Calculate trend (increase/decrease rate)
        first_week_avg = sum(recent_costs[:7]) / 7
        last_week_avg = sum(recent_costs[-7:]) / 7
        weekly_trend = (last_week_avg - first_week_avg) / first_week_avg if first_week_avg > 0 else 0
        
        # Generate forecast
        forecast = {
            "current_daily_average": round(avg_daily_cost, 2),
            "weekly_trend_percent": round(weekly_trend * 100, 2),
            "forecast_days": days,
            "projected_cost": round(avg_daily_cost * days * (1 + weekly_trend * days / 7), 2),
            "confidence": "medium" if len(daily_costs) > 30 else "low"
        }
        
        return forecast
    
    def get_cost_anomalies(self, threshold_percent: float = 50) -> List[Dict[str, Any]]:
        """
        Detect cost anomalies.
        
        Args:
            threshold_percent: Percentage threshold for anomaly detection
            
        Returns:
            List of detected anomalies
        """
        print(f"🚨 Detecting cost anomalies (threshold: {threshold_percent}%)")
        
        # Get daily costs for last 30 days
        costs = self.get_project_costs(granularity="DAILY")
        daily_costs = costs.get("daily_costs", [])
        
        if len(daily_costs) < 7:
            return []
        
        anomalies = []
        
        # Calculate rolling average
        window_size = 7
        for i in range(window_size, len(daily_costs)):
            # Get previous week average
            prev_week = daily_costs[i-window_size:i]
            avg_cost = sum(day["cost"] for day in prev_week) / window_size
            
            # Check current day
            current = daily_costs[i]
            if avg_cost > 0:
                change_percent = ((current["cost"] - avg_cost) / avg_cost) * 100
                
                if abs(change_percent) > threshold_percent:
                    anomalies.append({
                        "date": current["date"],
                        "cost": current["cost"],
                        "expected_cost": round(avg_cost, 2),
                        "change_percent": round(change_percent, 2),
                        "services": current.get("services", {})
                    })
        
        return anomalies
    
    def _process_cost_data(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw cost data from Cost Explorer."""
        results = response.get("ResultsByTime", [])
        
        # Aggregate by service
        service_costs = defaultdict(float)
        daily_costs = []
        total_cost = 0
        
        for result in results:
            daily_total = 0
            daily_services = defaultdict(float)
            
            for group in result.get("Groups", []):
                service = group["Keys"][0]  # SERVICE dimension
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                
                service_costs[service] += cost
                daily_services[service] += cost
                daily_total += cost
                total_cost += cost
            
            daily_costs.append({
                "date": result["TimePeriod"]["Start"],
                "cost": round(daily_total, 2),
                "services": dict(daily_services)
            })
        
        return {
            "total_cost": round(total_cost, 2),
            "services": {k: round(v, 2) for k, v in service_costs.items()},
            "daily_costs": daily_costs,
            "period": {
                "start": results[0]["TimePeriod"]["Start"] if results else None,
                "end": results[-1]["TimePeriod"]["End"] if results else None
            }
        }
    
    def _get_tagged_resources(self, environment: str) -> Dict[str, List[str]]:
        """Get resources tagged with project and environment."""
        # This would use Resource Groups Tagging API
        # Simplified for example
        return {
            "lambda": [f"{self.project_name}-{environment}-api"],
            "dynamodb": [f"{self.project_name}-{environment}-table"],
            "s3": [f"{self.project_name}-{environment}-assets"],
            "cloudfront": [f"{self.project_name}-{environment}-distribution"],
            "apigateway": [f"{self.project_name}-{environment}-api"]
        }
    
    def _analyze_lambda_costs(self, functions: List[str], environment: str) -> Dict[str, float]:
        """Analyze Lambda function costs."""
        costs = {}
        
        for function in functions:
            # Get invocation metrics
            try:
                invocations = self._get_metric_sum("AWS/Lambda", "Invocations", 
                                                  {"FunctionName": function})
                duration = self._get_metric_avg("AWS/Lambda", "Duration",
                                               {"FunctionName": function})
                
                # Estimate cost (simplified)
                # $0.20 per 1M requests, $0.0000166667 per GB-second
                request_cost = (invocations / 1_000_000) * 0.20
                compute_cost = (invocations * duration / 1000 * 512 / 1024) * 0.0000166667
                
                costs[function] = round(request_cost + compute_cost, 2)
                
            except Exception:
                costs[function] = 0
        
        return costs
    
    def _analyze_dynamodb_costs(self, tables: List[str], environment: str) -> Dict[str, float]:
        """Analyze DynamoDB table costs."""
        # Simplified - would use actual metrics
        return {table: 0.25 for table in tables}  # Minimum cost estimate
    
    def _analyze_s3_costs(self, buckets: List[str], environment: str) -> Dict[str, float]:
        """Analyze S3 bucket costs."""
        # Simplified - would use actual metrics
        return {bucket: 0.023 for bucket in buckets}  # Storage cost estimate
    
    def _analyze_cloudfront_costs(self, distributions: List[str], environment: str) -> Dict[str, float]:
        """Analyze CloudFront distribution costs."""
        # Simplified - would use actual metrics
        return {dist: 0.085 for dist in distributions}  # Data transfer estimate
    
    def _analyze_apigateway_costs(self, apis: List[str], environment: str) -> Dict[str, float]:
        """Analyze API Gateway costs."""
        # Simplified - would use actual metrics
        return {api: 0.035 for api in apis}  # Request cost estimate
    
    def _get_metric_sum(self, namespace: str, metric_name: str, dimensions: Dict[str, str]) -> float:
        """Get sum of CloudWatch metric."""
        response = self.cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[{"Name": k, "Value": v} for k, v in dimensions.items()],
            StartTime=datetime.now() - timedelta(days=1),
            EndTime=datetime.now(),
            Period=86400,
            Statistics=["Sum"]
        )
        
        datapoints = response.get("Datapoints", [])
        return sum(dp["Sum"] for dp in datapoints)
    
    def _get_metric_avg(self, namespace: str, metric_name: str, dimensions: Dict[str, str]) -> float:
        """Get average of CloudWatch metric."""
        response = self.cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[{"Name": k, "Value": v} for k, v in dimensions.items()],
            StartTime=datetime.now() - timedelta(days=1),
            EndTime=datetime.now(),
            Period=86400,
            Statistics=["Average"]
        )
        
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return 0
        return sum(dp["Average"] for dp in datapoints) / len(datapoints)