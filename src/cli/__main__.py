#!/usr/bin/env python3
"""Main CLI entry point for project utilities."""

import click
import sys
from pathlib import Path

# Import all command groups
from .deploy import main as deploy_commands
from .cloudformation import main as cf_commands
from .lambda_cmd import main as lambda_commands
from .iam import main as iam_commands
from .database import main as db_commands
from .test import main as test_commands

# Import new commands
from cli.setup import SetupWizard
from deployment.validation import PreDeploymentValidator
from security.audit import SecurityAuditor
from security.compliance import ComplianceChecker
from cost.estimator import CostEstimator
from cost.analyzer import CostAnalyzer
from config import get_project_config


@click.group()
@click.version_option()
def cli():
    """Project deployment and management utilities.
    
    A comprehensive toolkit for AWS project deployment, management, and monitoring.
    """
    pass


# Add existing command groups
cli.add_command(deploy_commands, name='deploy')
cli.add_command(cf_commands, name='cloudformation')
cli.add_command(lambda_commands, name='lambda')
cli.add_command(iam_commands, name='iam')
cli.add_command(db_commands, name='database')
cli.add_command(test_commands, name='test')


# New commands
@cli.command()
def setup():
    """Run interactive setup wizard for AWS credentials and project configuration."""
    wizard = SetupWizard()
    success = wizard.run()
    sys.exit(0 if success else 1)


@cli.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', required=True, help='Environment (dev/staging/prod)')
@click.option('--region', '-r', default='us-west-1', help='AWS region')
@click.option('--skip', '-s', multiple=True, help='Categories to skip')
@click.option('--config-only', is_flag=True, help='Only validate configuration files')
@click.option('--output', '-o', type=click.Choice(['console', 'json', 'html']), default='console')
def validate(project, environment, region, skip, config_only, output):
    """Run pre-deployment validation checks."""
    try:
        all_valid = True
        combined_report = {
            'project': project,
            'environment': environment,
            'validations': {}
        }
        
        # Configuration validation
        from config_validation.validator import ConfigurationValidator
        config_validator = ConfigurationValidator(project)
        config_valid, config_result = config_validator.validate_environment(environment)
        combined_report['validations']['configuration'] = config_result
        
        if not config_valid:
            all_valid = False
            click.echo("❌ Configuration validation failed")
            for error in config_result['errors']:
                click.echo(f"  - {error}")
        else:
            click.echo("✅ Configuration validation passed")
        
        # If config-only flag is set, stop here
        if config_only:
            sys.exit(0 if config_valid else 1)
        
        # Deployment validation
        validator = PreDeploymentValidator(project, environment, region)
        checks = validator.validate_all(skip_categories=list(skip))
        report = validator.generate_report(checks)
        combined_report['validations']['deployment'] = report
        
        if not report['ready_to_deploy']:
            all_valid = False
        
        if output == 'console':
            validator.print_report(report)
        elif output == 'json':
            import json
            click.echo(json.dumps(combined_report, indent=2))
        elif output == 'html':
            # Generate HTML report
            html = generate_html_report(report)
            output_file = f"validation-{project}-{environment}.html"
            with open(output_file, 'w') as f:
                f.write(html)
            click.echo(f"HTML report saved to {output_file}")
        
        # Exit with error if not ready to deploy
        if not all_valid:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', required=True, help='Environment (dev/staging/prod)')
@click.option('--region', '-r', default='us-west-1', help='AWS region')
@click.option('--output', '-o', type=click.Choice(['console', 'json', 'html']), default='console')
def audit_security(project, environment, region, output):
    """Run security audit on deployed resources."""
    try:
        auditor = SecurityAuditor(project, environment, region)
        issues = auditor.audit_all()
        report = auditor.generate_report(issues)
        
        if output == 'console':
            print_security_report(report)
        elif output == 'json':
            import json
            click.echo(json.dumps(report, indent=2))
        elif output == 'html':
            html = generate_security_html_report(report)
            output_file = f"security-audit-{project}-{environment}.html"
            with open(output_file, 'w') as f:
                f.write(html)
            click.echo(f"HTML report saved to {output_file}")
        
        # Exit with error if critical issues found
        if report['summary']['critical'] > 0:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', required=True, help='Environment (dev/staging/prod)')
@click.option('--region', '-r', default='us-west-1', help='AWS region')
@click.option('--output', '-o', type=click.Choice(['console', 'json']), default='console')
def check_compliance(project, environment, region, output):
    """Check AWS Well-Architected Framework compliance."""
    try:
        checker = ComplianceChecker(project, environment, region)
        checks = checker.check_all_pillars()
        report = checker.generate_report(checks)
        
        if output == 'console':
            print_compliance_report(report)
        elif output == 'json':
            import json
            click.echo(json.dumps(report, indent=2))
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', required=True, help='Environment (dev/staging/prod)')
@click.option('--region', '-r', default='us-west-1', help='AWS region')
@click.option('--template', '-t', help='CloudFormation template path')
@click.option('--usage-profile', '-u', help='Usage profile JSON file')
@click.option('--monthly-budget', '-b', type=float, help='Monthly budget for alerts')
def estimate_cost(project, environment, region, template, usage_profile, monthly_budget):
    """Estimate deployment costs."""
    try:
        estimator = CostEstimator(project, environment, region)
        
        if template:
            # Estimate from CloudFormation template
            report = estimator.estimate_stack_cost(template)
        elif usage_profile:
            # Estimate from usage profile
            import json
            with open(usage_profile, 'r') as f:
                profile = json.load(f)
            report = estimator.estimate_application_cost(profile)
        else:
            # Use default usage profile
            default_profile = {
                'api_requests_per_month': 1_000_000,
                'avg_lambda_duration_ms': 100,
                'lambda_memory_mb': 512,
                'database_operations': {
                    'reads_per_month': 5_000_000,
                    'writes_per_month': 500_000,
                    'storage_gb': 20
                },
                'storage_gb': 100,
                'uploads_per_month': 5_000,
                'downloads_per_month': 50_000,
                'cdn_traffic_gb': 500,
                'cdn_requests_per_month': 5_000_000,
                'monthly_active_users': 10_000
            }
            report = estimator.estimate_application_cost(default_profile)
        
        # Print report
        print_cost_report(report)
        
        # Generate budget alert template if requested
        if monthly_budget:
            alert_template = estimator.generate_cost_alert_template(monthly_budget)
            alert_file = f"budget-alerts-{project}.json"
            import json
            with open(alert_file, 'w') as f:
                json.dump(alert_template, f, indent=2)
            click.echo(f"\nBudget alert template saved to {alert_file}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--days', '-d', default=30, type=int, help='Number of days to analyze')
@click.option('--profile', help='AWS profile to use')
def analyze_cost(project, days, profile):
    """Analyze actual AWS costs for the project."""
    try:
        config = get_project_config(project)
        analyzer = CostAnalyzer(config, profile)
        
        # Get cost data
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        costs = analyzer.get_project_costs(start_date, end_date)
        forecast = analyzer.get_cost_forecast()
        anomalies = analyzer.get_cost_anomalies()
        
        # Print report
        click.echo(f"\n💰 Cost Analysis for {project}")
        click.echo("=" * 60)
        
        period = costs.get('period', {})
        click.echo(f"Period: {period.get('start')} to {period.get('end')}")
        click.echo(f"Total Cost: ${costs.get('total_cost', 0):.2f}")
        
        # Service breakdown
        click.echo("\n📊 Cost by Service:")
        services = costs.get('services', {})
        for service, cost in sorted(services.items(), key=lambda x: x[1], reverse=True):
            if cost > 0:
                click.echo(f"  {service}: ${cost:.2f}")
        
        # Forecast
        click.echo("\n🔮 Cost Forecast:")
        click.echo(f"  Current Daily Average: ${forecast.get('current_daily_average', 0):.2f}")
        click.echo(f"  Weekly Trend: {forecast.get('weekly_trend_percent', 0):.1f}%")
        click.echo(f"  30-Day Projection: ${forecast.get('projected_cost', 0):.2f}")
        
        # Anomalies
        if anomalies:
            click.echo("\n🚨 Cost Anomalies Detected:")
            for anomaly in anomalies[:5]:  # Show top 5
                click.echo(f"  {anomaly['date']}: ${anomaly['cost']:.2f} "
                          f"({anomaly['change_percent']:.1f}% change)")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Helper functions for report formatting
def print_security_report(report):
    """Print security report to console."""
    click.echo("\n🔒 Security Audit Report")
    click.echo("=" * 60)
    click.echo(f"Project: {report['project']} | Environment: {report['environment']}")
    click.echo(f"Total Issues: {report['total_issues']}")
    
    # Summary by severity
    click.echo("\n📊 Issues by Severity:")
    for severity in ['critical', 'high', 'medium', 'low', 'info']:
        count = report['summary'][severity]
        if count > 0:
            emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 
                    'low': '🔵', 'info': '⚪'}.get(severity, '')
            click.echo(f"  {emoji} {severity.upper()}: {count}")
    
    # Critical and high issues
    critical_high = [i for i in report['detailed_issues'] 
                     if i['severity'] in ['CRITICAL', 'HIGH']]
    if critical_high:
        click.echo("\n⚠️  Critical/High Issues:")
        for issue in critical_high[:10]:  # Show top 10
            click.echo(f"\n  • {issue['resource_type']} - {issue['issue_type']}")
            click.echo(f"    Resource: {issue['resource_id']}")
            click.echo(f"    {issue['description']}")
            if issue.get('recommendation'):
                click.echo(f"    Fix: {issue['recommendation']}")


def print_compliance_report(report):
    """Print compliance report to console."""
    click.echo("\n📋 Well-Architected Compliance Report")
    click.echo("=" * 60)
    click.echo(f"Project: {report['project']} | Environment: {report['environment']}")
    click.echo(f"Compliance Score: {report['compliance_score']}%")
    
    # Summary
    click.echo("\n📊 Check Summary:")
    click.echo(f"  ✅ Passed: {report['summary']['pass']}")
    click.echo(f"  ❌ Failed: {report['summary']['fail']}")
    click.echo(f"  ⚠️  Warnings: {report['summary']['warning']}")
    
    # By pillar
    click.echo("\n🏛️  Results by Pillar:")
    for pillar, stats in report['by_pillar'].items():
        total = sum(stats.values()) - len(stats.get('checks', []))
        passed = stats['pass']
        percentage = (passed / total * 100) if total > 0 else 0
        click.echo(f"  {pillar}: {passed}/{total} ({percentage:.0f}%)")


def print_cost_report(report):
    """Print cost estimation report to console."""
    click.echo("\n💰 Cost Estimation Report")
    click.echo("=" * 60)
    click.echo(f"Project: {report['project']} | Environment: {report['environment']}")
    
    # Summary
    summary = report['summary']
    click.echo("\n📊 Estimated Monthly Costs:")
    click.echo(f"  Minimum: ${summary['monthly_cost_estimate']['minimum']:.2f}")
    click.echo(f"  Maximum: ${summary['monthly_cost_estimate']['maximum']:.2f}")
    click.echo(f"  Average: ${summary['monthly_cost_estimate']['average']:.2f}")
    
    click.echo("\n📊 Estimated Annual Costs:")
    click.echo(f"  Average: ${summary['annual_cost_estimate']['average']:.2f}")
    
    # By service
    click.echo("\n💵 Cost Breakdown by Service:")
    for service, data in report['breakdown_by_service'].items():
        avg = (data['monthly_min'] + data['monthly_max']) / 2
        click.echo(f"  {service}: ${avg:.2f}/month")
        for resource in data['resources']:
            click.echo(f"    - {resource}")
    
    # Optimization tips
    if report.get('cost_optimization_tips'):
        click.echo("\n💡 Cost Optimization Tips:")
        for tip in report['cost_optimization_tips'][:5]:
            click.echo(f"  • {tip}")


def generate_html_report(report):
    """Generate HTML validation report."""
    # Simple HTML template
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Validation Report - {report['project']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .pass {{ color: green; }}
            .fail {{ color: red; }}
            .warning {{ color: orange; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Pre-Deployment Validation Report</h1>
        <p>Project: {report['project']} | Environment: {report['environment']}</p>
        <p>Ready to Deploy: <span class="{'pass' if report['ready_to_deploy'] else 'fail'}">
            {'Yes' if report['ready_to_deploy'] else 'No'}</span></p>
        
        <h2>Summary</h2>
        <ul>
            <li>Passed: {report['summary']['pass']}</li>
            <li>Failed: {report['summary']['fail']}</li>
            <li>Warnings: {report['summary']['warning']}</li>
        </ul>
        
        <h2>Detailed Checks</h2>
        <table>
            <tr>
                <th>Category</th>
                <th>Check</th>
                <th>Status</th>
                <th>Message</th>
            </tr>
            {''.join(f"<tr><td>{c['category']}</td><td>{c['name']}</td>"
                     f"<td class='{c['status'].lower()}'>{c['status']}</td>"
                     f"<td>{c['message']}</td></tr>"
                     for c in report['detailed_checks'])}
        </table>
    </body>
    </html>
    """


def generate_security_html_report(report):
    """Generate HTML security report."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Security Audit - {report['project']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .critical {{ color: darkred; font-weight: bold; }}
            .high {{ color: red; }}
            .medium {{ color: orange; }}
            .low {{ color: blue; }}
            .info {{ color: gray; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Security Audit Report</h1>
        <p>Project: {report['project']} | Environment: {report['environment']}</p>
        
        <h2>Summary</h2>
        <ul>
            <li class="critical">Critical: {report['summary']['critical']}</li>
            <li class="high">High: {report['summary']['high']}</li>
            <li class="medium">Medium: {report['summary']['medium']}</li>
            <li class="low">Low: {report['summary']['low']}</li>
            <li class="info">Info: {report['summary']['info']}</li>
        </ul>
        
        <h2>Security Issues</h2>
        <table>
            <tr>
                <th>Severity</th>
                <th>Resource Type</th>
                <th>Resource</th>
                <th>Issue</th>
                <th>Recommendation</th>
            </tr>
            {''.join(f"<tr><td class='{i['severity'].lower()}'>{i['severity']}</td>"
                     f"<td>{i['resource_type']}</td><td>{i['resource_id']}</td>"
                     f"<td>{i['description']}</td><td>{i['recommendation']}</td></tr>"
                     for i in report['detailed_issues'])}
        </table>
    </body>
    </html>
    """


if __name__ == '__main__':
    cli()