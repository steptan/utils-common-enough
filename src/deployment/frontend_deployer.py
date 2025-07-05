"""
Frontend deployment to S3 and CloudFront.
"""

import os
import subprocess
import mimetypes
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import json

from .base_deployer import BaseDeployer, DeploymentResult, DeploymentStatus


class FrontendDeployer(BaseDeployer):
    """Deploy frontend applications to S3 and CloudFront."""

    # Content type mappings
    CONTENT_TYPES = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".txt": "text/plain",
        ".xml": "application/xml",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".eot": "application/vnd.ms-fontobject",
        ".map": "application/json",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }

    # Cache control settings by file type
    CACHE_CONTROL = {
        "static": "public, max-age=31536000, immutable",  # 1 year for static assets
        "html": "public, max-age=0, must-revalidate",  # No cache for HTML
        "json": "public, max-age=3600",  # 1 hour for JSON
        "default": "public, max-age=86400",  # 1 day default
    }

    def __init__(
        self,
        project_name: str,
        environment: str,
        build_env: Optional[Dict[str, str]] = None,
        skip_build: bool = False,
        **kwargs,
    ):
        """
        Initialize frontend deployer.

        Args:
            project_name: Name of the project
            environment: Deployment environment
            build_env: Environment variables for build
            skip_build: Skip the build step
            **kwargs: Additional arguments for BaseDeployer
        """
        super().__init__(project_name, environment, **kwargs)
        self.build_env = build_env or {}
        self.skip_build = skip_build

        # Get project directory
        self.project_dir = Path.cwd() / ".." / project_name
        if not self.project_dir.exists():
            self.project_dir = Path.cwd()

    def get_content_type(self, file_path: Path) -> str:
        """Get content type for a file."""
        # Try our mapping first
        ext = file_path.suffix.lower()
        if ext in self.CONTENT_TYPES:
            return self.CONTENT_TYPES[ext]

        # Fall back to mimetypes
        content_type, _ = mimetypes.guess_type(str(file_path))
        return content_type or "application/octet-stream"

    def get_cache_control(self, file_path: Path) -> str:
        """Get cache control header for a file."""
        # Check if it's a static asset (in _next/static or similar)
        path_str = str(file_path)
        if "/_next/static/" in path_str or "/static/" in path_str:
            return self.CACHE_CONTROL["static"]

        # Check by file type
        ext = file_path.suffix.lower()
        if ext in [".html", ".htm"]:
            return self.CACHE_CONTROL["html"]
        elif ext == ".json":
            return self.CACHE_CONTROL["json"]

        return self.CACHE_CONTROL["default"]

    def build_frontend(self) -> bool:
        """Build the frontend application."""
        if self.skip_build:
            self.log("Skipping build step", "INFO")
            return True

        self.log(f"Building {self.project_name} frontend...", "INFO")

        # Get API URL from stack outputs
        stack_outputs = self.get_stack_outputs()
        api_url = stack_outputs.get("ApiGatewayUrl", "")

        # Set up build environment
        build_env = os.environ.copy()
        build_env.update(self.build_env)

        # Add common Next.js environment variables
        if api_url:
            build_env["NEXT_PUBLIC_API_URL"] = api_url
        build_env["NEXT_PUBLIC_ENVIRONMENT"] = self.environment
        build_env["NODE_ENV"] = "production"

        # Install dependencies
        self.log("Installing dependencies...", "INFO")
        return_code, _, stderr = self.run_command(
            ["npm", "ci"], cwd=self.project_dir, env=build_env
        )

        if return_code != 0:
            self.add_error(f"Failed to install dependencies: {stderr}")
            return False

        # Run build command
        build_command = self.config.frontend_build_command.split()
        self.log(f"Running build command: {' '.join(build_command)}", "INFO")

        return_code, _, stderr = self.run_command(
            build_command, cwd=self.project_dir, env=build_env
        )

        if return_code != 0:
            self.add_error(f"Build failed: {stderr}")
            return False

        self.log("Build completed successfully", "SUCCESS")
        return True

    def get_build_files(self) -> List[Tuple[Path, str]]:
        """Get list of files to upload with their S3 keys."""
        # Find build output directory
        build_dir = self.project_dir / self.config.frontend_dist_dir

        if not build_dir.exists():
            self.add_error(f"Build directory not found: {build_dir}")
            return []

        files = []

        # For Next.js static export
        if self.config.frontend_dist_dir == "out":
            # Include all files from out directory
            for file_path in build_dir.rglob("*"):
                if file_path.is_file():
                    # Calculate S3 key (relative path from build_dir)
                    s3_key = str(file_path.relative_to(build_dir))
                    files.append((file_path, s3_key))

        # For Next.js with .next/static
        elif ".next" in self.config.frontend_dist_dir:
            # Copy _next/static files
            next_static = self.project_dir / ".next" / "static"
            if next_static.exists():
                for file_path in next_static.rglob("*"):
                    if file_path.is_file():
                        s3_key = "_next/static/" + str(
                            file_path.relative_to(next_static)
                        )
                        files.append((file_path, s3_key))

            # Copy public files
            public_dir = self.project_dir / "public"
            if public_dir.exists():
                for file_path in public_dir.rglob("*"):
                    if file_path.is_file():
                        s3_key = str(file_path.relative_to(public_dir))
                        files.append((file_path, s3_key))

            # Copy exported HTML files if they exist
            out_dir = self.project_dir / "out"
            if out_dir.exists():
                for file_path in out_dir.rglob("*"):
                    if file_path.is_file():
                        s3_key = str(file_path.relative_to(out_dir))
                        files.append((file_path, s3_key))

        return files

    def upload_to_s3(self, bucket_name: str, files: List[Tuple[Path, str]]) -> bool:
        """Upload files to S3 bucket."""
        self.log(f"Uploading {len(files)} files to S3 bucket {bucket_name}...", "INFO")

        if self.dry_run:
            self.log("DRY RUN: Would upload files to S3", "INFO")
            for file_path, s3_key in files[:5]:  # Show first 5 files
                self.log(f"  {s3_key} ({self.get_content_type(file_path)})", "DEBUG")
            if len(files) > 5:
                self.log(f"  ... and {len(files) - 5} more files", "DEBUG")
            return True

        upload_count = 0
        for file_path, s3_key in files:
            try:
                content_type = self.get_content_type(file_path)
                cache_control = self.get_cache_control(file_path)

                # Read file
                with open(file_path, "rb") as f:
                    file_content = f.read()

                # Upload to S3
                self.s3.put_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=content_type,
                    CacheControl=cache_control,
                )

                upload_count += 1

                # Progress indicator
                if upload_count % 50 == 0:
                    self.log(f"Uploaded {upload_count}/{len(files)} files...", "INFO")

            except Exception as e:
                self.add_error(f"Failed to upload {s3_key}: {e}")
                return False

        self.log(f"Successfully uploaded {upload_count} files", "SUCCESS")
        return True

    def configure_s3_website(self, bucket_name: str) -> bool:
        """Configure S3 bucket for static website hosting."""
        self.log("Configuring S3 bucket for website hosting...", "INFO")

        if self.dry_run:
            self.log("DRY RUN: Would configure S3 website", "INFO")
            return True

        try:
            # Enable website hosting
            self.s3.put_bucket_website(
                Bucket=bucket_name,
                WebsiteConfiguration={
                    "IndexDocument": {"Suffix": "index.html"},
                    "ErrorDocument": {"Key": "error.html"},
                },
            )

            self.log("S3 website hosting configured", "SUCCESS")
            return True

        except Exception as e:
            self.add_error(f"Failed to configure website hosting: {e}")
            return False

    def invalidate_cloudfront(self, distribution_id: str) -> bool:
        """Create CloudFront invalidation."""
        self.log("Creating CloudFront invalidation...", "INFO")

        if self.dry_run:
            self.log("DRY RUN: Would create CloudFront invalidation", "INFO")
            return True

        try:
            cloudfront = self._get_client("cloudfront")

            response = cloudfront.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {"Quantity": 1, "Items": ["/*"]},
                    "CallerReference": f"{self.project_name}-{self.environment}-{int(time.time())}",
                },
            )

            invalidation_id = response["Invalidation"]["Id"]
            self.log(f"Created invalidation {invalidation_id}", "SUCCESS")

            # Add to outputs
            self.add_output("CloudFrontInvalidationId", invalidation_id)

            return True

        except Exception as e:
            self.add_error(f"Failed to create invalidation: {e}")
            return False

    def deploy(self) -> DeploymentResult:
        """Execute frontend deployment."""
        self.log(
            f"Deploying {self.project_name} frontend to {self.environment}", "INFO"
        )

        # Build frontend
        if not self.build_frontend():
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message="Frontend build failed",
                duration=0,
                errors=self.errors,
            )

        # Get S3 bucket and CloudFront distribution from stack outputs
        stack_outputs = self.get_stack_outputs()

        frontend_bucket = stack_outputs.get("FrontendBucketName")
        if not frontend_bucket:
            frontend_bucket = self.config.get_frontend_bucket(self.environment)
            self.add_warning(
                f"Frontend bucket not in stack outputs, using: {frontend_bucket}"
            )

        distribution_id = stack_outputs.get("CloudFrontDistributionId")

        # Get files to upload
        files = self.get_build_files()
        if not files:
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message="No build files found",
                duration=0,
                errors=self.errors,
            )

        self.log(f"Found {len(files)} files to upload", "INFO")

        # Upload to S3
        if not self.upload_to_s3(frontend_bucket, files):
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message="Failed to upload files to S3",
                duration=0,
                errors=self.errors,
            )

        # Configure S3 website if needed
        if not stack_outputs.get("CloudFrontDistributionId"):
            # No CloudFront, configure S3 website hosting
            if not self.configure_s3_website(frontend_bucket):
                return DeploymentResult(
                    status=DeploymentStatus.FAILED,
                    message="Failed to configure S3 website",
                    duration=0,
                    errors=self.errors,
                )

        # Invalidate CloudFront if available
        if distribution_id:
            if not self.invalidate_cloudfront(distribution_id):
                # Invalidation failure is not critical
                self.add_warning(
                    "CloudFront invalidation failed, content may be cached"
                )

        # Add deployment info to outputs
        self.add_output("FrontendBucket", frontend_bucket)
        self.add_output("FilesUploaded", len(files))

        if distribution_id:
            cloudfront_url = stack_outputs.get("CloudFrontDomainName", "")
            if cloudfront_url:
                self.add_output("FrontendURL", f"https://{cloudfront_url}")
        else:
            # S3 website URL
            region = self.region if self.region != "us-east-1" else ""
            region_part = f"-{region}" if region else ""
            self.add_output(
                "FrontendURL",
                f"http://{frontend_bucket}.s3-website{region_part}.amazonaws.com",
            )

        return DeploymentResult(
            status=DeploymentStatus.SUCCESS,
            message=f"Frontend deployed successfully to {self.environment}",
            duration=0,
            outputs=self.outputs,
            warnings=self.warnings,
        )
