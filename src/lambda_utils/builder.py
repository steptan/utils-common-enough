"""Lambda function builder."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import ProjectConfig


class LambdaBuilder:
    """Build Lambda functions for deployment."""

    def __init__(self, config: ProjectConfig):
        """
        Initialize Lambda builder.

        Args:
            config: Project configuration
        """
        self.config = config
        self.runtime = config.lambda_runtime
        self.architecture = config.lambda_architecture

    def build_function(
        self,
        source_dir: Path,
        output_dir: Path,
        function_name: str,
        environment: str = "dev",
    ) -> Path:
        """
        Build a Lambda function.

        Args:
            source_dir: Source directory containing Lambda code
            output_dir: Output directory for built function
            function_name: Name of the function
            environment: Target environment

        Returns:
            Path to built function directory
        """
        print(f"🔨 Building Lambda function: {function_name}")

        # Create output directory
        function_output = output_dir / function_name
        function_output.mkdir(parents=True, exist_ok=True)

        # Determine build method based on runtime
        if self.runtime.startswith("nodejs"):
            return self._build_nodejs_function(
                source_dir, function_output, function_name
            )
        elif self.runtime.startswith("python"):
            return self._build_python_function(
                source_dir, function_output, function_name
            )
        else:
            raise ValueError(f"Unsupported runtime: {self.runtime}")

    def _build_nodejs_function(
        self, source_dir: Path, output_dir: Path, function_name: str
    ) -> Path:
        """Build Node.js Lambda function."""
        print(f"  Building Node.js function ({self.runtime})")

        # Copy source files
        for item in source_dir.iterdir():
            if item.name in [".git", "node_modules", ".env", "dist", "build"]:
                continue

            if item.is_file():
                shutil.copy2(item, output_dir)
            else:
                shutil.copytree(item, output_dir / item.name, dirs_exist_ok=True)

        # Install production dependencies
        if (source_dir / "package.json").exists():
            print("  Installing production dependencies...")

            # Copy package files
            shutil.copy2(source_dir / "package.json", output_dir)
            if (source_dir / "package-lock.json").exists():
                shutil.copy2(source_dir / "package-lock.json", output_dir)

            # Install dependencies
            subprocess.run(
                ["npm", "ci", "--production"],
                cwd=output_dir,
                check=True,
                capture_output=True,
            )

        # Run build command if specified
        if (output_dir / "package.json").exists():
            package_json = self._read_json(output_dir / "package.json")
            if "scripts" in package_json and "build" in package_json["scripts"]:
                print("  Running build script...")
                subprocess.run(
                    ["npm", "run", "build"],
                    cwd=output_dir,
                    check=True,
                    capture_output=True,
                )

        return output_dir

    def _build_python_function(
        self, source_dir: Path, output_dir: Path, function_name: str
    ) -> Path:
        """Build Python Lambda function."""
        print(f"  Building Python function ({self.runtime})")

        # Copy source files
        for item in source_dir.iterdir():
            if item.name in [".git", "__pycache__", ".env", "venv", ".venv"]:
                continue

            if item.is_file():
                shutil.copy2(item, output_dir)
            else:
                shutil.copytree(item, output_dir / item.name, dirs_exist_ok=True)

        # Install dependencies
        requirements_file = source_dir / "requirements.txt"
        if requirements_file.exists():
            print("  Installing dependencies...")

            # Use Docker for consistent builds (matches Lambda environment)
            if shutil.which("docker"):
                self._build_python_docker(requirements_file, output_dir)
            else:
                # Fallback to pip
                subprocess.run(
                    [
                        "pip",
                        "install",
                        "-r",
                        str(requirements_file),
                        "-t",
                        str(output_dir),
                        "--no-deps",
                        "--platform",
                        (
                            "manylinux2014_x86_64"
                            if self.architecture == "x86_64"
                            else "manylinux2014_aarch64"
                        ),
                        "--only-binary",
                        ":all:",
                    ],
                    check=True,
                    capture_output=True,
                )

        return output_dir

    def _build_python_docker(self, requirements_file: Path, output_dir: Path) -> None:
        """Build Python dependencies using Docker."""
        image = f"public.ecr.aws/lambda/python:{self.runtime.replace('python', '')}"

        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{requirements_file.parent}:/var/task",
                "-v",
                f"{output_dir}:/var/output",
                image,
                "pip",
                "install",
                "-r",
                "/var/task/requirements.txt",
                "-t",
                "/var/output",
                "--no-deps",
                "--platform",
                (
                    "manylinux2014_x86_64"
                    if self.architecture == "x86_64"
                    else "manylinux2014_aarch64"
                ),
                "--only-binary",
                ":all:",
            ],
            check=True,
            capture_output=True,
        )

    def build_all_functions(
        self, source_root: Path, output_dir: Path, environment: str = "dev"
    ) -> Dict[str, Path]:
        """
        Build all Lambda functions in a project.

        Args:
            source_root: Root directory containing Lambda functions
            output_dir: Output directory for built functions
            environment: Target environment

        Returns:
            Dictionary mapping function names to built paths
        """
        print(f"🔨 Building all Lambda functions for {self.config.name}")

        built_functions = {}

        # Find all Lambda functions
        for function_dir in source_root.iterdir():
            if function_dir.is_dir() and not function_dir.name.startswith("."):
                # Check if it's a Lambda function directory
                if self._is_lambda_function(function_dir):
                    output_path = self.build_function(
                        function_dir, output_dir, function_dir.name, environment
                    )
                    built_functions[function_dir.name] = output_path

        print(f"✅ Built {len(built_functions)} functions")
        return built_functions

    def _is_lambda_function(self, directory: Path) -> bool:
        """Check if a directory contains a Lambda function."""
        # Node.js indicators
        if self.runtime.startswith("nodejs"):
            return (directory / "index.js").exists() or (
                directory / "index.ts"
            ).exists()

        # Python indicators
        elif self.runtime.startswith("python"):
            return (directory / "lambda_function.py").exists() or (
                directory / "handler.py"
            ).exists()

        return False

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """Read JSON file."""
        import json

        with open(file_path, "r") as f:
            return json.load(f)
