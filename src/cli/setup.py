"""Interactive setup wizard for AWS credentials and project configuration."""

import configparser
import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config import ProjectConfig, get_project_config


class SetupWizard:
    """Interactive setup wizard for project configuration."""

    def __init__(self):
        """Initialize the setup wizard."""
        self.config = None
        self.aws_config_path = Path.home() / ".aws"
        self.project_root = Path.cwd()

    def run(self) -> bool:
        """Run the interactive setup wizard.

        Returns:
            True if setup completed successfully
        """
        print("🧙 Welcome to the Project Setup Wizard!")
        print("=" * 50)
        print()

        # Check for existing configuration
        if self._check_existing_config():
            if not self._confirm(
                "Configuration already exists. Do you want to reconfigure?"
            ):
                print("Setup cancelled.")
                return False

        # Run setup steps
        steps = [
            ("AWS Credentials", self._setup_aws_credentials),
            ("Project Configuration", self._setup_project_config),
            ("Deployment Environments", self._setup_environments),
            ("Feature Flags", self._setup_features),
            ("Validation", self._validate_setup),
        ]

        for step_name, step_func in steps:
            print(f"\n📋 {step_name}")
            print("-" * 40)

            try:
                if not step_func():
                    print(f"❌ {step_name} setup failed")
                    return False
            except KeyboardInterrupt:
                print("\n\n⚠️  Setup cancelled by user")
                return False
            except Exception as e:
                print(f"❌ Error during {step_name}: {e}")
                return False

        print("\n✅ Setup completed successfully!")
        self._show_next_steps()
        return True

    def _check_existing_config(self) -> bool:
        """Check if configuration already exists."""
        config_files = [
            self.project_root / "config" / "base.yaml",
            self.aws_config_path / "credentials",
            self.aws_config_path / "config",
        ]

        return any(f.exists() for f in config_files)

    def _setup_aws_credentials(self) -> bool:
        """Set up AWS credentials interactively."""
        print("\nLet's configure your AWS credentials.")
        print("You can choose from the following options:")
        print("1. Use existing AWS profile")
        print("2. Create new AWS profile")
        print("3. Use environment variables (CI/CD)")
        print("4. Use IAM role (EC2/Lambda)")

        choice = self._get_choice("Select option", ["1", "2", "3", "4"])

        if choice == "1":
            return self._use_existing_profile()
        elif choice == "2":
            return self._create_new_profile()
        elif choice == "3":
            return self._setup_env_credentials()
        else:
            return self._setup_iam_role()

    def _use_existing_profile(self) -> bool:
        """Use an existing AWS profile."""
        profiles = self._list_aws_profiles()

        if not profiles:
            print("No AWS profiles found.")
            return self._create_new_profile()

        print("\nAvailable profiles:")
        for i, profile in enumerate(profiles, 1):
            print(f"{i}. {profile}")

        profile_choice = self._get_choice(
            "Select profile number", [str(i) for i in range(1, len(profiles) + 1)]
        )

        selected_profile = profiles[int(profile_choice) - 1]

        # Test the profile
        if self._test_aws_credentials(selected_profile):
            self._save_config("aws_profile", selected_profile)
            print(f"✅ Using AWS profile: {selected_profile}")
            return True
        else:
            print(f"❌ Failed to validate profile: {selected_profile}")
            return False

    def _create_new_profile(self) -> bool:
        """Create a new AWS profile."""
        print("\nCreating new AWS profile...")

        profile_name = self._get_input("Profile name", default="default")
        access_key = self._get_input("AWS Access Key ID")
        secret_key = getpass.getpass("AWS Secret Access Key: ")
        region = self._get_input("AWS Region", default="us-west-1")

        # Create AWS config directory if it doesn't exist
        self.aws_config_path.mkdir(exist_ok=True)

        # Update credentials file
        credentials_file = self.aws_config_path / "credentials"
        credentials = configparser.ConfigParser()

        if credentials_file.exists():
            credentials.read(credentials_file)

        credentials[profile_name] = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }

        with open(credentials_file, "w") as f:
            credentials.write(f)

        # Update config file
        config_file = self.aws_config_path / "config"
        config = configparser.ConfigParser()

        if config_file.exists():
            config.read(config_file)

        config[f"profile {profile_name}"] = {"region": region, "output": "json"}

        with open(config_file, "w") as f:
            config.write(f)

        # Test the credentials
        if self._test_aws_credentials(profile_name):
            self._save_config("aws_profile", profile_name)
            print(f"✅ Created and configured AWS profile: {profile_name}")
            return True
        else:
            print("❌ Failed to validate AWS credentials")
            return False

    def _setup_env_credentials(self) -> bool:
        """Set up environment variable credentials."""
        print("\nFor CI/CD environments, set these environment variables:")
        print("  AWS_ACCESS_KEY_ID")
        print("  AWS_SECRET_ACCESS_KEY")
        print("  AWS_DEFAULT_REGION")
        print()

        # Create example .env file
        env_example = """# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-west-1

# Optional
AWS_SESSION_TOKEN=optional_session_token
"""

        env_file = self.project_root / ".env.example"
        with open(env_file, "w") as f:
            f.write(env_example)

        print(f"Created {env_file} with example environment variables")

        # For GitHub Actions
        print("\nFor GitHub Actions, add these secrets:")
        print("  AWS_ACCESS_KEY_ID")
        print("  AWS_SECRET_ACCESS_KEY")
        print("  AWS_REGION")

        self._save_config("credentials_type", "environment")
        return True

    def _setup_iam_role(self) -> bool:
        """Set up IAM role configuration."""
        print("\nUsing IAM role for authentication.")
        print("This is recommended for EC2 instances and Lambda functions.")

        role_arn = self._get_input("IAM Role ARN (optional)", required=False)

        if role_arn:
            self._save_config("iam_role_arn", role_arn)

        self._save_config("credentials_type", "iam_role")
        print("✅ Configured to use IAM role authentication")
        return True

    def _setup_project_config(self) -> bool:
        """Set up project configuration."""
        print("\nConfiguring project settings...")

        # Get project name
        default_name = self.project_root.name
        project_name = self._get_input("Project name", default=default_name)

        # Get organization
        organization = self._get_input("Organization name", required=False)

        # Get deployment regions
        regions = self._get_regions()

        # Create base configuration
        base_config = {
            "project": {
                "name": project_name,
                "organization": organization,
                "created": datetime.now().isoformat(),
            },
            "aws": {"regions": regions, "primary_region": regions[0]},
        }

        # Save configuration
        config_dir = self.project_root / "config"
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / "base.yaml"

        try:
            import yaml

            with open(config_file, "w") as f:
                yaml.dump(base_config, f, default_flow_style=False)

            print(f"✅ Created project configuration: {config_file}")
            return True

        except ImportError:
            # Fallback to JSON if PyYAML not available
            config_file = config_dir / "base.json"
            with open(config_file, "w") as f:
                json.dump(base_config, f, indent=2)

            print(f"✅ Created project configuration: {config_file}")
            return True

    def _setup_environments(self) -> bool:
        """Set up deployment environments."""
        print("\nConfiguring deployment environments...")

        environments = ["dev", "staging", "prod"]
        print(f"Default environments: {', '.join(environments)}")

        if self._confirm("Do you want to customize environments?"):
            environments = []
            while True:
                env = self._get_input("Environment name (or 'done' to finish)")
                if env.lower() == "done":
                    break
                environments.append(env)

        # Create environment configs
        config_dir = self.project_root / "config" / "environments"
        config_dir.mkdir(exist_ok=True, parents=True)

        for env in environments:
            env_config = {
                "environment": env,
                "settings": {
                    "debug": env == "dev",
                    "monitoring": env in ["staging", "prod"],
                    "auto_scaling": env == "prod",
                },
            }

            env_file = config_dir / f"{env}.yaml"
            try:
                import yaml

                with open(env_file, "w") as f:
                    yaml.dump(env_config, f, default_flow_style=False)
            except ImportError:
                env_file = config_dir / f"{env}.json"
                with open(env_file, "w") as f:
                    json.dump(env_config, f, indent=2)

        print(f"✅ Created {len(environments)} environment configurations")
        return True

    def _setup_features(self) -> bool:
        """Set up feature flags."""
        print("\nConfiguring features...")

        features = {
            "cognito_auth": self._confirm("Enable AWS Cognito authentication?"),
            "waf_protection": self._confirm("Enable WAF protection?"),
            "cloudfront_cdn": self._confirm("Enable CloudFront CDN?"),
            "monitoring": self._confirm("Enable CloudWatch monitoring?"),
            "auto_backup": self._confirm("Enable automated backups?"),
        }

        self._save_config("features", features)

        enabled_count = sum(1 for enabled in features.values() if enabled)
        print(f"✅ Enabled {enabled_count} features")
        return True

    def _validate_setup(self) -> bool:
        """Validate the setup configuration."""
        print("\nValidating configuration...")

        checks = [
            ("AWS credentials", self._validate_aws_credentials),
            ("Project structure", self._validate_project_structure),
            ("Dependencies", self._validate_dependencies),
        ]

        all_valid = True
        for check_name, check_func in checks:
            print(f"  Checking {check_name}... ", end="", flush=True)
            if check_func():
                print("✅")
            else:
                print("❌")
                all_valid = False

        return all_valid

    def _validate_aws_credentials(self) -> bool:
        """Validate AWS credentials are working."""
        try:
            session = boto3.Session()
            sts = session.client("sts")
            sts.get_caller_identity()
            return True
        except Exception:
            return False

    def _validate_project_structure(self) -> bool:
        """Validate project structure exists."""
        required_dirs = ["config", "src", "tests"]
        return all((self.project_root / d).exists() for d in required_dirs)

    def _validate_dependencies(self) -> bool:
        """Validate required dependencies are installed."""
        try:
            import boto3
            import yaml

            return True
        except ImportError:
            return False

    def _test_aws_credentials(self, profile: Optional[str] = None) -> bool:
        """Test AWS credentials."""
        try:
            session_args = {}
            if profile:
                session_args["profile_name"] = profile

            session = boto3.Session(**session_args)
            sts = session.client("sts")
            response = sts.get_caller_identity()

            print(f"\n✅ AWS credentials valid")
            print(f"   Account: {response['Account']}")
            print(f"   User/Role: {response['Arn']}")
            return True

        except NoCredentialsError:
            print("❌ No AWS credentials found")
            return False
        except ClientError as e:
            print(f"❌ AWS credential error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

    def _list_aws_profiles(self) -> List[str]:
        """List available AWS profiles."""
        profiles = []

        credentials_file = self.aws_config_path / "credentials"
        if credentials_file.exists():
            config = configparser.ConfigParser()
            config.read(credentials_file)
            profiles.extend(config.sections())

        config_file = self.aws_config_path / "config"
        if config_file.exists():
            config = configparser.ConfigParser()
            config.read(config_file)
            for section in config.sections():
                if section.startswith("profile "):
                    profile_name = section.replace("profile ", "")
                    if profile_name not in profiles:
                        profiles.append(profile_name)

        return profiles

    def _get_regions(self) -> List[str]:
        """Get AWS regions from user."""
        print("\nSelect AWS regions for deployment:")

        common_regions = [
            "us-east-1",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1",
        ]

        print("Common regions:")
        for i, region in enumerate(common_regions, 1):
            print(f"{i}. {region}")

        regions = []
        while True:
            choice = self._get_input(
                "Select region number or enter custom region (or 'done')"
            )

            if choice.lower() == "done":
                break

            if choice.isdigit() and 1 <= int(choice) <= len(common_regions):
                region = common_regions[int(choice) - 1]
            else:
                region = choice

            if region not in regions:
                regions.append(region)
                print(f"Added region: {region}")

        if not regions:
            regions = ["us-west-1"]  # Default

        return regions

    def _show_next_steps(self) -> None:
        """Show next steps after setup."""
        print("\n📚 Next Steps:")
        print("-" * 40)
        print("1. Review generated configuration files:")
        print("   - config/base.yaml")
        print("   - config/environments/*.yaml")
        print()
        print("2. Deploy infrastructure:")
        print("   project-deploy --environment dev")
        print()
        print("3. Run tests:")
        print("   project-test smoke")
        print()
        print("4. View deployment status:")
        print("   project-cloudformation list")

    def _confirm(self, prompt: str) -> bool:
        """Get yes/no confirmation from user."""
        while True:
            response = input(f"{prompt} (y/n): ").strip().lower()
            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            else:
                print("Please enter 'y' or 'n'")

    def _get_choice(self, prompt: str, choices: List[str]) -> str:
        """Get a choice from user."""
        while True:
            response = input(f"{prompt} ({'/'.join(choices)}): ").strip()
            if response in choices:
                return response
            else:
                print(f"Please enter one of: {', '.join(choices)}")

    def _get_input(
        self, prompt: str, default: Optional[str] = None, required: bool = True
    ) -> str:
        """Get input from user."""
        if default:
            prompt = f"{prompt} [{default}]"

        while True:
            response = input(f"{prompt}: ").strip()

            if not response and default:
                return default

            if response or not required:
                return response

            print("This field is required")

    def _save_config(self, key: str, value: Any) -> None:
        """Save configuration value."""
        if not self.config:
            self.config = {}

        self.config[key] = value

        # Save to file for reference
        setup_file = self.project_root / ".setup_config.json"
        with open(setup_file, "w") as f:
            json.dump(self.config, f, indent=2)


def main():
    """Run the setup wizard."""
    wizard = SetupWizard()
    success = wizard.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
