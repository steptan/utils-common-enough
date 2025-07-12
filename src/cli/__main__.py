#!/usr/bin/env python3
"""Main CLI entry point for project utilities."""

import sys
from typing import Optional, Type

import click

# Import all command groups
try:
    from .deploy import main as deploy_commands
except ImportError:
    deploy_commands: Optional[click.Group] = None

try:
    from .cloudformation import main as cf_commands
except ImportError:
    cf_commands: Optional[click.Group] = None

try:
    from .lambda_cmd import main as lambda_commands
except ImportError:
    lambda_commands: Optional[click.Group] = None

try:
    from .iam import main as iam_commands
except ImportError:
    iam_commands = None

try:
    from .database import main as db_commands
except ImportError:
    db_commands: Optional[click.Group] = None

try:
    from .test import main as test_commands
except ImportError:
    test_commands: Optional[click.Group] = None

# Import new commands
try:
    from .setup import SetupWizard
except ImportError:
    SetupWizard: Optional[Type] = None

# Import dynamodb commands
try:
    from .dynamodb import dynamodb as dynamodb_commands
except ImportError:
    dynamodb_commands = None
try:
    from deployment.validation import PreDeploymentValidator
except ImportError:
    PreDeploymentValidator = None

try:
    from security.audit import SecurityAuditor
    from security.compliance import ComplianceChecker
except ImportError:
    SecurityAuditor = None
    ComplianceChecker = None

try:
    from cost.analyzer import CostAnalyzer
    from cost.estimator import CostEstimator
except ImportError:
    CostEstimator = None
    CostAnalyzer = None

try:
    from config import get_project_config
except ImportError:
    get_project_config = None


@click.group()
@click.version_option()
def cli() -> None:
    """Project deployment and management utilities.

    A comprehensive toolkit for AWS project deployment, management, and monitoring.
    """
    pass


# Add existing command groups
if deploy_commands:
    cli.add_command(deploy_commands, name="deploy")
if cf_commands:
    cli.add_command(cf_commands, name="cloudformation")
if lambda_commands:
    cli.add_command(lambda_commands, name="lambda")
if iam_commands:
    cli.add_command(iam_commands, name="iam")
if db_commands:
    cli.add_command(db_commands, name="database")
if test_commands:
    cli.add_command(test_commands, name="test")
if dynamodb_commands:
    cli.add_command(dynamodb_commands, name="dynamodb")


# New commands
@cli.command()
def setup() -> None:
    """Run interactive setup wizard for AWS credentials and project configuration."""
    wizard = SetupWizard()
    success = wizard.run()
    sys.exit(0 if success else 1)


@cli.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--region", "-r", default="us-west-1", help="AWS region")
@click.option("--skip", "-s", multiple=True, help="Categories to skip")
@click.option("--config-only", is_flag=True, help="Only validate configuration files")
@click.option(
    "--output", "-o", type=click.Choice(["console", "json", "html"]), default="console"
)
def validate(project: str, environment: str, region: str, skip: tuple, config_only: bool, output: str) -> None:
    """Run pre-deployment validation checks."""
    try:
        all_valid = True
        combined_report = {
            "project": project,
            "environment": environment,
            "validations": {},
        }

        # Configuration validation
        try:
            from config_validation.validator import ConfigurationValidator

            config_validator = ConfigurationValidator(project)
        except ImportError:
            click.echo("⚠️  Configuration validator not available")
            config_validator = None
        config_valid, config_result = config_validator.validate_environment(environment)
        combined_report["validations"]["configuration"] = config_result

        if not config_valid:
            all_valid = False
            click.echo("❌ Configuration validation failed")
            for error in config_result["errors"]:
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
        combined_report["validations"]["deployment"] = report

        if not report["ready_to_deploy"]:
            all_valid = False

        if output == "console":
            validator.print_report(report)
        elif output == "json":
            import json

            click.echo(json.dumps(combined_report, indent=2))
        elif output == "html":
            # Generate HTML report
            html = generate_html_report(report)
            output_file = f"validation-{project}-{environment}.html"
            with open(output_file, "w") as f:
                f.write(html)
            click.echo(f"HTML report saved to {output_file}")

        # Exit with error if not ready to deploy
        if not all_valid:
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--region", "-r", default="us-west-1", help="AWS region")
@click.option(
    "--output", "-o", type=click.Choice(["console", "json", "html"]), default="console"
)
def audit_security(project: str, environment: str, region: str, output: str) -> None:
    """Run security audit on deployed resources."""
    try:
        auditor = SecurityAuditor(project, environment, region)
        issues = auditor.audit_all()
        report = auditor.generate_report(issues)

        if output == "console":
            print_security_report(report)
        elif output == "json":
            import json

            click.echo(json.dumps(report, indent=2))
        elif output == "html":
            html = generate_security_html_report(report)
            output_file = f"security-audit-{project}-{environment}.html"
            with open(output_file, "w") as f:
                f.write(html)
            click.echo(f"HTML report saved to {output_file}")

        # Exit with error if critical issues found
        if report["summary"]["critical"] > 0:
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--region", "-r", default="us-west-1", help="AWS region")
@click.option(
    "--output", "-o", type=click.Choice(["console", "json"]), default="console"
)
def check_compliance(project: str, environment: str, region: str, output: str) -> None:
    """Check AWS Well-Architected Framework compliance."""
    try:
        checker = ComplianceChecker(project, environment, region)
        checks = checker.check_all_pillars()
        report = checker.generate_report(checks)

        if output == "console":
            print_compliance_report(report)
        elif output == "json":
            import json

            click.echo(json.dumps(report, indent=2))

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--region", "-r", default="us-west-1", help="AWS region")
@click.option("--template", "-t", help="CloudFormation template path")
@click.option("--usage-profile", "-u", help="Usage profile JSON file")
@click.option("--monthly-budget", "-b", type=float, help="Monthly budget for alerts")
def estimate_cost(
    project: str, environment: str, region: str, template: Optional[str], usage_profile: Optional[str], monthly_budget: Optional[float]
) -> None:
    """Estimate deployment costs."""
    try:
        estimator = CostEstimator(project, environment, region)

        if template:
            # Estimate from CloudFormation template
            report = estimator.estimate_stack_cost(template)
        elif usage_profile:
            # Estimate from usage profile
            import json

            with open(usage_profile, "r") as f:
                profile = json.load(f)
            report = estimator.estimate_application_cost(profile)
        else:
            # Use default usage profile
            default_profile = {
                "api_requests_per_month": 1_000_000,
                "avg_lambda_duration_ms": 100,
                "lambda_memory_mb": 512,
                "database_operations": {
                    "reads_per_month": 5_000_000,
                    "writes_per_month": 500_000,
                    "storage_gb": 20,
                },
                "storage_gb": 100,
                "uploads_per_month": 5_000,
                "downloads_per_month": 50_000,
                "cdn_traffic_gb": 500,
                "cdn_requests_per_month": 5_000_000,
                "monthly_active_users": 10_000,
            }
            report = estimator.estimate_application_cost(default_profile)

        # Print report
        print_cost_report(report)

        # Generate budget alert template if requested
        if monthly_budget:
            alert_template = estimator.generate_cost_alert_template(monthly_budget)
            alert_file = f"budget-alerts-{project}.json"
            import json

            with open(alert_file, "w") as f:
                json.dump(alert_template, f, indent=2)
            click.echo(f"\nBudget alert template saved to {alert_file}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--days", "-d", default=30, type=int, help="Number of days to analyze")
@click.option("--profile", help="AWS profile to use")
def analyze_cost(project: str, days: int, profile: Optional[str]) -> None:
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

        period = costs.get("period", {})
        click.echo(f"Period: {period.get('start')} to {period.get('end')}")
        click.echo(f"Total Cost: ${costs.get('total_cost', 0):.2f}")

        # Service breakdown
        click.echo("\n📊 Cost by Service:")
        services = costs.get("services", {})
        for service, cost in sorted(services.items(), key=lambda x: x[1], reverse=True):
            if cost > 0:
                click.echo(f"  {service}: ${cost:.2f}")

        # Forecast
        click.echo("\n🔮 Cost Forecast:")
        click.echo(
            f"  Current Daily Average: ${forecast.get('current_daily_average', 0):.2f}"
        )
        click.echo(f"  Weekly Trend: {forecast.get('weekly_trend_percent', 0):.1f}%")
        click.echo(f"  30-Day Projection: ${forecast.get('projected_cost', 0):.2f}")

        # Anomalies
        if anomalies:
            click.echo("\n🚨 Cost Anomalies Detected:")
            for anomaly in anomalies[:5]:  # Show top 5
                click.echo(
                    f"  {anomaly['date']}: ${anomaly['cost']:.2f} "
                    f"({anomaly['change_percent']:.1f}% change)"
                )

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Helper functions for report formatting
def print_security_report(report: dict) -> None:
    """Print security report to console."""
    click.echo("\n🔒 Security Audit Report")
    click.echo("=" * 60)
    click.echo(f"Project: {report['project']} | Environment: {report['environment']}")
    click.echo(f"Total Issues: {report['total_issues']}")

    # Summary by severity
    click.echo("\n📊 Issues by Severity:")
    for severity in ["critical", "high", "medium", "low", "info"]:
        count = report["summary"][severity]
        if count > 0:
            emoji = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🔵",
                "info": "⚪",
            }.get(severity, "")
            click.echo(f"  {emoji} {severity.upper()}: {count}")

    # Critical and high issues
    critical_high = [
        i for i in report["detailed_issues"] if i["severity"] in ["CRITICAL", "HIGH"]
    ]
    if critical_high:
        click.echo("\n⚠️  Critical/High Issues:")
        for issue in critical_high[:10]:  # Show top 10
            click.echo(f"\n  • {issue['resource_type']} - {issue['issue_type']}")
            click.echo(f"    Resource: {issue['resource_id']}")
            click.echo(f"    {issue['description']}")
            if issue.get("recommendation"):
                click.echo(f"    Fix: {issue['recommendation']}")


def print_compliance_report(report: dict) -> None:
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
    for pillar, stats in report["by_pillar"].items():
        total = sum(stats.values()) - len(stats.get("checks", []))
        passed = stats["pass"]
        percentage = (passed / total * 100) if total > 0 else 0
        click.echo(f"  {pillar}: {passed}/{total} ({percentage:.0f}%)")


def print_cost_report(report: dict) -> None:
    """Print cost estimation report to console."""
    click.echo("\n💰 Cost Estimation Report")
    click.echo("=" * 60)
    click.echo(f"Project: {report['project']} | Environment: {report['environment']}")

    # Summary
    summary = report["summary"]
    click.echo("\n📊 Estimated Monthly Costs:")
    click.echo(f"  Minimum: ${summary['monthly_cost_estimate']['minimum']:.2f}")
    click.echo(f"  Maximum: ${summary['monthly_cost_estimate']['maximum']:.2f}")
    click.echo(f"  Average: ${summary['monthly_cost_estimate']['average']:.2f}")

    click.echo("\n📊 Estimated Annual Costs:")
    click.echo(f"  Average: ${summary['annual_cost_estimate']['average']:.2f}")

    # By service
    click.echo("\n💵 Cost Breakdown by Service:")
    for service, data in report["breakdown_by_service"].items():
        avg = (data["monthly_min"] + data["monthly_max"]) / 2
        click.echo(f"  {service}: ${avg:.2f}/month")
        for resource in data["resources"]:
            click.echo(f"    - {resource}")

    # Optimization tips
    if report.get("cost_optimization_tips"):
        click.echo("\n💡 Cost Optimization Tips:")
        for tip in report["cost_optimization_tips"][:5]:
            click.echo(f"  • {tip}")


def generate_html_report(report: dict) -> str:
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


def generate_security_html_report(report: dict) -> str:
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


# Claude settings management commands
@cli.command()
@click.option(
    "--projects",
    multiple=True,
    help="Specific projects to deploy to (default: all projects)",
)
@click.option("--settings-dir", type=click.Path(exists=True), help="Directory containing settings files")
def deploy_settings(projects: tuple, settings_dir: str) -> None:
    """Deploy Claude settings to projects."""
    from scripts.deploy_claude_settings import ClaudeSettingsDeployer
    
    deployer = ClaudeSettingsDeployer(Path(settings_dir) if settings_dir else None)
    
    if projects:
        success = True
        for project in projects:
            if project in deployer.projects:
                success &= deployer.deploy_project(project)
            elif project in deployer.special_projects:
                success &= deployer.deploy_special_project(
                    project, deployer.special_projects[project]
                )
            else:
                click.echo(f"❌ Unknown project: {project}")
                success = False
        sys.exit(0 if success else 1)
    else:
        success = deployer.deploy_all()
        sys.exit(0 if success else 1)


@cli.command()
@click.option("--backup-dir", type=click.Path(), help="Directory containing backup files")
def rollback_settings(backup_dir: str) -> None:
    """Rollback Claude settings from backup."""
    from scripts.rollback_claude_settings import ClaudeSettingsRollback
    
    rollback = ClaudeSettingsRollback(Path(backup_dir) if backup_dir else None)
    success = rollback.rollback_all()
    sys.exit(0 if success else 1)


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.argument("command", type=click.Choice(["setup", "push", "pull"]))
@click.option("-m", "--message", help="Commit message for push command")
def setup_submodules(project_path: str, command: str, message: str) -> None:
    """Set up git submodules for a project."""
    from scripts.git_submodules import GitSubmoduleManager
    
    manager = GitSubmoduleManager(Path(project_path))
    
    if command == "setup":
        click.echo("Setting up git submodule configuration...")
        manager.setup_pre_push_hook()
        manager.setup_git_aliases()
        manager.configure_submodule()
        click.echo("\n✨ Git submodule configuration complete!")
    elif command == "push":
        if not message:
            click.echo("❌ Commit message required for push command")
            sys.exit(1)
        success = manager.push_with_submodules(message)
        sys.exit(0 if success else 1)
    elif command == "pull":
        success = manager.pull_with_submodules()
        sys.exit(0 if success else 1)


@cli.group()
def people_cards():
    """People Cards project specific commands."""
    pass


@people_cards.command()
@click.option('--venv/--no-venv', default=True, help='Create virtual environment')
@click.option('--git-submodules/--no-git-submodules', default=True, help='Setup git submodules')
@click.option('--npm/--no-npm', default=True, help='Install npm dependencies')
@click.option('--python-version', default='3.11', help='Python version to use')
def setup_dev(venv, git_submodules, npm, python_version):
    """Set up development environment for people-cards project."""
    import subprocess
    import platform
    from pathlib import Path
    
    project_root = Path.cwd()
    
    click.echo("🚀 People Cards Development Environment Setup")
    click.echo("=" * 50)
    
    # Check Python version
    import sys
    version = sys.version_info
    click.echo(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        click.echo("❌ Python 3.11 or higher is required")
        sys.exit(1)
    
    click.echo("✅ Python version is compatible")
    
    # Setup git submodules
    if git_submodules:
        click.echo("\n📦 Setting up git submodules...")
        try:
            subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
            click.echo("✅ Git submodules initialized")
        except subprocess.CalledProcessError:
            click.echo("⚠️  Git submodules setup failed, continuing anyway...")
    
    # Create virtual environment
    if venv:
        venv_path = project_root / "venv"
        
        if venv_path.exists():
            response = click.confirm("Virtual environment already exists. Recreate it?", default=False)
            if response:
                click.echo("Removing existing virtual environment...")
                if platform.system() == "Windows":
                    subprocess.run("rmdir /s /q venv", shell=True, check=False)
                else:
                    subprocess.run("rm -rf venv", shell=True, check=False)
            else:
                click.echo("Using existing virtual environment")
                venv = False
        
        if venv:
            click.echo("\n📦 Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            click.echo("✅ Virtual environment created")
            
            # Install Python dependencies
            click.echo("\n📦 Installing Python dependencies...")
            if platform.system() == "Windows":
                pip = "venv\\Scripts\\pip"
            else:
                pip = "venv/bin/pip"
            
            subprocess.run([pip, "install", "--upgrade", "pip"], check=True)
            
            if (project_root / "requirements.txt").exists():
                subprocess.run([pip, "install", "-r", "requirements.txt"], check=True)
                click.echo("✅ Python dependencies installed")
            
            # Install utils package
            if (project_root / "utils" / "setup.py").exists():
                subprocess.run([pip, "install", "-e", "utils/"], check=True)
                click.echo("✅ Utils package installed")
    
    # Install npm dependencies
    if npm and (project_root / "package.json").exists():
        click.echo("\n📦 Installing npm dependencies...")
        try:
            subprocess.run(["npm", "install"], check=True)
            click.echo("✅ npm dependencies installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            click.echo("⚠️  npm install failed - make sure Node.js is installed")
    
    # Success message
    click.echo("\n" + "=" * 50)
    click.echo("✨ Development environment setup complete!")
    click.echo("\nNext steps:")
    
    if venv:
        if platform.system() == "Windows":
            click.echo("1. Activate the virtual environment:")
            click.echo("   venv\\Scripts\\activate")
        else:
            click.echo("1. Activate the virtual environment:")
            click.echo("   source venv/bin/activate")
    
    click.echo("\n2. Configure AWS credentials:")
    click.echo("   utils-cli iam setup-credentials --project people-cards")
    click.echo("\n3. Create DynamoDB tables:")
    click.echo("   utils-cli dynamodb ensure-tables --project people-cards --environment dev")
    click.echo("\n4. Start development:")
    click.echo("   npm run dev")


if __name__ == "__main__":
    cli()
