"""Pre-deployment cost estimation for AWS resources."""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import boto3
from botocore.exceptions import ClientError


class ResourceType(Enum):
    """AWS resource types for cost estimation."""
    LAMBDA = "Lambda"
    DYNAMODB = "DynamoDB"
    S3 = "S3"
    CLOUDFRONT = "CloudFront"
    API_GATEWAY = "API Gateway"
    COGNITO = "Cognito"
    WAF = "WAF"
    CLOUDWATCH = "CloudWatch"
    VPC = "VPC"
    NAT_GATEWAY = "NAT Gateway"


@dataclass
class ResourceEstimate:
    """Cost estimate for a single resource."""
    resource_type: ResourceType
    resource_name: str
    monthly_cost_min: float
    monthly_cost_max: float
    cost_factors: Dict[str, Any]
    assumptions: List[str]


class CostEstimator:
    """Estimate costs for AWS resources before deployment."""
    
    # AWS Pricing (simplified, actual prices vary by region)
    PRICING = {
        ResourceType.LAMBDA: {
            "request_price": 0.20,  # per 1M requests
            "gb_second_price": 0.0000166667,  # per GB-second
            "free_requests": 1_000_000,
            "free_gb_seconds": 400_000
        },
        ResourceType.DYNAMODB: {
            "on_demand_write": 1.25,  # per 1M write units
            "on_demand_read": 0.25,   # per 1M read units
            "provisioned_write": 0.00065,  # per WCU per hour
            "provisioned_read": 0.00013,   # per RCU per hour
            "storage": 0.25,  # per GB per month
            "free_storage": 25  # GB
        },
        ResourceType.S3: {
            "storage_standard": 0.023,  # per GB per month
            "requests_put": 0.005,  # per 1000 requests
            "requests_get": 0.0004,  # per 1000 requests
            "data_transfer": 0.09,  # per GB (first 10TB)
            "free_storage": 5,  # GB
            "free_requests": 20_000  # GET requests
        },
        ResourceType.CLOUDFRONT: {
            "data_transfer_us": 0.085,  # per GB
            "data_transfer_eu": 0.085,
            "data_transfer_asia": 0.140,
            "requests_http": 0.0075,  # per 10K requests
            "requests_https": 0.0100,  # per 10K requests
            "free_data_transfer": 1024  # GB per month
        },
        ResourceType.API_GATEWAY: {
            "rest_api_requests": 3.50,  # per 1M requests
            "http_api_requests": 1.00,  # per 1M requests
            "websocket_messages": 1.00,  # per 1M messages
            "websocket_minutes": 0.25,  # per 1M connection minutes
            "free_requests": 1_000_000  # per month for 12 months
        },
        ResourceType.COGNITO: {
            "mau_tier1": 0.0055,  # per MAU (first 50K)
            "mau_tier2": 0.0046,  # per MAU (next 50K)
            "mau_tier3": 0.00325,  # per MAU (next 900K)
            "mau_tier4": 0.0025,   # per MAU (above 1M)
            "free_mau": 50_000
        },
        ResourceType.WAF: {
            "web_acl": 5.00,  # per month
            "rule": 1.00,     # per rule per month
            "requests": 0.60,  # per 1M requests
            "free_requests": 0
        },
        ResourceType.CLOUDWATCH: {
            "logs_ingestion": 0.50,  # per GB
            "logs_storage": 0.03,    # per GB per month
            "metrics": 0.30,         # per metric per month (first 10K)
            "alarms": 0.10,          # per alarm per month
            "free_metrics": 10,
            "free_alarms": 10,
            "free_logs_gb": 5
        },
        ResourceType.NAT_GATEWAY: {
            "hourly": 0.045,  # per hour
            "data_processing": 0.045  # per GB
        }
    }
    
    def __init__(self, project_name: str, environment: str, region: str = "us-west-1"):
        """Initialize cost estimator.
        
        Args:
            project_name: Name of the project
            environment: Deployment environment
            region: AWS region
        """
        self.project_name = project_name
        self.environment = environment
        self.region = region
        
        # Initialize pricing client if available
        try:
            self.pricing_client = boto3.client('pricing', region_name='us-east-1')
        except:
            self.pricing_client = None
    
    def estimate_stack_cost(self, template_path: str, 
                           parameters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Estimate costs for a CloudFormation stack.
        
        Args:
            template_path: Path to CloudFormation template
            parameters: Template parameters
            
        Returns:
            Cost estimation report
        """
        # Load template
        with open(template_path, 'r') as f:
            if template_path.endswith('.json'):
                template = json.load(f)
            else:
                import yaml
                template = yaml.safe_load(f)
        
        # Extract resources
        resources = template.get('Resources', {})
        
        # Estimate each resource
        estimates = []
        for logical_id, resource in resources.items():
            resource_type = resource.get('Type', '')
            properties = resource.get('Properties', {})
            
            estimate = self._estimate_resource(logical_id, resource_type, properties)
            if estimate:
                estimates.append(estimate)
        
        # Generate report
        return self._generate_cost_report(estimates)
    
    def estimate_application_cost(self, usage_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate costs based on usage profile.
        
        Args:
            usage_profile: Expected usage patterns
            
        Returns:
            Cost estimation report
        """
        estimates = []
        
        # API Gateway + Lambda
        if usage_profile.get('api_requests_per_month', 0) > 0:
            api_estimate = self._estimate_api_costs(usage_profile)
            estimates.extend(api_estimate)
        
        # DynamoDB
        if usage_profile.get('database_operations', {}):
            db_estimate = self._estimate_database_costs(usage_profile)
            estimates.append(db_estimate)
        
        # S3 Storage
        if usage_profile.get('storage_gb', 0) > 0:
            storage_estimate = self._estimate_storage_costs(usage_profile)
            estimates.append(storage_estimate)
        
        # CloudFront CDN
        if usage_profile.get('cdn_traffic_gb', 0) > 0:
            cdn_estimate = self._estimate_cdn_costs(usage_profile)
            estimates.append(cdn_estimate)
        
        # Cognito Auth
        if usage_profile.get('monthly_active_users', 0) > 0:
            auth_estimate = self._estimate_auth_costs(usage_profile)
            estimates.append(auth_estimate)
        
        # Monitoring
        monitoring_estimate = self._estimate_monitoring_costs(usage_profile)
        estimates.append(monitoring_estimate)
        
        return self._generate_cost_report(estimates)
    
    def _estimate_resource(self, logical_id: str, resource_type: str, 
                          properties: Dict[str, Any]) -> Optional[ResourceEstimate]:
        """Estimate cost for a single resource."""
        
        # Lambda Function
        if resource_type == 'AWS::Lambda::Function':
            return self._estimate_lambda_function(logical_id, properties)
        
        # DynamoDB Table
        elif resource_type == 'AWS::DynamoDB::Table':
            return self._estimate_dynamodb_table(logical_id, properties)
        
        # S3 Bucket
        elif resource_type == 'AWS::S3::Bucket':
            return self._estimate_s3_bucket(logical_id, properties)
        
        # API Gateway
        elif resource_type.startswith('AWS::ApiGateway'):
            return self._estimate_api_gateway(logical_id, properties)
        
        # CloudFront Distribution
        elif resource_type == 'AWS::CloudFront::Distribution':
            return self._estimate_cloudfront(logical_id, properties)
        
        # Cognito User Pool
        elif resource_type == 'AWS::Cognito::UserPool':
            return self._estimate_cognito(logical_id, properties)
        
        # WAF
        elif resource_type.startswith('AWS::WAFv2'):
            return self._estimate_waf(logical_id, properties)
        
        # NAT Gateway
        elif resource_type == 'AWS::EC2::NatGateway':
            return self._estimate_nat_gateway(logical_id, properties)
        
        return None
    
    def _estimate_lambda_function(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate Lambda function costs."""
        pricing = self.PRICING[ResourceType.LAMBDA]
        
        # Assumptions
        memory_mb = properties.get('MemorySize', 128)
        avg_duration_ms = 100  # Assumed average
        requests_per_month = 100_000  # Assumed
        
        # Calculate costs
        gb_seconds = (requests_per_month * avg_duration_ms / 1000) * (memory_mb / 1024)
        
        # Apply free tier
        billable_requests = max(0, requests_per_month - pricing['free_requests'])
        billable_gb_seconds = max(0, gb_seconds - pricing['free_gb_seconds'])
        
        request_cost = (billable_requests / 1_000_000) * pricing['request_price']
        compute_cost = billable_gb_seconds * pricing['gb_second_price']
        
        return ResourceEstimate(
            resource_type=ResourceType.LAMBDA,
            resource_name=name,
            monthly_cost_min=round(request_cost + compute_cost, 2),
            monthly_cost_max=round((request_cost + compute_cost) * 2, 2),  # 2x for peak
            cost_factors={
                'memory_mb': memory_mb,
                'requests_per_month': requests_per_month,
                'avg_duration_ms': avg_duration_ms
            },
            assumptions=[
                f"Assumed {requests_per_month:,} requests per month",
                f"Assumed {avg_duration_ms}ms average duration",
                "Free tier applied (1M requests, 400K GB-seconds)"
            ]
        )
    
    def _estimate_dynamodb_table(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate DynamoDB table costs."""
        pricing = self.PRICING[ResourceType.DYNAMODB]
        
        billing_mode = properties.get('BillingMode', 'PAY_PER_REQUEST')
        
        if billing_mode == 'PAY_PER_REQUEST':
            # On-demand pricing
            reads_per_month = 1_000_000  # Assumed
            writes_per_month = 100_000   # Assumed
            
            read_cost = (reads_per_month / 1_000_000) * pricing['on_demand_read']
            write_cost = (writes_per_month / 1_000_000) * pricing['on_demand_write']
            storage_cost = max(0, 10 - pricing['free_storage']) * pricing['storage']  # 10GB assumed
            
            total_cost = read_cost + write_cost + storage_cost
            
            assumptions = [
                f"Assumed {reads_per_month:,} read requests per month",
                f"Assumed {writes_per_month:,} write requests per month",
                "Assumed 10GB storage",
                "On-demand billing mode"
            ]
        else:
            # Provisioned capacity
            rcu = properties.get('ProvisionedThroughput', {}).get('ReadCapacityUnits', 5)
            wcu = properties.get('ProvisionedThroughput', {}).get('WriteCapacityUnits', 5)
            
            read_cost = rcu * pricing['provisioned_read'] * 24 * 30  # Monthly hours
            write_cost = wcu * pricing['provisioned_write'] * 24 * 30
            storage_cost = max(0, 10 - pricing['free_storage']) * pricing['storage']
            
            total_cost = read_cost + write_cost + storage_cost
            
            assumptions = [
                f"Provisioned {rcu} RCU and {wcu} WCU",
                "Assumed 10GB storage",
                "Auto-scaling not included"
            ]
        
        return ResourceEstimate(
            resource_type=ResourceType.DYNAMODB,
            resource_name=name,
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 1.5, 2),
            cost_factors={
                'billing_mode': billing_mode,
                'storage_gb': 10
            },
            assumptions=assumptions
        )
    
    def _estimate_s3_bucket(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate S3 bucket costs."""
        pricing = self.PRICING[ResourceType.S3]
        
        # Assumptions
        storage_gb = 100  # Assumed
        put_requests = 10_000  # Monthly
        get_requests = 100_000  # Monthly
        data_transfer_gb = 10  # Monthly
        
        # Calculate costs
        storage_cost = max(0, storage_gb - pricing['free_storage']) * pricing['storage_standard']
        put_cost = (put_requests / 1000) * pricing['requests_put']
        get_cost = max(0, get_requests - pricing['free_requests']) / 1000 * pricing['requests_get']
        transfer_cost = data_transfer_gb * pricing['data_transfer']
        
        total_cost = storage_cost + put_cost + get_cost + transfer_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.S3,
            resource_name=name,
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 2, 2),
            cost_factors={
                'storage_gb': storage_gb,
                'put_requests': put_requests,
                'get_requests': get_requests,
                'data_transfer_gb': data_transfer_gb
            },
            assumptions=[
                f"Assumed {storage_gb}GB storage",
                f"Assumed {put_requests:,} PUT and {get_requests:,} GET requests",
                f"Assumed {data_transfer_gb}GB data transfer"
            ]
        )
    
    def _estimate_api_gateway(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate API Gateway costs."""
        pricing = self.PRICING[ResourceType.API_GATEWAY]
        
        # Determine API type
        api_type = 'REST'  # Default
        requests_per_month = 1_000_000  # Assumed
        
        # Apply free tier
        billable_requests = max(0, requests_per_month - pricing['free_requests'])
        
        if api_type == 'REST':
            cost = (billable_requests / 1_000_000) * pricing['rest_api_requests']
        else:
            cost = (billable_requests / 1_000_000) * pricing['http_api_requests']
        
        return ResourceEstimate(
            resource_type=ResourceType.API_GATEWAY,
            resource_name=name,
            monthly_cost_min=round(cost, 2),
            monthly_cost_max=round(cost * 3, 2),  # 3x for peak
            cost_factors={
                'api_type': api_type,
                'requests_per_month': requests_per_month
            },
            assumptions=[
                f"Assumed {requests_per_month:,} API requests per month",
                f"{api_type} API type",
                "Free tier applied (1M requests for 12 months)"
            ]
        )
    
    def _estimate_cloudfront(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate CloudFront costs."""
        pricing = self.PRICING[ResourceType.CLOUDFRONT]
        
        # Assumptions
        data_transfer_gb = 100  # Monthly
        requests = 1_000_000   # Monthly
        
        # Apply free tier
        billable_transfer = max(0, data_transfer_gb - pricing['free_data_transfer'] / 12)
        
        transfer_cost = billable_transfer * pricing['data_transfer_us']
        request_cost = (requests / 10_000) * pricing['requests_https']
        
        total_cost = transfer_cost + request_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.CLOUDFRONT,
            resource_name=name,
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 2, 2),
            cost_factors={
                'data_transfer_gb': data_transfer_gb,
                'requests': requests
            },
            assumptions=[
                f"Assumed {data_transfer_gb}GB data transfer",
                f"Assumed {requests:,} HTTPS requests",
                "US/EU pricing, Asia-Pacific would be higher"
            ]
        )
    
    def _estimate_cognito(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate Cognito costs."""
        pricing = self.PRICING[ResourceType.COGNITO]
        
        # Assumptions
        mau = 1000  # Monthly active users
        
        # Apply free tier
        billable_mau = max(0, mau - pricing['free_mau'])
        
        if billable_mau == 0:
            cost = 0
        elif billable_mau <= 50_000:
            cost = billable_mau * pricing['mau_tier1']
        else:
            # Simplified tier calculation
            cost = 50_000 * pricing['mau_tier1'] + (billable_mau - 50_000) * pricing['mau_tier2']
        
        return ResourceEstimate(
            resource_type=ResourceType.COGNITO,
            resource_name=name,
            monthly_cost_min=round(cost, 2),
            monthly_cost_max=round(cost * 1.5, 2),
            cost_factors={
                'monthly_active_users': mau
            },
            assumptions=[
                f"Assumed {mau:,} monthly active users",
                "Free tier: 50,000 MAU"
            ]
        )
    
    def _estimate_waf(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate WAF costs."""
        pricing = self.PRICING[ResourceType.WAF]
        
        # Count rules
        rules = properties.get('Rules', [])
        rule_count = len(rules) if rules else 3  # Assumed
        requests_per_month = 1_000_000  # Assumed
        
        web_acl_cost = pricing['web_acl']
        rule_cost = rule_count * pricing['rule']
        request_cost = (requests_per_month / 1_000_000) * pricing['requests']
        
        total_cost = web_acl_cost + rule_cost + request_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.WAF,
            resource_name=name,
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 1.5, 2),
            cost_factors={
                'rule_count': rule_count,
                'requests_per_month': requests_per_month
            },
            assumptions=[
                f"Assumed {rule_count} WAF rules",
                f"Assumed {requests_per_month:,} requests per month"
            ]
        )
    
    def _estimate_nat_gateway(self, name: str, properties: Dict[str, Any]) -> ResourceEstimate:
        """Estimate NAT Gateway costs."""
        pricing = self.PRICING[ResourceType.NAT_GATEWAY]
        
        # Monthly hours
        hours = 24 * 30
        data_processed_gb = 100  # Assumed
        
        hourly_cost = hours * pricing['hourly']
        data_cost = data_processed_gb * pricing['data_processing']
        
        total_cost = hourly_cost + data_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.NAT_GATEWAY,
            resource_name=name,
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 1.5, 2),
            cost_factors={
                'hours': hours,
                'data_processed_gb': data_processed_gb
            },
            assumptions=[
                "24/7 operation",
                f"Assumed {data_processed_gb}GB data processed"
            ]
        )
    
    def _estimate_api_costs(self, usage: Dict[str, Any]) -> List[ResourceEstimate]:
        """Estimate API Gateway + Lambda costs from usage profile."""
        estimates = []
        
        # API Gateway
        api_requests = usage.get('api_requests_per_month', 0)
        api_pricing = self.PRICING[ResourceType.API_GATEWAY]
        
        billable_requests = max(0, api_requests - api_pricing['free_requests'])
        api_cost = (billable_requests / 1_000_000) * api_pricing['rest_api_requests']
        
        estimates.append(ResourceEstimate(
            resource_type=ResourceType.API_GATEWAY,
            resource_name="API Gateway",
            monthly_cost_min=round(api_cost, 2),
            monthly_cost_max=round(api_cost * 2, 2),
            cost_factors={'requests': api_requests},
            assumptions=[f"{api_requests:,} API requests per month"]
        ))
        
        # Lambda (backend for API)
        lambda_pricing = self.PRICING[ResourceType.LAMBDA]
        avg_duration = usage.get('avg_lambda_duration_ms', 100)
        memory = usage.get('lambda_memory_mb', 512)
        
        gb_seconds = (api_requests * avg_duration / 1000) * (memory / 1024)
        billable_gb_seconds = max(0, gb_seconds - lambda_pricing['free_gb_seconds'])
        
        lambda_request_cost = (billable_requests / 1_000_000) * lambda_pricing['request_price']
        lambda_compute_cost = billable_gb_seconds * lambda_pricing['gb_second_price']
        
        estimates.append(ResourceEstimate(
            resource_type=ResourceType.LAMBDA,
            resource_name="API Lambda Functions",
            monthly_cost_min=round(lambda_request_cost + lambda_compute_cost, 2),
            monthly_cost_max=round((lambda_request_cost + lambda_compute_cost) * 2, 2),
            cost_factors={
                'memory_mb': memory,
                'avg_duration_ms': avg_duration,
                'requests': api_requests
            },
            assumptions=[
                f"{memory}MB memory allocation",
                f"{avg_duration}ms average duration"
            ]
        ))
        
        return estimates
    
    def _estimate_database_costs(self, usage: Dict[str, Any]) -> ResourceEstimate:
        """Estimate DynamoDB costs from usage profile."""
        db_ops = usage.get('database_operations', {})
        reads = db_ops.get('reads_per_month', 0)
        writes = db_ops.get('writes_per_month', 0)
        storage = db_ops.get('storage_gb', 10)
        
        pricing = self.PRICING[ResourceType.DYNAMODB]
        
        read_cost = (reads / 1_000_000) * pricing['on_demand_read']
        write_cost = (writes / 1_000_000) * pricing['on_demand_write']
        storage_cost = max(0, storage - pricing['free_storage']) * pricing['storage']
        
        total_cost = read_cost + write_cost + storage_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.DYNAMODB,
            resource_name="DynamoDB Tables",
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 2, 2),
            cost_factors={
                'reads': reads,
                'writes': writes,
                'storage_gb': storage
            },
            assumptions=[
                "On-demand billing mode",
                f"{storage}GB total storage"
            ]
        )
    
    def _estimate_storage_costs(self, usage: Dict[str, Any]) -> ResourceEstimate:
        """Estimate S3 costs from usage profile."""
        storage = usage.get('storage_gb', 0)
        uploads = usage.get('uploads_per_month', 1000)
        downloads = usage.get('downloads_per_month', 10000)
        
        pricing = self.PRICING[ResourceType.S3]
        
        storage_cost = max(0, storage - pricing['free_storage']) * pricing['storage_standard']
        put_cost = (uploads / 1000) * pricing['requests_put']
        get_cost = max(0, downloads - pricing['free_requests']) / 1000 * pricing['requests_get']
        
        total_cost = storage_cost + put_cost + get_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.S3,
            resource_name="S3 Storage",
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 1.5, 2),
            cost_factors={
                'storage_gb': storage,
                'uploads': uploads,
                'downloads': downloads
            },
            assumptions=[
                "Standard storage class",
                "Minimal data transfer costs"
            ]
        )
    
    def _estimate_cdn_costs(self, usage: Dict[str, Any]) -> ResourceEstimate:
        """Estimate CloudFront costs from usage profile."""
        traffic = usage.get('cdn_traffic_gb', 0)
        requests = usage.get('cdn_requests_per_month', 1_000_000)
        
        pricing = self.PRICING[ResourceType.CLOUDFRONT]
        
        billable_traffic = max(0, traffic - pricing['free_data_transfer'] / 12)
        transfer_cost = billable_traffic * pricing['data_transfer_us']
        request_cost = (requests / 10_000) * pricing['requests_https']
        
        total_cost = transfer_cost + request_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.CLOUDFRONT,
            resource_name="CloudFront CDN",
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 2, 2),
            cost_factors={
                'traffic_gb': traffic,
                'requests': requests
            },
            assumptions=[
                "US/EU traffic pricing",
                "HTTPS requests only"
            ]
        )
    
    def _estimate_auth_costs(self, usage: Dict[str, Any]) -> ResourceEstimate:
        """Estimate Cognito costs from usage profile."""
        mau = usage.get('monthly_active_users', 0)
        
        pricing = self.PRICING[ResourceType.COGNITO]
        billable_mau = max(0, mau - pricing['free_mau'])
        
        if billable_mau == 0:
            cost = 0
        elif billable_mau <= 50_000:
            cost = billable_mau * pricing['mau_tier1']
        else:
            cost = 50_000 * pricing['mau_tier1'] + (billable_mau - 50_000) * pricing['mau_tier2']
        
        return ResourceEstimate(
            resource_type=ResourceType.COGNITO,
            resource_name="Cognito Authentication",
            monthly_cost_min=round(cost, 2),
            monthly_cost_max=round(cost * 1.2, 2),
            cost_factors={'mau': mau},
            assumptions=[
                f"{mau:,} monthly active users",
                "Standard authentication flow"
            ]
        )
    
    def _estimate_monitoring_costs(self, usage: Dict[str, Any]) -> ResourceEstimate:
        """Estimate CloudWatch costs from usage profile."""
        pricing = self.PRICING[ResourceType.CLOUDWATCH]
        
        # Estimate based on other services
        lambda_requests = usage.get('api_requests_per_month', 0)
        log_gb = lambda_requests / 1_000_000 * 0.5  # 0.5KB per request assumed
        metrics = 20  # Assumed custom metrics
        alarms = 5   # Assumed alarms
        
        log_ingestion_cost = max(0, log_gb - pricing['free_logs_gb']) * pricing['logs_ingestion']
        log_storage_cost = log_gb * pricing['logs_storage']
        metrics_cost = max(0, metrics - pricing['free_metrics']) * pricing['metrics']
        alarms_cost = max(0, alarms - pricing['free_alarms']) * pricing['alarms']
        
        total_cost = log_ingestion_cost + log_storage_cost + metrics_cost + alarms_cost
        
        return ResourceEstimate(
            resource_type=ResourceType.CLOUDWATCH,
            resource_name="CloudWatch Monitoring",
            monthly_cost_min=round(total_cost, 2),
            monthly_cost_max=round(total_cost * 1.5, 2),
            cost_factors={
                'log_gb': round(log_gb, 2),
                'metrics': metrics,
                'alarms': alarms
            },
            assumptions=[
                f"{round(log_gb, 2)}GB logs per month",
                f"{metrics} custom metrics",
                f"{alarms} alarms"
            ]
        )
    
    def _generate_cost_report(self, estimates: List[ResourceEstimate]) -> Dict[str, Any]:
        """Generate comprehensive cost report."""
        total_min = sum(e.monthly_cost_min for e in estimates)
        total_max = sum(e.monthly_cost_max for e in estimates)
        
        report = {
            "project": self.project_name,
            "environment": self.environment,
            "region": self.region,
            "summary": {
                "monthly_cost_estimate": {
                    "minimum": round(total_min, 2),
                    "maximum": round(total_max, 2),
                    "average": round((total_min + total_max) / 2, 2)
                },
                "annual_cost_estimate": {
                    "minimum": round(total_min * 12, 2),
                    "maximum": round(total_max * 12, 2),
                    "average": round((total_min + total_max) / 2 * 12, 2)
                },
                "daily_cost_estimate": {
                    "minimum": round(total_min / 30, 2),
                    "maximum": round(total_max / 30, 2)
                }
            },
            "breakdown_by_service": self._group_by_service(estimates),
            "detailed_estimates": [
                {
                    "resource_type": e.resource_type.value,
                    "resource_name": e.resource_name,
                    "monthly_cost": {
                        "min": e.monthly_cost_min,
                        "max": e.monthly_cost_max
                    },
                    "cost_factors": e.cost_factors,
                    "assumptions": e.assumptions
                }
                for e in estimates
            ],
            "cost_optimization_tips": self._get_optimization_tips(estimates),
            "notes": [
                "Costs are estimated based on typical usage patterns",
                "Actual costs may vary based on real usage",
                "Free tier benefits are included where applicable",
                "Data transfer costs between AWS services not included",
                "Prices based on US regions, other regions may vary"
            ]
        }
        
        return report
    
    def _group_by_service(self, estimates: List[ResourceEstimate]) -> Dict[str, Dict[str, float]]:
        """Group estimates by service type."""
        by_service = {}
        
        for estimate in estimates:
            service = estimate.resource_type.value
            if service not in by_service:
                by_service[service] = {
                    "monthly_min": 0,
                    "monthly_max": 0,
                    "resources": []
                }
            
            by_service[service]["monthly_min"] += estimate.monthly_cost_min
            by_service[service]["monthly_max"] += estimate.monthly_cost_max
            by_service[service]["resources"].append(estimate.resource_name)
        
        # Round values
        for service in by_service:
            by_service[service]["monthly_min"] = round(by_service[service]["monthly_min"], 2)
            by_service[service]["monthly_max"] = round(by_service[service]["monthly_max"], 2)
        
        return by_service
    
    def _get_optimization_tips(self, estimates: List[ResourceEstimate]) -> List[str]:
        """Get cost optimization recommendations."""
        tips = []
        
        # Check for expensive services
        for estimate in estimates:
            if estimate.monthly_cost_max > 100:
                if estimate.resource_type == ResourceType.NAT_GATEWAY:
                    tips.append("Consider using VPC endpoints instead of NAT Gateway for S3/DynamoDB access")
                elif estimate.resource_type == ResourceType.CLOUDFRONT:
                    tips.append("Enable CloudFront caching to reduce origin requests")
                elif estimate.resource_type == ResourceType.DYNAMODB:
                    tips.append("Consider DynamoDB auto-scaling or on-demand for variable workloads")
        
        # General tips
        tips.extend([
            "Use AWS Free Tier resources during development",
            "Enable billing alerts to monitor actual costs",
            "Review and remove unused resources regularly",
            "Consider Reserved Instances or Savings Plans for stable workloads",
            "Use S3 lifecycle policies to move old data to cheaper storage classes"
        ])
        
        return tips
    
    def generate_cost_alert_template(self, monthly_budget: float) -> Dict[str, Any]:
        """Generate CloudFormation template for cost alerts.
        
        Args:
            monthly_budget: Monthly budget limit
            
        Returns:
            CloudFormation template for budget alerts
        """
        return {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": f"Cost alerts for {self.project_name}",
            "Resources": {
                "MonthlyBudget": {
                    "Type": "AWS::Budgets::Budget",
                    "Properties": {
                        "Budget": {
                            "BudgetName": f"{self.project_name}-monthly-budget",
                            "BudgetLimit": {
                                "Amount": monthly_budget,
                                "Unit": "USD"
                            },
                            "TimeUnit": "MONTHLY",
                            "BudgetType": "COST",
                            "CostFilters": {
                                "TagKeyValue": [f"user:Project${self.project_name}"]
                            }
                        },
                        "NotificationsWithSubscribers": [
                            {
                                "Notification": {
                                    "NotificationType": "ACTUAL",
                                    "ComparisonOperator": "GREATER_THAN",
                                    "Threshold": 80,
                                    "ThresholdType": "PERCENTAGE"
                                },
                                "Subscribers": [
                                    {
                                        "SubscriptionType": "EMAIL",
                                        "Address": "admin@example.com"
                                    }
                                ]
                            },
                            {
                                "Notification": {
                                    "NotificationType": "FORECASTED",
                                    "ComparisonOperator": "GREATER_THAN",
                                    "Threshold": 100,
                                    "ThresholdType": "PERCENTAGE"
                                },
                                "Subscribers": [
                                    {
                                        "SubscriptionType": "EMAIL",
                                        "Address": "admin@example.com"
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }