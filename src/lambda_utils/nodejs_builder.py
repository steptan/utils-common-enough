"""Node.js Lambda function builder."""

import os
import subprocess
import shutil
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class NodeJSBuilder:
    """Build Node.js Lambda functions."""

    def __init__(self, project_path: Path, runtime: str = "nodejs20.x"):
        """Initialize the Node.js builder.

        Args:
            project_path: Path to the project root
            runtime: Node.js runtime version
        """
        self.project_path = Path(project_path)
        self.runtime = runtime
        self.node_version = self._extract_node_version(runtime)

    def _extract_node_version(self, runtime: str) -> str:
        """Extract Node.js version from runtime string."""
        # nodejs20.x -> 20
        return runtime.replace("nodejs", "").replace(".x", "")

    def check_node_version(self) -> bool:
        """Check if the correct Node.js version is installed."""
        try:
            result = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, check=True
            )
            version = result.stdout.strip()
            major_version = version.split(".")[0].replace("v", "")

            if major_version != self.node_version:
                logger.warning(
                    f"Node.js version mismatch. Expected: {self.node_version}, "
                    f"Found: {major_version}"
                )
                return False
            return True
        except subprocess.CalledProcessError:
            logger.error("Node.js is not installed")
            return False

    def install_dependencies(self, lambda_path: Path, production: bool = True) -> None:
        """Install npm dependencies.

        Args:
            lambda_path: Path to the Lambda function directory
            production: Whether to install only production dependencies
        """
        logger.info(f"Installing dependencies in {lambda_path}")

        # Check if package.json exists
        package_json = lambda_path / "package.json"
        if not package_json.exists():
            raise FileNotFoundError(f"No package.json found in {lambda_path}")

        # Determine package manager
        if (lambda_path / "yarn.lock").exists():
            package_manager = "yarn"
            install_cmd = ["yarn", "install"]
            if production:
                install_cmd.append("--production")
        elif (lambda_path / "package-lock.json").exists():
            package_manager = "npm"
            install_cmd = ["npm", "ci"]
            if production:
                install_cmd.append("--omit=dev")
        else:
            package_manager = "npm"
            install_cmd = ["npm", "install"]
            if production:
                install_cmd.append("--omit=dev")

        logger.info(f"Using {package_manager} to install dependencies")

        # Run installation
        subprocess.run(
            install_cmd, cwd=lambda_path, check=True, capture_output=True, text=True
        )

    def build(self, lambda_path: Path, output_dir: Optional[Path] = None) -> Path:
        """Build a Node.js Lambda function.

        Args:
            lambda_path: Path to the Lambda function source
            output_dir: Output directory for built files

        Returns:
            Path to the built function directory
        """
        lambda_path = Path(lambda_path)
        if not output_dir:
            output_dir = lambda_path / "dist"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Building Node.js Lambda function from {lambda_path}")

        # Check for build script in package.json
        package_json_path = lambda_path / "package.json"
        if package_json_path.exists():
            with open(package_json_path) as f:
                package_data = json.load(f)

            scripts = package_data.get("scripts", {})

            # Run build script if it exists
            if "build" in scripts:
                logger.info("Running npm build script")
                subprocess.run(
                    ["npm", "run", "build"],
                    cwd=lambda_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                logger.info("No build script found, copying source files")
                # Copy source files (excluding common non-deploy files)
                exclude_patterns = [
                    "node_modules",
                    "test",
                    "tests",
                    "spec",
                    "*.test.js",
                    "*.spec.js",
                    "*.test.ts",
                    "*.spec.ts",
                    ".git",
                    ".gitignore",
                    "README.md",
                    "package-lock.json",
                    "yarn.lock",
                    "tsconfig.json",
                    ".eslintrc*",
                    ".prettierrc*",
                ]

                for item in lambda_path.iterdir():
                    if item.name not in exclude_patterns and not any(
                        item.match(pattern) for pattern in exclude_patterns
                    ):
                        if item.is_file():
                            shutil.copy2(item, output_dir)
                        elif item.is_dir():
                            shutil.copytree(
                                item,
                                output_dir / item.name,
                                ignore=shutil.ignore_patterns(*exclude_patterns),
                            )

        return output_dir

    def run_tests(self, lambda_path: Path) -> bool:
        """Run tests for the Lambda function.

        Args:
            lambda_path: Path to the Lambda function

        Returns:
            True if tests pass, False otherwise
        """
        package_json_path = lambda_path / "package.json"
        if not package_json_path.exists():
            logger.warning("No package.json found, skipping tests")
            return True

        with open(package_json_path) as f:
            package_data = json.load(f)

        scripts = package_data.get("scripts", {})

        if "test" not in scripts:
            logger.info("No test script found, skipping tests")
            return True

        logger.info("Running tests")
        try:
            subprocess.run(
                ["npm", "test"],
                cwd=lambda_path,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Tests passed")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Tests failed: {e.stderr}")
            return False

    def get_handler_info(self, lambda_path: Path) -> Dict[str, Any]:
        """Extract handler information from package.json or index file.

        Args:
            lambda_path: Path to the Lambda function

        Returns:
            Dictionary with handler information
        """
        info = {
            "handler": "index.handler",  # Default
            "runtime": self.runtime,
            "timeout": 30,
            "memory_size": 512,
        }

        # Check package.json for Lambda configuration
        package_json_path = lambda_path / "package.json"
        if package_json_path.exists():
            with open(package_json_path) as f:
                package_data = json.load(f)

            lambda_config = package_data.get("lambda", {})
            info.update(lambda_config)

        # Look for handler file
        for ext in [".js", ".mjs", ".ts"]:
            handler_file = lambda_path / f"index{ext}"
            if handler_file.exists():
                info["handler"] = f"index.handler"
                break

            handler_file = lambda_path / f"handler{ext}"
            if handler_file.exists():
                info["handler"] = f"handler.handler"
                break

        return info
