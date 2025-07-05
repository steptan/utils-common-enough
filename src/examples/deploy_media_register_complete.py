#!/usr/bin/env python3
"""
Simple deployment script for the complete Media Register application.

This script deploys the full application with all API endpoints, Lambda functions,
and infrastructure components.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def deploy_complete_application(environment: str = "dev", auto_approve: bool = False):
    """
    Deploy the complete Media Register application.

    Args:
        environment: Target environment (dev, staging, prod)
        auto_approve: Skip confirmation prompts
    """
    print(
        f"🚀 Deploying complete Media Register application to {environment} environment"
    )
    print()

    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)

    try:
        # Step 1: Validate configuration
        print("1️⃣ Validating configuration...")
        result = subprocess.run(
            [sys.executable, "validate_config.py", environment],
            check=True,
            capture_output=True,
            text=True,
        )
        print("   ✅ Configuration validated")
        print()

        # Step 2: Install dependencies
        print("2️⃣ Installing dependencies...")
        subprocess.run(
            ["pip", "install", "-r", "requirements.txt"],
            check=True,
            capture_output=True,
        )
        print("   ✅ Dependencies installed")
        print()

        # Step 3: Bootstrap CDK if needed
        print("3️⃣ Checking CDK bootstrap...")
        try:
            subprocess.run(
                [
                    "aws",
                    "cloudformation",
                    "describe-stacks",
                    "--stack-name",
                    "CDKToolkit",
                ],
                check=True,
                capture_output=True,
            )
            print("   ✅ CDK already bootstrapped")
        except subprocess.CalledProcessError:
            print("   🔄 Bootstrapping CDK...")
            subprocess.run(["cdk", "bootstrap"], check=True)
            print("   ✅ CDK bootstrapped")
        print()

        # Step 4: Synthesize CDK app
        print("4️⃣ Synthesizing CDK application...")
        cmd = [
            "cdk",
            "synth",
            "--app",
            "python examples/complete_media_register_app.py",
            "--context",
            f"environment={environment}",
        ]

        subprocess.run(cmd, check=True)
        print("   ✅ CDK app synthesized successfully")
        print()

        # Step 5: Show deployment diff
        print("5️⃣ Showing deployment changes...")
        diff_cmd = [
            "cdk",
            "diff",
            "--app",
            "python examples/complete_media_register_app.py",
            "--context",
            f"environment={environment}",
        ]

        result = subprocess.run(diff_cmd, capture_output=True, text=True)
        if result.stdout.strip():
            print(result.stdout)
        else:
            print("   📋 No changes detected")
        print()

        # Step 6: Confirmation
        if not auto_approve:
            print("6️⃣ Deployment confirmation")
            response = (
                input(f"   Deploy Media Register to {environment}? [y/N]: ")
                .strip()
                .lower()
            )
            if response not in ["y", "yes"]:
                print("   ⏹️ Deployment cancelled")
                return False
            print()

        # Step 7: Deploy
        print("7️⃣ Deploying infrastructure...")
        deploy_cmd = [
            "cdk",
            "deploy",
            "--app",
            "python examples/complete_media_register_app.py",
            "--context",
            f"environment={environment}",
            "--require-approval",
            "never" if auto_approve else "broadening",
            "--outputs-file",
            f"outputs-{environment}.json",
        ]

        print(f"   🚀 Running: {' '.join(deploy_cmd)}")
        print()

        result = subprocess.run(deploy_cmd, check=True)
        print()
        print("   ✅ Infrastructure deployed successfully")
        print()

        # Step 8: Run health checks
        print("8️⃣ Running health checks...")
        try:
            health_result = subprocess.run(
                [sys.executable, "scripts/health_check.py", environment],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            print("   ✅ Health checks passed")
        except subprocess.CalledProcessError:
            print("   ⚠️ Health checks failed - check logs for details")
        except FileNotFoundError:
            print("   ⚠️ Health check script not found - skipping")
        print()

        # Step 9: Display success information
        print("9️⃣ Deployment completed successfully! 🎉")
        print()

        # Show outputs
        outputs_file = Path(f"outputs-{environment}.json")
        if outputs_file.exists():
            print("📋 Stack Outputs:")
            with open(outputs_file) as f:
                import json

                outputs = json.load(f)
                stack_outputs = list(outputs.values())[0] if outputs else {}

                for key, value in stack_outputs.items():
                    print(f"   {key}: {value}")
            print()

        print("🔗 Next Steps:")
        print("   1. Test the API endpoints:")
        print(f"      curl https://{{ApiGatewayUrl}}/health")
        print()
        print("   2. Access the User Pool for authentication:")
        print(f"      User Pool ID: {{UserPoolId}}")
        print(f"      App Client ID: {{UserPoolClientId}}")
        print()
        print("   3. Deploy frontend application (if available)")
        print(f"      npm run deploy:{environment}")
        print()
        print("   4. Run integration tests:")
        print(f"      python tests/integration_test.py --environment {environment}")
        print()

        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed: {e}")
        if hasattr(e, "stdout") and e.stdout:
            print("STDOUT:", e.stdout)
        if hasattr(e, "stderr") and e.stderr:
            print("STDERR:", e.stderr)
        return False

    except KeyboardInterrupt:
        print("\n⏹️ Deployment cancelled by user")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Deploy complete Media Register application",
        epilog="""Examples:
  python deploy_complete_app.py dev
  python deploy_complete_app.py prod --auto-approve
  python deploy_complete_app.py staging""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "environment",
        nargs="?",
        default="dev",
        choices=["dev", "staging", "prod"],
        help="Target environment (default: dev)",
    )

    parser.add_argument(
        "--auto-approve", action="store_true", help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    # Deploy the application
    success = deploy_complete_application(args.environment, args.auto_approve)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
