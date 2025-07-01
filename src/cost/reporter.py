"""Cost reporting utilities."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from config import ProjectConfig
from .analyzer import CostAnalyzer
from .monitor import CostMonitor


class CostReporter:
    """Generate cost reports for projects."""
    
    def __init__(
        self,
        config: ProjectConfig,
        aws_profile: Optional[str] = None
    ):
        """
        Initialize cost reporter.
        
        Args:
            config: Project configuration
            aws_profile: AWS profile to use
        """
        self.config = config
        self.project_name = config.name
        
        # Initialize analyzer and monitor
        self.analyzer = CostAnalyzer(config, aws_profile)
        self.monitor = CostMonitor(config, aws_profile)
    
    def generate_monthly_report(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
        output_format: str = "text"
    ) -> str:
        """
        Generate monthly cost report.
        
        Args:
            month: Month (1-12), defaults to previous month
            year: Year, defaults to current year
            output_format: Output format (text, json, html)
            
        Returns:
            Report content
        """
        # Default to previous month
        if not month or not year:
            today = datetime.now()
            if today.month == 1:
                month = 12
                year = today.year - 1
            else:
                month = today.month - 1
                year = today.year
        
        # Calculate date range
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        print(f"📊 Generating monthly report for {self.project_name} ({month}/{year})")
        
        # Gather data
        cost_data = self.analyzer.get_project_costs(start_date, end_date, "MONTHLY")
        service_breakdown = self.analyzer.get_service_breakdown(start_date, end_date)
        anomalies = self.analyzer.get_cost_anomalies()
        forecast = self.analyzer.get_cost_forecast()
        
        # Get budget status for all environments
        budget_status = {}
        for env in self.config.environments:
            budget_status[env] = self.monitor.get_budget_status(env)
        
        # Generate report
        if output_format == "json":
            return self._generate_json_report(
                cost_data, service_breakdown, anomalies, forecast, budget_status
            )
        elif output_format == "html":
            return self._generate_html_report(
                cost_data, service_breakdown, anomalies, forecast, budget_status,
                month, year
            )
        else:
            return self._generate_text_report(
                cost_data, service_breakdown, anomalies, forecast, budget_status,
                month, year
            )
    
    def generate_comparison_report(
        self,
        environments: Optional[List[str]] = None,
        days: int = 30
    ) -> str:
        """
        Generate environment comparison report.
        
        Args:
            environments: Environments to compare
            days: Number of days to analyze
            
        Returns:
            Comparison report
        """
        if not environments:
            environments = self.config.environments
        
        print(f"🔍 Generating comparison report for {', '.join(environments)}")
        
        # Gather data for each environment
        env_data = {}
        for env in environments:
            # Get costs
            costs = self.analyzer.get_project_costs(
                start_date=datetime.now() - timedelta(days=days),
                end_date=datetime.now()
            )
            
            # Get resource costs
            resource_costs = self.analyzer.get_resource_costs(env)
            
            env_data[env] = {
                "total_cost": costs["total_cost"],
                "daily_average": costs["total_cost"] / days if days > 0 else 0,
                "services": costs["services"],
                "resources": resource_costs
            }
        
        return self._generate_comparison_text(env_data, days)
    
    def generate_executive_summary(
        self,
        quarter: Optional[int] = None,
        year: Optional[int] = None
    ) -> str:
        """
        Generate executive summary for quarter.
        
        Args:
            quarter: Quarter (1-4)
            year: Year
            
        Returns:
            Executive summary
        """
        # Default to previous quarter
        if not quarter or not year:
            today = datetime.now()
            current_quarter = (today.month - 1) // 3 + 1
            if current_quarter == 1:
                quarter = 4
                year = today.year - 1
            else:
                quarter = current_quarter - 1
                year = today.year
        
        # Calculate date range
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime(year, start_month, 1)
        
        if quarter == 4:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, start_month + 3, 1)
        
        print(f"📈 Generating executive summary for Q{quarter} {year}")
        
        # Gather quarterly data
        quarterly_costs = self.analyzer.get_project_costs(start_date, end_date, "MONTHLY")
        total_cost = quarterly_costs["total_cost"]
        
        # Calculate cost trends
        monthly_costs = quarterly_costs.get("daily_costs", [])  # Actually monthly when granularity=MONTHLY
        
        # Get forecast for next quarter
        forecast = self.analyzer.get_cost_forecast(90)
        
        # Generate summary
        summary = f"""
EXECUTIVE SUMMARY - {self.project_name.upper()}
Q{quarter} {year} Cost Report

TOTAL SPEND: ${total_cost:,.2f}
MONTHLY AVERAGE: ${total_cost / 3:,.2f}

TOP SERVICES BY COST:
"""
        
        # Add top 5 services
        services = sorted(
            quarterly_costs["services"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        for service, cost in services:
            percentage = (cost / total_cost * 100) if total_cost > 0 else 0
            summary += f"  • {service}: ${cost:,.2f} ({percentage:.1f}%)\n"
        
        summary += f"""
NEXT QUARTER FORECAST:
  • Projected Spend: ${forecast.get('projected_cost', 0):,.2f}
  • Trend: {forecast.get('weekly_trend_percent', 0):+.1f}% weekly
  • Confidence: {forecast.get('confidence', 'low').upper()}

RECOMMENDATIONS:
"""
        
        # Add recommendations based on data
        recommendations = self._generate_recommendations(quarterly_costs, forecast)
        for rec in recommendations:
            summary += f"  • {rec}\n"
        
        return summary
    
    def save_report(self, report: str, filename: str, output_dir: Path) -> Path:
        """
        Save report to file.
        
        Args:
            report: Report content
            filename: Output filename
            output_dir: Output directory
            
        Returns:
            Path to saved report
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        
        with open(output_path, "w") as f:
            f.write(report)
        
        print(f"💾 Report saved to: {output_path}")
        return output_path
    
    def _generate_text_report(
        self,
        cost_data: Dict[str, Any],
        service_breakdown: Dict[str, float],
        anomalies: List[Dict[str, Any]],
        forecast: Dict[str, Any],
        budget_status: Dict[str, Dict[str, Any]],
        month: int,
        year: int
    ) -> str:
        """Generate text format report."""
        report = f"""
================================================================================
MONTHLY COST REPORT - {self.project_name.upper()}
{month}/{year}
================================================================================

TOTAL COST: ${cost_data['total_cost']:,.2f}

SERVICE BREAKDOWN:
"""
        
        # Add service costs
        for service, cost in sorted(service_breakdown.items(), key=lambda x: x[1], reverse=True):
            percentage = (cost / cost_data['total_cost'] * 100) if cost_data['total_cost'] > 0 else 0
            report += f"  {service:<30} ${cost:>10,.2f} ({percentage:>5.1f}%)\n"
        
        # Add budget status
        report += "\nBUDGET STATUS:\n"
        for env, status in budget_status.items():
            if "error" not in status:
                report += f"  {env:<15} ${status.get('current_spend', 0):>10,.2f} / ${status.get('budget_amount', 0):>10,.2f} ({status.get('percentage_used', 0):>5.1f}%) - {status.get('status', 'UNKNOWN')}\n"
        
        # Add anomalies
        if anomalies:
            report += f"\nCOST ANOMALIES DETECTED ({len(anomalies)}):\n"
            for anomaly in anomalies[:5]:  # Show top 5
                report += f"  • {anomaly['date']}: ${anomaly['cost']:.2f} (expected: ${anomaly['expected_cost']:.2f}, {anomaly['change_percent']:+.1f}%)\n"
        
        # Add forecast
        report += f"\nFORECAST (Next 30 days):\n"
        report += f"  Projected Cost: ${forecast.get('projected_cost', 0):,.2f}\n"
        report += f"  Current Daily Average: ${forecast.get('current_daily_average', 0):.2f}\n"
        report += f"  Weekly Trend: {forecast.get('weekly_trend_percent', 0):+.1f}%\n"
        
        report += "\n" + "=" * 80 + "\n"
        
        return report
    
    def _generate_json_report(
        self,
        cost_data: Dict[str, Any],
        service_breakdown: Dict[str, float],
        anomalies: List[Dict[str, Any]],
        forecast: Dict[str, Any],
        budget_status: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate JSON format report."""
        report_data = {
            "project": self.project_name,
            "generated_at": datetime.now().isoformat(),
            "cost_summary": cost_data,
            "service_breakdown": service_breakdown,
            "anomalies": anomalies,
            "forecast": forecast,
            "budget_status": budget_status
        }
        
        return json.dumps(report_data, indent=2, default=str)
    
    def _generate_html_report(
        self,
        cost_data: Dict[str, Any],
        service_breakdown: Dict[str, float],
        anomalies: List[Dict[str, Any]],
        forecast: Dict[str, Any],
        budget_status: Dict[str, Dict[str, Any]],
        month: int,
        year: int
    ) -> str:
        """Generate HTML format report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Cost Report - {self.project_name} - {month}/{year}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .total {{ font-size: 24px; color: #0066cc; }}
        .warning {{ color: #ff9900; }}
        .error {{ color: #cc0000; }}
        .good {{ color: #009900; }}
    </style>
</head>
<body>
    <h1>Monthly Cost Report - {self.project_name}</h1>
    <p>{month}/{year}</p>
    
    <div class="total">Total Cost: ${cost_data['total_cost']:,.2f}</div>
    
    <h2>Service Breakdown</h2>
    <table>
        <tr><th>Service</th><th>Cost</th><th>Percentage</th></tr>
"""
        
        for service, cost in sorted(service_breakdown.items(), key=lambda x: x[1], reverse=True):
            percentage = (cost / cost_data['total_cost'] * 100) if cost_data['total_cost'] > 0 else 0
            html += f"        <tr><td>{service}</td><td>${cost:,.2f}</td><td>{percentage:.1f}%</td></tr>\n"
        
        html += """    </table>
    
    <h2>Budget Status</h2>
    <table>
        <tr><th>Environment</th><th>Current Spend</th><th>Budget</th><th>Usage</th><th>Status</th></tr>
"""
        
        for env, status in budget_status.items():
            if "error" not in status:
                status_class = "good" if status.get("status") == "GOOD" else "warning" if status.get("status") == "WARNING" else "error"
                html += f"""        <tr>
            <td>{env}</td>
            <td>${status.get('current_spend', 0):,.2f}</td>
            <td>${status.get('budget_amount', 0):,.2f}</td>
            <td>{status.get('percentage_used', 0):.1f}%</td>
            <td class="{status_class}">{status.get('status', 'UNKNOWN')}</td>
        </tr>\n"""
        
        html += """    </table>
</body>
</html>"""
        
        return html
    
    def _generate_comparison_text(self, env_data: Dict[str, Dict[str, Any]], days: int) -> str:
        """Generate environment comparison text."""
        report = f"""
ENVIRONMENT COMPARISON REPORT - {self.project_name.upper()}
Last {days} days

"""
        
        # Summary table
        report += f"{'Environment':<15} {'Total Cost':>15} {'Daily Average':>15} {'Top Service':>20}\n"
        report += "-" * 70 + "\n"
        
        for env, data in env_data.items():
            top_service = max(data["services"].items(), key=lambda x: x[1])[0] if data["services"] else "N/A"
            report += f"{env:<15} ${data['total_cost']:>14,.2f} ${data['daily_average']:>14,.2f} {top_service:>20}\n"
        
        # Detailed breakdown
        report += "\n\nDETAILED SERVICE COSTS:\n"
        
        # Get all services
        all_services = set()
        for data in env_data.values():
            all_services.update(data["services"].keys())
        
        # Create comparison table
        report += f"\n{'Service':<30}"
        for env in env_data.keys():
            report += f" {env:>15}"
        report += "\n" + "-" * (30 + 16 * len(env_data)) + "\n"
        
        for service in sorted(all_services):
            report += f"{service:<30}"
            for env, data in env_data.items():
                cost = data["services"].get(service, 0)
                report += f" ${cost:>14,.2f}"
            report += "\n"
        
        return report
    
    def _generate_recommendations(
        self,
        cost_data: Dict[str, Any],
        forecast: Dict[str, Any]
    ) -> List[str]:
        """Generate cost optimization recommendations."""
        recommendations = []
        
        # Check for high-cost services
        top_services = sorted(
            cost_data["services"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        for service, cost in top_services:
            if "Lambda" in service and cost > 100:
                recommendations.append(f"Review Lambda function efficiency - {service} costs ${cost:.2f}")
            elif "S3" in service and cost > 50:
                recommendations.append(f"Consider S3 lifecycle policies - {service} costs ${cost:.2f}")
            elif "CloudFront" in service and cost > 100:
                recommendations.append(f"Optimize CloudFront caching - {service} costs ${cost:.2f}")
        
        # Check forecast trend
        trend = forecast.get("weekly_trend_percent", 0)
        if trend > 10:
            recommendations.append(f"Cost trend increasing at {trend:.1f}% weekly - investigate root cause")
        
        # Generic recommendations
        if not recommendations:
            recommendations.append("Continue monitoring costs for optimization opportunities")
        
        return recommendations