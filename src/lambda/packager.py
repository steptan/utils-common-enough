"""
Lambda function packaging utilities.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Union


class LambdaPackager:
    """Package Lambda functions for deployment."""

    def __init__(self, project_root: Union[str, Path]):
        """
        Initialize Lambda packager.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)

    def package_nodejs_lambda(
        self,
        source_dir: Union[str, Path],
        output_path: Union[str, Path],
        handler: str = "index.handler",
        include_dev_deps: bool = False,
        minify: bool = True,
    ) -> Path:
        """
        Package Node.js Lambda function.

        Args:
            source_dir: Directory containing Lambda function code
            output_path: Output path for the zip file
            handler: Lambda handler (e.g., "index.handler")
            include_dev_deps: Whether to include dev dependencies
            minify: Whether to minify the code

        Returns:
            Path to the created zip file
        """
        source_dir = Path(source_dir)
        output_path = Path(output_path)

        if not source_dir.exists():
            raise ValueError(f"Source directory does not exist: {source_dir}")

        # Create temporary directory for packaging
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Copy source files
            print(f"📦 Copying source files from {source_dir}")
            shutil.copytree(source_dir, temp_path / "src", dirs_exist_ok=True)

            # Install dependencies
            package_json = source_dir / "package.json"
            if package_json.exists():
                print("📦 Installing dependencies...")

                # Copy package.json to temp directory
                shutil.copy2(package_json, temp_path / "package.json")

                # Copy package-lock.json if exists
                package_lock = source_dir / "package-lock.json"
                if package_lock.exists():
                    shutil.copy2(package_lock, temp_path / "package-lock.json")

                # Install dependencies
                npm_cmd = ["npm", "ci" if package_lock.exists() else "install"]
                if not include_dev_deps:
                    npm_cmd.append("--production")

                result = subprocess.run(
                    npm_cmd, cwd=temp_path, capture_output=True, text=True
                )

                if result.returncode != 0:
                    raise RuntimeError(f"npm install failed: {result.stderr}")

            # Build TypeScript if needed
            tsconfig = source_dir / "tsconfig.json"
            if tsconfig.exists():
                print("📦 Building TypeScript...")

                # Copy tsconfig
                shutil.copy2(tsconfig, temp_path / "tsconfig.json")

                # Run TypeScript compiler
                result = subprocess.run(
                    ["npx", "tsc"], cwd=temp_path, capture_output=True, text=True
                )

                if result.returncode != 0:
                    raise RuntimeError(
                        f"TypeScript compilation failed: {result.stderr}"
                    )

            # Minify if requested
            if minify and (temp_path / "dist").exists():
                print("📦 Minifying code...")
                self._minify_javascript(temp_path / "dist")

            # Create deployment package
            print(f"📦 Creating deployment package: {output_path}")
            return self._create_zip(temp_path, output_path, handler)

    def package_python_lambda(
        self,
        source_dir: Union[str, Path],
        output_path: Union[str, Path],
        handler: str = "handler.lambda_handler",
        python_version: str = "3.11",
        requirements_file: Optional[str] = None,
    ) -> Path:
        """
        Package Python Lambda function.

        Args:
            source_dir: Directory containing Lambda function code
            output_path: Output path for the zip file
            handler: Lambda handler (e.g., "handler.lambda_handler")
            python_version: Python version (e.g., "3.11")
            requirements_file: Path to requirements.txt file

        Returns:
            Path to the created zip file
        """
        source_dir = Path(source_dir)
        output_path = Path(output_path)

        if not source_dir.exists():
            raise ValueError(f"Source directory does not exist: {source_dir}")

        # Create temporary directory for packaging
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            package_dir = temp_path / "package"
            package_dir.mkdir()

            # Copy source files
            print(f"📦 Copying source files from {source_dir}")
            for item in source_dir.iterdir():
                if item.name not in ["__pycache__", ".pytest_cache", "tests", "test_*"]:
                    if item.is_dir():
                        shutil.copytree(item, package_dir / item.name)
                    else:
                        shutil.copy2(item, package_dir)

            # Install dependencies
            if requirements_file:
                req_path = Path(requirements_file)
            else:
                req_path = source_dir / "requirements.txt"

            if req_path.exists():
                print(f"📦 Installing dependencies from {req_path}")

                # Use platform-specific pip for Lambda runtime
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        str(req_path),
                        "-t",
                        str(package_dir),
                        "--platform",
                        "manylinux2014_x86_64",
                        "--only-binary",
                        ":all:",
                        "--python-version",
                        python_version,
                        "--no-deps",
                    ],
                    capture_output=True,
                    text=True,
                )

                # Fallback to regular pip install if platform-specific fails
                if result.returncode != 0:
                    print(
                        "⚠️  Platform-specific install failed, trying regular install..."
                    )
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "-r",
                            str(req_path),
                            "-t",
                            str(package_dir),
                        ],
                        capture_output=True,
                        text=True,
                    )

                if result.returncode != 0:
                    raise RuntimeError(f"pip install failed: {result.stderr}")

            # Create deployment package
            print(f"📦 Creating deployment package: {output_path}")
            return self._create_zip(package_dir, output_path, handler)

    def _minify_javascript(self, directory: Path) -> None:
        """Minify JavaScript files in directory."""
        try:
            # Try to use terser if available
            result = subprocess.run(
                ["npx", "terser", "--version"], capture_output=True, text=True
            )

            if result.returncode == 0:
                # Minify all .js files
                for js_file in directory.rglob("*.js"):
                    if ".min.js" not in js_file.name:
                        print(f"  Minifying {js_file.name}")
                        subprocess.run(
                            [
                                "npx",
                                "terser",
                                str(js_file),
                                "-o",
                                str(js_file),
                                "--compress",
                                "--mangle",
                            ],
                            capture_output=True,
                        )
        except Exception as e:
            print(f"⚠️  Minification failed: {e}")

    def _create_zip(self, source_dir: Path, output_path: Path, handler: str) -> Path:
        """Create zip file from directory."""
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create zip file
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                # Skip unnecessary directories
                dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "tests"]]

                for file in files:
                    # Skip unnecessary files
                    if file.endswith((".pyc", ".pyo", ".git", ".DS_Store")):
                        continue

                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(source_dir)

                    # For the main handler file in src/, put it at root level
                    if source_dir.name == "src" and str(arc_name).startswith("src/"):
                        arc_name = Path(str(arc_name).replace("src/", "", 1))

                    zf.write(file_path, arc_name)

        # Verify handler exists in zip
        handler_file = handler.split(".")[0] + ".py" if handler else None
        if handler_file:
            with zipfile.ZipFile(output_path, "r") as zf:
                files_in_zip = zf.namelist()
                if (
                    handler_file not in files_in_zip
                    and f"src/{handler_file}" not in files_in_zip
                ):
                    print(
                        f"⚠️  Warning: Handler file '{handler_file}' not found in package"
                    )

        print(
            f"✅ Created Lambda package: {output_path} ({output_path.stat().st_size / 1024 / 1024:.2f} MB)"
        )
        return output_path

    def validate_package(
        self, package_path: Union[str, Path], handler: str, runtime: str
    ) -> bool:
        """
        Validate Lambda deployment package.

        Args:
            package_path: Path to the zip file
            handler: Lambda handler
            runtime: Lambda runtime (e.g., "python3.11", "nodejs20.x")

        Returns:
            True if package is valid
        """
        package_path = Path(package_path)

        if not package_path.exists():
            print(f"❌ Package does not exist: {package_path}")
            return False

        # Check size (Lambda limit is 50MB for direct upload)
        size_mb = package_path.stat().st_size / 1024 / 1024
        if size_mb > 50:
            print(
                f"⚠️  Package size ({size_mb:.2f} MB) exceeds 50MB limit for direct upload"
            )
            print("   Consider using S3 for deployment")

        # Validate handler exists
        handler_parts = handler.split(".")
        if runtime.startswith("python"):
            handler_file = handler_parts[0] + ".py"
        elif runtime.startswith("node"):
            handler_file = handler_parts[0] + ".js"
        else:
            handler_file = handler_parts[0]

        with zipfile.ZipFile(package_path, "r") as zf:
            files = zf.namelist()
            if handler_file not in files:
                print(f"❌ Handler file '{handler_file}' not found in package")
                print(f"   Available files: {', '.join(sorted(files)[:10])}...")
                return False

        print("✅ Package validation passed")
        return True
