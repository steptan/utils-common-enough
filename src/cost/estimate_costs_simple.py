#!/usr/bin/env python3
"""
Simple cost estimator for AWS projects.
Provides quick cost estimates based on usage patterns.
"""

import json
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime


class SimpleCostEstimator:
    """Simple AWS cost estimator based on usage patterns."""
    
    # AWS Pricing (simplified, prices in USD)
    PRICING = {
        "lambda": {
            "request_price": 0.20,  # per 1M requests
            "gb_second_price": 0.0000166667,  # per GB-second
            "free_tier": {
                "requests": 1_000_000,
                "gb_seconds": 400_000
            }
        },
        "dynamodb": {
            "on_demand": {
                "write_price": 1.25,  # per 1M write units
                "read_price": 0.25,   # per 1M read units
            },
            "storage_price": 0.25,  # per GB per month
        },
        "s3": {
            "storage_standard": 0.023,  # per GB per month
            "requests": {
                "put": 0.005,  # per 1K requests
                "get": 0.0004,  # per 1K requests
            },
            "data_transfer": 0.09,  # per GB (internet)
        },
        "cloudfront": {
            "data_transfer": {
                "us": 0.085,  # per GB
                "eu": 0.085,
                "asia": 0.140,
            },
            "requests": 0.01,  # per 10K requests
        },
        "api_gateway": {
            "requests": 3.50,  # per 1M requests
            "data_transfer": 0.09,  # per GB
        },
        "cognito": {
            "mau_price": 0.0055,  # per MAU after 50K
            "free_tier_mau": 50_000,
        },
        "cloudwatch": {
            "logs_ingestion": 0.50,  # per GB
            "logs_storage": 0.03,  # per GB per month
            "custom_metrics": 0.30,  # per metric per month
        }
    }
    
    def __init__(self, project_name: str):
        self.project_name = project_name
    
    def estimate_costs(self, usage_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate monthly costs based on usage profile."""
        
        costs = {}
        total_min = 0
        total_max = 0
        
        # Lambda costs
        if "lambda" in usage_profile:
            lambda_cost = self._estimate_lambda_cost(usage_profile["lambda"])
            costs["lambda"] = lambda_cost
            total_min += lambda_cost["min"]
            total_max += lambda_cost["max"]
        
        # DynamoDB costs
        if "dynamodb" in usage_profile:
            dynamo_cost = self._estimate_dynamodb_cost(usage_profile["dynamodb"])
            costs["dynamodb"] = dynamo_cost
            total_min += dynamo_cost["min"]
            total_max += dynamo_cost["max"]
        
        # S3 costs
        if "s3" in usage_profile:
            s3_cost = self._estimate_s3_cost(usage_profile["s3"])
            costs["s3"] = s3_cost
            total_min += s3_cost["min"]
            total_max += s3_cost["max"]
        
        # CloudFront costs
        if "cloudfront" in usage_profile:
            cf_cost = self._estimate_cloudfront_cost(usage_profile["cloudfront"])
            costs["cloudfront"] = cf_cost
            total_min += cf_cost["min"]
            total_max += cf_cost["max"]
        
        # API Gateway costs
        if "api_gateway" in usage_profile:
            api_cost = self._estimate_api_gateway_cost(usage_profile["api_gateway"])
            costs["api_gateway"] = api_cost
            total_min += api_cost["min"]
            total_max += api_cost["max"]
        
        # Cognito costs
        if "cognito" in usage_profile:
            cognito_cost = self._estimate_cognito_cost(usage_profile["cognito"])
            costs["cognito"] = cognito_cost
            total_min += cognito_cost["min"]
            total_max += cognito_cost["max"]
        
        # CloudWatch costs
        if "cloudwatch" in usage_profile:
            cw_cost = self._estimate_cloudwatch_cost(usage_profile["cloudwatch"])
            costs["cloudwatch"] = cw_cost
            total_min += cw_cost["min"]
            total_max += cw_cost["max"]
        
        return {
            "project": self.project_name,
            "timestamp": datetime.now().isoformat(),
            "services": costs,
            "total": {
                "monthly": {
                    "min": round(total_min, 2),
                    "max": round(total_max, 2),
                    "average": round((total_min + total_max) / 2, 2)
                },
                "annual": {
                    "min": round(total_min * 12, 2),
                    "max": round(total_max * 12, 2),
                    "average": round((total_min + total_max) / 2 * 12, 2)
                }
            },
            "assumptions": self._get_assumptions(),
            "optimization_tips": self._get_optimization_tips(costs)
        }
    
    def _estimate_lambda_cost(self, usage: Dict[str, Any]) -> Dict[str, float]:
        """Estimate Lambda costs."""
        requests = usage.get("requests_per_month", 1_000_000)
        avg_duration_ms = usage.get("avg_duration_ms", 100)
        memory_mb = usage.get("memory_mb", 512)
        
        # Calculate GB-seconds
        gb_seconds = (requests * avg_duration_ms / 1000) * (memory_mb / 1024)
        
        # Apply free tier
        billable_requests = max(0, requests - self.PRICING["lambda"]["free_tier"]["requests"])
        billable_gb_seconds = max(0, gb_seconds - self.PRICING["lambda"]["free_tier"]["gb_seconds"])
        
        # Calculate costs
        request_cost = (billable_requests / 1_000_000) * self.PRICING["lambda"]["request_price"]
        compute_cost = billable_gb_seconds * self.PRICING["lambda"]["gb_second_price"]
        
        total = request_cost + compute_cost
        
        return {
            "min": total * 0.8,  # 20% variance
            "max": total * 1.2,
            "details": {
                "requests": requests,
                "gb_seconds": gb_seconds,
                "request_cost": request_cost,
                "compute_cost": compute_cost
            }
        }
    
    def _estimate_dynamodb_cost(self, usage: Dict[str, Any]) -> Dict[str, float]:
        """Estimate DynamoDB costs."""
        reads_per_month = usage.get("reads_per_month", 5_000_000)
        writes_per_month = usage.get("writes_per_month", 500_000)
        storage_gb = usage.get("storage_gb", 10)
        
        # On-demand pricing
        read_cost = (reads_per_month / 1_000_000) * self.PRICING["dynamodb"]["on_demand"]["read_price"]
        write_cost = (writes_per_month / 1_000_000) * self.PRICING["dynamodb"]["on_demand"]["write_price"]
        storage_cost = storage_gb * self.PRICING["dynamodb"]["storage_price"]
        
        total = read_cost + write_cost + storage_cost
        
        return {
            "min": total * 0.7,  # 30% variance for on-demand
            "max": total * 1.3,
            "details": {
                "read_cost": read_cost,
                "write_cost": write_cost,
                "storage_cost": storage_cost
            }
        }
    
    def _estimate_s3_cost(self, usage: Dict[str, Any]) -> Dict[str, float]:
        """Estimate S3 costs."""
        storage_gb = usage.get("storage_gb", 100)
        put_requests = usage.get("put_requests_per_month", 10_000)
        get_requests = usage.get("get_requests_per_month", 100_000)
        data_transfer_gb = usage.get("data_transfer_gb", 10)
        
        storage_cost = storage_gb * self.PRICING["s3"]["storage_standard"]
        put_cost = (put_requests / 1_000) * self.PRICING["s3"]["requests"]["put"]
        get_cost = (get_requests / 1_000) * self.PRICING["s3"]["requests"]["get"]
        transfer_cost = data_transfer_gb * self.PRICING["s3"]["data_transfer"]
        
        total = storage_cost + put_cost + get_cost + transfer_cost
        
        return {
            "min": total * 0.9,
            "max": total * 1.1,
            "details": {
                "storage_cost": storage_cost,
                "request_cost": put_cost + get_cost,
                "transfer_cost": transfer_cost
            }
        }
    
    def _estimate_cloudfront_cost(self, usage: Dict[str, Any]) -> Dict[str, float]:
        """Estimate CloudFront costs."""
        data_transfer_gb = usage.get("data_transfer_gb", 100)
        requests = usage.get("requests_per_month", 1_000_000)
        region_distribution = usage.get("region_distribution", {"us": 0.6, "eu": 0.3, "asia": 0.1})
        
        # Calculate weighted data transfer cost
        transfer_cost = 0
        for region, percentage in region_distribution.items():
            if region in self.PRICING["cloudfront"]["data_transfer"]:
                transfer_cost += data_transfer_gb * percentage * self.PRICING["cloudfront"]["data_transfer"][region]
        
        request_cost = (requests / 10_000) * self.PRICING["cloudfront"]["requests"]
        
        total = transfer_cost + request_cost
        
        return {
            "min": total * 0.8,
            "max": total * 1.2,
            "details": {
                "transfer_cost": transfer_cost,
                "request_cost": request_cost
            }
        }
    
    def _estimate_api_gateway_cost(self, usage: Dict[str, Any]) -> Dict[str, float]:
        """Estimate API Gateway costs."""
        requests = usage.get("requests_per_month", 1_000_000)
        data_transfer_gb = usage.get("data_transfer_gb", 5)
        
        request_cost = (requests / 1_000_000) * self.PRICING["api_gateway"]["requests"]
        transfer_cost = data_transfer_gb * self.PRICING["api_gateway"]["data_transfer"]
        
        total = request_cost + transfer_cost
        
        return {
            "min": total * 0.9,
            "max": total * 1.1,
            "details": {
                "request_cost": request_cost,
                "transfer_cost": transfer_cost
            }
        }
    
    def _estimate_cognito_cost(self, usage: Dict[str, Any]) -> Dict[str, float]:
        """Estimate Cognito costs."""
        mau = usage.get("monthly_active_users", 10_000)
        
        billable_mau = max(0, mau - self.PRICING["cognito"]["free_tier_mau"])
        total = billable_mau * self.PRICING["cognito"]["mau_price"]
        
        return {
            "min": total,
            "max": total * 1.2,  # Some growth variance
            "details": {
                "mau": mau,
                "billable_mau": billable_mau
            }
        }
    
    def _estimate_cloudwatch_cost(self, usage: Dict[str, Any]) -> Dict[str, float]:
        """Estimate CloudWatch costs."""
        logs_ingestion_gb = usage.get("logs_ingestion_gb", 10)
        logs_storage_gb = usage.get("logs_storage_gb", 50)
        custom_metrics = usage.get("custom_metrics", 10)
        
        ingestion_cost = logs_ingestion_gb * self.PRICING["cloudwatch"]["logs_ingestion"]
        storage_cost = logs_storage_gb * self.PRICING["cloudwatch"]["logs_storage"]
        metrics_cost = custom_metrics * self.PRICING["cloudwatch"]["custom_metrics"]
        
        total = ingestion_cost + storage_cost + metrics_cost
        
        return {
            "min": total * 0.8,
            "max": total * 1.2,
            "details": {
                "ingestion_cost": ingestion_cost,
                "storage_cost": storage_cost,
                "metrics_cost": metrics_cost
            }
        }
    
    def _get_assumptions(self) -> List[str]:
        """Get list of assumptions made in estimates."""
        return [
            "Prices based on US regions (us-east-1/us-west-1)",
            "Free tier benefits included where applicable",
            "On-demand pricing for DynamoDB (provisioned may be cheaper)",
            "Standard storage class for S3",
            "Min/max estimates include 10-30% variance for usage fluctuations",
            "Data transfer costs may vary by actual geographic distribution"
        ]
    
    def _get_optimization_tips(self, costs: Dict[str, Any]) -> List[str]:
        """Get cost optimization tips based on estimates."""
        tips = []
        
        # Lambda tips
        if "lambda" in costs and costs["lambda"]["max"] > 20:
            tips.append("Consider optimizing Lambda memory allocation and execution time")
            tips.append("Use Lambda Reserved Concurrency for predictable workloads")
        
        # DynamoDB tips  
        if "dynamodb" in costs and costs["dynamodb"]["max"] > 50:
            tips.append("Consider DynamoDB provisioned capacity for predictable workloads")
            tips.append("Enable auto-scaling for DynamoDB tables")
            tips.append("Use DynamoDB TTL to automatically remove old items")
        
        # S3 tips
        if "s3" in costs and costs["s3"]["max"] > 30:
            tips.append("Use S3 lifecycle policies to move old data to cheaper storage classes")
            tips.append("Enable S3 Intelligent-Tiering for automatic cost optimization")
        
        # CloudFront tips
        if "cloudfront" in costs and costs["cloudfront"]["max"] > 50:
            tips.append("Improve CloudFront cache hit ratios to reduce origin requests")
            tips.append("Use CloudFront compression to reduce data transfer")
        
        # General tips
        tips.extend([
            "Tag all resources for accurate cost allocation",
            "Set up AWS Budgets with alerts",
            "Use AWS Cost Explorer to track actual vs estimated costs",
            "Review and remove unused resources regularly"
        ])
        
        return tips[:8]  # Return top 8 tips


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Estimate AWS costs for a project")
    parser.add_argument("project", help="Project name")
    parser.add_argument("--profile", "-p", help="Usage profile JSON file")
    parser.add_argument("--output", "-o", choices=["console", "json"], default="console",
                       help="Output format")
    
    args = parser.parse_args()
    
    # Default usage profile
    default_profile = {
        "lambda": {
            "requests_per_month": 1_000_000,
            "avg_duration_ms": 100,
            "memory_mb": 512
        },
        "dynamodb": {
            "reads_per_month": 5_000_000,
            "writes_per_month": 500_000,
            "storage_gb": 20
        },
        "s3": {
            "storage_gb": 100,
            "put_requests_per_month": 10_000,
            "get_requests_per_month": 100_000,
            "data_transfer_gb": 10
        },
        "cloudfront": {
            "data_transfer_gb": 100,
            "requests_per_month": 5_000_000,
            "region_distribution": {"us": 0.7, "eu": 0.2, "asia": 0.1}
        },
        "api_gateway": {
            "requests_per_month": 1_000_000,
            "data_transfer_gb": 5
        },
        "cognito": {
            "monthly_active_users": 10_000
        },
        "cloudwatch": {
            "logs_ingestion_gb": 10,
            "logs_storage_gb": 50,
            "custom_metrics": 10
        }
    }
    
    # Load custom profile if provided
    if args.profile:
        try:
            with open(args.profile, 'r') as f:
                usage_profile = json.load(f)
        except Exception as e:
            print(f"❌ Error loading profile: {e}")
            sys.exit(1)
    else:
        usage_profile = default_profile
    
    # Create estimator and get estimates
    estimator = SimpleCostEstimator(args.project)
    estimates = estimator.estimate_costs(usage_profile)
    
    if args.output == "json":
        print(json.dumps(estimates, indent=2))
    else:
        # Console output
        print(f"\n💰 Cost Estimate for {args.project}")
        print("=" * 60)
        print(f"Generated: {estimates['timestamp']}")
        print()
        
        # Service breakdown
        print("📊 Estimated Monthly Costs by Service:")
        for service, cost in estimates["services"].items():
            avg = (cost["min"] + cost["max"]) / 2
            print(f"  {service.upper()}: ${cost['min']:.2f} - ${cost['max']:.2f} (avg: ${avg:.2f})")
        
        print()
        print("💵 Total Estimated Costs:")
        total = estimates["total"]["monthly"]
        print(f"  Monthly: ${total['min']:.2f} - ${total['max']:.2f} (avg: ${total['average']:.2f})")
        annual = estimates["total"]["annual"]
        print(f"  Annual:  ${annual['min']:.2f} - ${annual['max']:.2f} (avg: ${annual['average']:.2f})")
        
        print()
        print("📌 Assumptions:")
        for assumption in estimates["assumptions"]:
            print(f"  • {assumption}")
        
        print()
        print("💡 Cost Optimization Tips:")
        for tip in estimates["optimization_tips"]:
            print(f"  • {tip}")
        
        print()


if __name__ == "__main__":
    main()