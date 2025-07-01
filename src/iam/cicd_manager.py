"""
CI/CD IAM permission management.
"""

import json
import sys
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError

from config import ProjectConfig, get_project_config
from .policies import PolicyGenerator


@dataclass
class IAMCredentials:
    """IAM user credentials."""
    access_key_id: str
    secret_access_key: str
    user_name: str
    policy_arn: str


class CICDPermissionManager:
    """Manage CI/CD permissions for projects."""
    
    def __init__(
        self,
        project_name: str,
        config: Optional[ProjectConfig] = None,
        profile: Optional[str] = None
    ):
        """
        Initialize CI/CD permission manager.
        
        Args:
            project_name: Name of the project
            config: Project configuration
            profile: AWS profile to use
        """
        self.project_name = project_name
        self.config = config or get_project_config(project_name)
        self.profile = profile
        
        # Initialize AWS clients
        session_args = {"region_name": self.config.aws_region}
        if profile:
            session_args["profile_name"] = profile
            
        session = boto3.Session(**session_args)
        self.iam = session.client("iam")
        self.sts = session.client("sts")
        
        # Get account ID
        self.account_id = self._get_account_id()
        
        # Initialize policy generator
        self.policy_generator = PolicyGenerator(self.config)
    
    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        try:
            response = self.sts.get_caller_identity()
            return response["Account"]
        except Exception as e:
            print(f"❌ Failed to get AWS account ID: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _print_success(self, message: str) -> None:
        """Print success message."""
        print(f"✅ {message}")
    
    def _print_warning(self, message: str) -> None:
        """Print warning message."""
        print(f"⚠️  {message}")
    
    def _print_error(self, message: str) -> None:
        """Print error message."""
        print(f"❌ {message}", file=sys.stderr)
    
    def _print_info(self, message: str) -> None:
        """Print info message."""
        print(f"ℹ️  {message}")
    
    def setup_cicd_permissions(self, github_org: Optional[str] = None, github_repo: Optional[str] = None) -> IAMCredentials:
        """
        Set up CI/CD permissions for the project.
        
        Args:
            github_org: GitHub organization (for OIDC setup)
            github_repo: GitHub repository (for OIDC setup)
            
        Returns:
            IAM credentials for CI/CD
        """
        print(f"🔧 Setting up CI/CD permissions for {self.project_name}...")
        print(f"   Region: {self.config.aws_region}")
        print(f"   Account: {self.account_id}")
        print()
        
        # Create or update policy
        policy_name = self.config.format_name(self.config.cicd_policy_pattern)
        policy_arn = self._create_or_update_policy(policy_name)
        
        # Check if we should use OIDC
        if github_org and github_repo:
            # Set up GitHub Actions OIDC
            role_name = f"{self.project_name}-github-actions-role"
            self._setup_github_oidc_role(role_name, policy_arn, github_org, github_repo)
            
            self._print_success("GitHub Actions OIDC setup complete!")
            print()
            print("Add these secrets to your GitHub repository:")
            print(f"   AWS_ROLE_ARN: arn:aws:iam::{self.account_id}:role/{role_name}")
            print(f"   AWS_REGION: {self.config.aws_region}")
            print()
            
            return None  # No credentials needed for OIDC
        else:
            # Traditional IAM user setup
            user_name = self.config.format_name(self.config.cicd_user_pattern)
            credentials = self._setup_iam_user(user_name, policy_arn)
            
            self._print_success("IAM user setup complete!")
            self._print_warning("IMPORTANT: Save these credentials securely!")
            print()
            print("Add these secrets to your CI/CD system:")
            print(f"   AWS_ACCESS_KEY_ID: {credentials.access_key_id}")
            print(f"   AWS_SECRET_ACCESS_KEY: {credentials.secret_access_key}")
            print(f"   AWS_REGION: {self.config.aws_region}")
            print()
            self._print_warning("This is the only time you'll see the secret access key!")
            
            return credentials
    
    def _create_or_update_policy(self, policy_name: str) -> str:
        """Create or update IAM policy."""
        # Generate policy document
        policy_doc = self.policy_generator.generate_cicd_policy(self.account_id)
        policy_json = json.dumps(policy_doc)
        
        # Check if policy exists
        try:
            existing_policies = self.iam.list_policies(
                Scope="Local",
                PathPrefix="/",
                MaxItems=1000
            )
            
            policy_arn = None
            for policy in existing_policies["Policies"]:
                if policy["PolicyName"] == policy_name:
                    policy_arn = policy["Arn"]
                    break
            
            if policy_arn:
                # Update existing policy
                self._print_warning(f"Policy {policy_name} already exists. Creating new version...")
                
                # Delete old versions if necessary
                versions = self.iam.list_policy_versions(PolicyArn=policy_arn)
                if len(versions["Versions"]) >= 5:  # AWS limit is 5 versions
                    # Delete oldest non-default version
                    for version in reversed(versions["Versions"]):
                        if not version["IsDefaultVersion"]:
                            self.iam.delete_policy_version(
                                PolicyArn=policy_arn,
                                VersionId=version["VersionId"]
                            )
                            break
                
                # Create new version
                self.iam.create_policy_version(
                    PolicyArn=policy_arn,
                    PolicyDocument=policy_json,
                    SetAsDefault=True
                )
                
                self._print_success(f"Updated policy {policy_name}")
            else:
                # Create new policy
                response = self.iam.create_policy(
                    PolicyName=policy_name,
                    PolicyDocument=policy_json,
                    Description=f"CI/CD permissions for {self.project_name}"
                )
                policy_arn = response["Policy"]["Arn"]
                
                self._print_success(f"Created policy {policy_name}")
            
            return policy_arn
            
        except Exception as e:
            self._print_error(f"Failed to create/update policy: {e}")
            sys.exit(1)
    
    def _setup_iam_user(self, user_name: str, policy_arn: str) -> IAMCredentials:
        """Set up IAM user with credentials."""
        # Check if user exists
        try:
            self.iam.get_user(UserName=user_name)
            self._print_warning(f"IAM user {user_name} already exists")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                # Create user
                self.iam.create_user(UserName=user_name)
                self._print_success(f"Created IAM user {user_name}")
            else:
                raise
        
        # Attach policy to user
        try:
            self.iam.attach_user_policy(
                UserName=user_name,
                PolicyArn=policy_arn
            )
            self._print_success(f"Attached policy to user {user_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "EntityAlreadyExists":
                raise
        
        # Create access key
        response = self.iam.create_access_key(UserName=user_name)
        access_key = response["AccessKey"]
        
        return IAMCredentials(
            access_key_id=access_key["AccessKeyId"],
            secret_access_key=access_key["SecretAccessKey"],
            user_name=user_name,
            policy_arn=policy_arn
        )
    
    def _setup_github_oidc_role(
        self,
        role_name: str,
        policy_arn: str,
        github_org: str,
        github_repo: str
    ) -> None:
        """Set up GitHub Actions OIDC role."""
        # Check if OIDC provider exists
        oidc_url = "https://token.actions.githubusercontent.com"
        oidc_arn = f"arn:aws:iam::{self.account_id}:oidc-provider/token.actions.githubusercontent.com"
        
        try:
            self.iam.get_open_id_connect_provider(
                OpenIDConnectProviderArn=oidc_arn
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                # Create OIDC provider
                self._print_info("Creating GitHub OIDC provider...")
                self.iam.create_open_id_connect_provider(
                    Url=oidc_url,
                    ClientIdList=["sts.amazonaws.com"],
                    ThumbprintList=["6938fd4d98bab03faadb97b34396831e3780aea1"]
                )
                self._print_success("Created GitHub OIDC provider")
            else:
                raise
        
        # Generate trust policy
        trust_policy = self.policy_generator.generate_github_actions_trust_policy(
            github_org, github_repo
        )
        
        # Check if role exists
        try:
            self.iam.get_role(RoleName=role_name)
            # Update assume role policy
            self.iam.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(trust_policy)
            )
            self._print_success(f"Updated role {role_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                # Create role
                self.iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description=f"GitHub Actions role for {self.project_name}"
                )
                self._print_success(f"Created role {role_name}")
            else:
                raise
        
        # Attach policy to role
        try:
            self.iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            self._print_success(f"Attached policy to role {role_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "EntityAlreadyExists":
                raise
    
    def rotate_access_keys(self, user_name: Optional[str] = None) -> Optional[IAMCredentials]:
        """
        Rotate access keys for a user.
        
        Args:
            user_name: IAM user name (uses default if not provided)
            
        Returns:
            New credentials if successful
        """
        if not user_name:
            user_name = self.config.format_name(self.config.cicd_user_pattern)
        
        self._print_info(f"Rotating access keys for {user_name}...")
        
        try:
            # List existing access keys
            response = self.iam.list_access_keys(UserName=user_name)
            existing_keys = response["AccessKeyMetadata"]
            
            # Create new access key first
            new_key_response = self.iam.create_access_key(UserName=user_name)
            new_key = new_key_response["AccessKey"]
            
            self._print_success("Created new access key")
            
            # Delete old access keys
            for key in existing_keys:
                if key["AccessKeyId"] != new_key["AccessKeyId"]:
                    self.iam.delete_access_key(
                        UserName=user_name,
                        AccessKeyId=key["AccessKeyId"]
                    )
                    self._print_success(f"Deleted old access key {key['AccessKeyId']}")
            
            # Get policy ARN
            policies = self.iam.list_attached_user_policies(UserName=user_name)
            policy_arn = policies["AttachedPolicies"][0]["PolicyArn"] if policies["AttachedPolicies"] else None
            
            return IAMCredentials(
                access_key_id=new_key["AccessKeyId"],
                secret_access_key=new_key["SecretAccessKey"],
                user_name=user_name,
                policy_arn=policy_arn
            )
            
        except Exception as e:
            self._print_error(f"Failed to rotate access keys: {e}")
            return None
    
    def validate_permissions(self) -> bool:
        """Validate that CI/CD permissions are correctly set up."""
        self._print_info("Validating CI/CD permissions...")
        
        user_name = self.config.format_name(self.config.cicd_user_pattern)
        policy_name = self.config.format_name(self.config.cicd_policy_pattern)
        
        all_valid = True
        
        # Check user exists
        try:
            self.iam.get_user(UserName=user_name)
            self._print_success(f"User {user_name} exists")
        except ClientError:
            self._print_warning(f"User {user_name} not found")
            all_valid = False
        
        # Check policy exists
        policy_arn = None
        try:
            policies = self.iam.list_policies(Scope="Local", MaxItems=1000)
            for policy in policies["Policies"]:
                if policy["PolicyName"] == policy_name:
                    policy_arn = policy["Arn"]
                    self._print_success(f"Policy {policy_name} exists")
                    break
            
            if not policy_arn:
                self._print_warning(f"Policy {policy_name} not found")
                all_valid = False
        except Exception as e:
            self._print_error(f"Failed to check policy: {e}")
            all_valid = False
        
        # Check policy is attached
        if policy_arn:
            try:
                attached_policies = self.iam.list_attached_user_policies(UserName=user_name)
                policy_attached = any(
                    p["PolicyArn"] == policy_arn 
                    for p in attached_policies["AttachedPolicies"]
                )
                
                if policy_attached:
                    self._print_success(f"Policy is attached to user")
                else:
                    self._print_warning(f"Policy is not attached to user")
                    all_valid = False
            except Exception:
                pass
        
        # Check access keys
        try:
            keys = self.iam.list_access_keys(UserName=user_name)
            if keys["AccessKeyMetadata"]:
                self._print_success(f"User has {len(keys['AccessKeyMetadata'])} access key(s)")
            else:
                self._print_warning(f"User has no access keys")
                all_valid = False
        except Exception:
            pass
        
        return all_valid
    
    def cleanup_cicd_resources(self, force: bool = False) -> bool:
        """
        Clean up CI/CD IAM resources.
        
        Args:
            force: Force deletion without confirmation
            
        Returns:
            True if successful
        """
        user_name = self.config.format_name(self.config.cicd_user_pattern)
        policy_name = self.config.format_name(self.config.cicd_policy_pattern)
        
        if not force:
            response = input(f"⚠️  Delete CI/CD resources for {self.project_name}? [y/N]: ")
            if response.lower() != 'y':
                print("Cancelled")
                return False
        
        self._print_info("Cleaning up CI/CD resources...")
        
        # Delete access keys
        try:
            keys = self.iam.list_access_keys(UserName=user_name)
            for key in keys["AccessKeyMetadata"]:
                self.iam.delete_access_key(
                    UserName=user_name,
                    AccessKeyId=key["AccessKeyId"]
                )
                self._print_success(f"Deleted access key {key['AccessKeyId']}")
        except Exception:
            pass
        
        # Detach policies
        try:
            attached_policies = self.iam.list_attached_user_policies(UserName=user_name)
            for policy in attached_policies["AttachedPolicies"]:
                self.iam.detach_user_policy(
                    UserName=user_name,
                    PolicyArn=policy["PolicyArn"]
                )
                self._print_success(f"Detached policy {policy['PolicyName']}")
        except Exception:
            pass
        
        # Delete user
        try:
            self.iam.delete_user(UserName=user_name)
            self._print_success(f"Deleted user {user_name}")
        except Exception as e:
            if "NoSuchEntity" not in str(e):
                self._print_error(f"Failed to delete user: {e}")
        
        # Delete policy
        try:
            policies = self.iam.list_policies(Scope="Local", MaxItems=1000)
            for policy in policies["Policies"]:
                if policy["PolicyName"] == policy_name:
                    # Delete all non-default versions first
                    versions = self.iam.list_policy_versions(PolicyArn=policy["Arn"])
                    for version in versions["Versions"]:
                        if not version["IsDefaultVersion"]:
                            self.iam.delete_policy_version(
                                PolicyArn=policy["Arn"],
                                VersionId=version["VersionId"]
                            )
                    
                    # Delete policy
                    self.iam.delete_policy(PolicyArn=policy["Arn"])
                    self._print_success(f"Deleted policy {policy_name}")
                    break
        except Exception as e:
            if "NoSuchEntity" not in str(e):
                self._print_error(f"Failed to delete policy: {e}")
        
        return True
    
    def show_all_permissions(self, output_json: bool = False) -> Dict[str, Any]:
        """
        Show all permissions for CI/CD user.
        
        Args:
            output_json: Output as JSON instead of formatted text
            
        Returns:
            Dictionary with permission details
        """
        user_name = self.config.format_name(self.config.cicd_user_pattern)
        permissions_data = {
            "user_name": user_name,
            "user_arn": f"arn:aws:iam::{self.account_id}:user/{user_name}",
            "attached_policies": [],
            "inline_policies": [],
            "groups": []
        }
        
        try:
            # Check if user exists
            try:
                self.iam.get_user(UserName=user_name)
            except self.iam.exceptions.NoSuchEntityException:
                if output_json:
                    print(json.dumps({"error": f"User {user_name} not found"}, indent=2))
                else:
                    self._print_error(f"User {user_name} not found")
                return permissions_data
            
            # Get attached managed policies
            response = self.iam.list_attached_user_policies(UserName=user_name)
            for policy in response["AttachedPolicies"]:
                policy_data = {
                    "policy_name": policy["PolicyName"],
                    "policy_arn": policy["PolicyArn"]
                }
                
                # Get policy version
                policy_details = self.iam.get_policy(PolicyArn=policy["PolicyArn"])
                default_version = policy_details["Policy"]["DefaultVersionId"]
                
                # Get policy document
                version_details = self.iam.get_policy_version(
                    PolicyArn=policy["PolicyArn"],
                    VersionId=default_version
                )
                policy_data["document"] = version_details["PolicyVersion"]["Document"]
                policy_data["version"] = default_version
                
                permissions_data["attached_policies"].append(policy_data)
            
            # Get inline policies
            response = self.iam.list_user_policies(UserName=user_name)
            for policy_name in response.get("PolicyNames", []):
                policy_response = self.iam.get_user_policy(
                    UserName=user_name,
                    PolicyName=policy_name
                )
                permissions_data["inline_policies"].append({
                    "policy_name": policy_name,
                    "document": policy_response["PolicyDocument"]
                })
            
            # Get group memberships
            response = self.iam.list_groups_for_user(UserName=user_name)
            for group in response.get("Groups", []):
                group_data = {
                    "group_name": group["GroupName"],
                    "group_arn": group["Arn"],
                    "attached_policies": []
                }
                
                # Get group policies
                group_policies = self.iam.list_attached_group_policies(
                    GroupName=group["GroupName"]
                )
                for policy in group_policies["AttachedPolicies"]:
                    group_data["attached_policies"].append({
                        "policy_name": policy["PolicyName"],
                        "policy_arn": policy["PolicyArn"]
                    })
                
                permissions_data["groups"].append(group_data)
            
            if output_json:
                print(json.dumps(permissions_data, indent=2, default=str))
            else:
                self._display_permissions(permissions_data)
            
            return permissions_data
            
        except Exception as e:
            self._print_error(f"Failed to get permissions: {e}")
            return permissions_data
    
    def _display_permissions(self, permissions_data: Dict[str, Any]) -> None:
        """Display permissions in a formatted way."""
        print(f"🔍 Showing permissions for user: {permissions_data['user_name']}")
        print("=" * 60)
        print()
        
        # Attached policies
        print("📋 Attached Managed Policies:")
        print("-" * 30)
        if permissions_data["attached_policies"]:
            for policy in permissions_data["attached_policies"]:
                print(f"Policy: {policy['policy_name']}")
                print(f"ARN: {policy['policy_arn']}")
                print(f"Version: {policy['version']}")
                print()
                
                # Show summary of permissions
                doc = policy["document"]
                if "Statement" in doc:
                    actions = set()
                    for statement in doc["Statement"]:
                        if statement.get("Effect") == "Allow":
                            for action in statement.get("Action", []):
                                if isinstance(action, str):
                                    actions.add(action.split(":")[0])
                    
                    if actions:
                        print("Services with permissions:")
                        for service in sorted(actions):
                            print(f"  - {service}")
                print("-" * 30)
        else:
            print("No managed policies attached")
        
        print()
        
        # Inline policies
        if permissions_data["inline_policies"]:
            print("📄 Inline Policies:")
            print("-" * 30)
            for policy in permissions_data["inline_policies"]:
                print(f"Policy: {policy['policy_name']}")
                print()
        
        # Groups
        if permissions_data["groups"]:
            print("👥 Group Memberships:")
            print("-" * 30)
            for group in permissions_data["groups"]:
                print(f"Group: {group['group_name']}")
                if group["attached_policies"]:
                    print("  Policies:")
                    for policy in group["attached_policies"]:
                        print(f"    - {policy['policy_name']}")
                print()
    
    def show_policy_document(self, version: Optional[str] = None) -> None:
        """
        Show policy document for CI/CD user.
        
        Args:
            version: Policy version to show (default: current)
        """
        user_name = self.config.format_name(self.config.cicd_user_pattern)
        policy_name = self.config.format_name(self.config.cicd_policy_pattern)
        
        try:
            # Find the policy
            policies = self.iam.list_policies(Scope="Local", MaxItems=1000)
            policy_arn = None
            
            for policy in policies["Policies"]:
                if policy["PolicyName"] == policy_name:
                    policy_arn = policy["Arn"]
                    break
            
            if not policy_arn:
                # Check attached policies
                try:
                    attached = self.iam.list_attached_user_policies(UserName=user_name)
                    for policy in attached["AttachedPolicies"]:
                        if policy["PolicyName"] == policy_name:
                            policy_arn = policy["PolicyArn"]
                            break
                except:
                    pass
            
            if not policy_arn:
                self._print_error(f"Policy {policy_name} not found")
                return
            
            # Get policy details
            policy_details = self.iam.get_policy(PolicyArn=policy_arn)
            default_version = policy_details["Policy"]["DefaultVersionId"]
            
            if version is None:
                version = default_version
            
            print(f"📋 Policy Document for: {policy_name}")
            print("=" * 60)
            print()
            print(f"Policy ARN: {policy_arn}")
            print(f"Version: {version}")
            print()
            print("Policy Document:")
            print("-" * 20)
            
            # Get policy document
            version_details = self.iam.get_policy_version(
                PolicyArn=policy_arn,
                VersionId=version
            )
            
            print(json.dumps(version_details["PolicyVersion"]["Document"], indent=2))
            
        except Exception as e:
            self._print_error(f"Failed to get policy document: {e}")
    
    def setup_credentials(
        self,
        save_to_github: bool = False,
        github_token: Optional[str] = None,
        github_repo: Optional[str] = None
    ) -> Optional[IAMCredentials]:
        """
        Set up CI/CD credentials and optionally save to GitHub.
        
        Args:
            save_to_github: Save credentials to GitHub secrets
            github_token: GitHub token for API access
            github_repo: GitHub repository (owner/repo)
            
        Returns:
            IAM credentials if successful
        """
        user_name = self.config.format_name(self.config.cicd_user_pattern)
        
        try:
            # Check if user exists
            try:
                self.iam.get_user(UserName=user_name)
                self._print_info(f"User {user_name} already exists")
                
                # Check for existing access keys
                keys = self.iam.list_access_keys(UserName=user_name)
                if keys["AccessKeyMetadata"]:
                    response = input("User has existing access keys. Create new ones? [y/N]: ")
                    if response.lower() != 'y':
                        return None
                
            except self.iam.exceptions.NoSuchEntityException:
                self._print_error(f"User {user_name} not found. Run 'setup-cicd' first.")
                return None
            
            # Create new access key
            response = self.iam.create_access_key(UserName=user_name)
            access_key = response["AccessKey"]
            
            # Get policy ARN
            policies = self.iam.list_attached_user_policies(UserName=user_name)
            policy_arn = policies["AttachedPolicies"][0]["PolicyArn"] if policies["AttachedPolicies"] else None
            
            credentials = IAMCredentials(
                access_key_id=access_key["AccessKeyId"],
                secret_access_key=access_key["SecretAccessKey"],
                user_name=user_name,
                policy_arn=policy_arn
            )
            
            self._print_success("Created new access key")
            
            # Save to GitHub if requested
            if save_to_github and github_token and github_repo:
                if self._save_to_github(credentials, github_token, github_repo):
                    self._print_success("Saved credentials to GitHub secrets")
                else:
                    self._print_warning("Failed to save to GitHub, showing credentials below")
            
            return credentials
            
        except Exception as e:
            self._print_error(f"Failed to setup credentials: {e}")
            return None
    
    def _save_to_github(
        self,
        credentials: IAMCredentials,
        github_token: str,
        github_repo: str
    ) -> bool:
        """Save credentials to GitHub secrets."""
        try:
            import requests
            from base64 import b64encode
            from nacl import encoding, public
            
            # GitHub API headers
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Get repository public key
            url = f"https://api.github.com/repos/{github_repo}/actions/secrets/public-key"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            public_key = response.json()
            key_id = public_key["key_id"]
            key = public_key["key"]
            
            # Encrypt secrets
            def encrypt_secret(secret_value: str) -> str:
                public_key_obj = public.PublicKey(key.encode("utf-8"), encoding.Base64Encoder())
                sealed_box = public.SealedBox(public_key_obj)
                encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
                return b64encode(encrypted).decode("utf-8")
            
            # Save secrets
            secrets = {
                "AWS_ACCESS_KEY_ID": credentials.access_key_id,
                "AWS_SECRET_ACCESS_KEY": credentials.secret_access_key,
                "AWS_REGION": self.config.aws_region
            }
            
            for secret_name, secret_value in secrets.items():
                url = f"https://api.github.com/repos/{github_repo}/actions/secrets/{secret_name}"
                data = {
                    "encrypted_value": encrypt_secret(secret_value),
                    "key_id": key_id
                }
                response = requests.put(url, json=data, headers=headers)
                response.raise_for_status()
            
            return True
            
        except ImportError:
            self._print_error("Please install 'requests' and 'pynacl' to save to GitHub")
            self._print_info("Run: pip install requests pynacl")
            return False
        except Exception as e:
            self._print_error(f"Failed to save to GitHub: {e}")
            return False