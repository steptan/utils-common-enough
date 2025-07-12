"""Package Lambda functions for deployment."""

import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LambdaPackager:
    """Package Lambda functions into deployment artifacts."""

    def __init__(self, project_path: Path) -> None:
        """Initialize the packager.

        Args:
            project_path: Path to the project root
        """
        self.project_path: Path = Path(project_path)

    def create_deployment_package(
        self,
        source_dir: Path,
        output_file: Path,
        include_dependencies: bool = True,
        handler_info: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Create a Lambda deployment package (ZIP file).

        Args:
            source_dir: Directory containing Lambda function code
            output_file: Path for the output ZIP file
            include_dependencies: Whether to include node_modules
            handler_info: Optional handler configuration

        Returns:
            Path to the created ZIP file
        """
        source_dir: Path = Path(source_dir)
        output_file: Path = Path(output_file)

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating deployment package: {output_file}")

        # If including dependencies and package.json exists, install them
        if include_dependencies and (source_dir / "package.json").exists():
            self._install_production_dependencies(source_dir)

        # Create ZIP file
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from source directory
            for root, dirs, files in os.walk(source_dir):
                # Skip certain directories
                dirs[:] = [
                    d
                    for d in dirs
                    if d
                    not in [
                        ".git",
                        ".pytest_cache",
                        "__pycache__",
                        ".venv",
                        "venv",
                        "tests",
                        "test",
                    ]
                ]

                for file in files:
                    # Skip certain file types
                    if file.endswith((".pyc", ".pyo", ".git", ".DS_Store")):
                        continue

                    file_path = Path(root) / file
                    archive_path = file_path.relative_to(source_dir)

                    # Add file to zip
                    zipf.write(file_path, archive_path)

        # Get package size
        size_mb: float = output_file.stat().st_size / (1024 * 1024)
        logger.info(f"Package created: {output_file} ({size_mb:.2f} MB)")

        # Warn if package is large
        if size_mb > 50:
            logger.warning(
                f"Package size ({size_mb:.2f} MB) exceeds recommended limit of 50 MB. "
                "Consider using Lambda layers for dependencies."
            )
        elif size_mb > 250:
            logger.error(
                f"Package size ({size_mb:.2f} MB) exceeds Lambda limit of 250 MB. "
                "Use Lambda layers or container images."
            )

        return output_file

    def _install_production_dependencies(self, source_dir: Path) -> None:
        """Install production dependencies in the source directory.

        Args:
            source_dir: Directory containing package.json
        """
        logger.info("Installing production dependencies")

        # Create a temporary directory for clean install
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path: Path = Path(temp_dir)

            # Copy package.json (and lock file if exists)
            shutil.copy2(source_dir / "package.json", temp_path)

            for lock_file in ["package-lock.json", "yarn.lock"]:
                if (source_dir / lock_file).exists():
                    shutil.copy2(source_dir / lock_file, temp_path)

            # Determine package manager and install command
            if (temp_path / "yarn.lock").exists():
                install_cmd: List[str] = ["yarn", "install", "--production", "--frozen-lockfile"]
            elif (temp_path / "package-lock.json").exists():
                install_cmd = ["npm", "ci", "--omit=dev"]
            else:
                install_cmd = ["npm", "install", "--omit=dev"]

            # Install dependencies
            result: subprocess.CompletedProcess[str] = subprocess.run(
                install_cmd, cwd=temp_path, check=True, capture_output=True, text=True
            )

            # Copy node_modules to source directory
            if (temp_path / "node_modules").exists():
                # Remove existing node_modules if present
                if (source_dir / "node_modules").exists():
                    shutil.rmtree(source_dir / "node_modules")

                shutil.copytree(temp_path / "node_modules", source_dir / "node_modules")

    def create_layer_package(
        self, dependencies: Dict[str, str], runtime: str, output_file: Path
    ) -> Path:
        """Create a Lambda layer package for shared dependencies.

        Args:
            dependencies: Dictionary of package names and versions
            runtime: Lambda runtime (e.g., nodejs20.x)
            output_file: Path for the output ZIP file

        Returns:
            Path to the created layer ZIP file
        """
        output_file: Path = Path(output_file)

        logger.info(f"Creating Lambda layer package: {output_file}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path: Path = Path(temp_dir)

            # Determine the correct directory structure for the runtime
            if runtime.startswith("nodejs"):
                # Node.js layers expect dependencies in nodejs/node_modules
                layer_dir = temp_path / "nodejs"
                layer_dir.mkdir()

                # Create package.json
                package_json: Dict[str, Any] = {
                    "name": "lambda-layer",
                    "version": "1.0.0",
                    "dependencies": dependencies,
                }

                with open(layer_dir / "package.json", "w") as f:
                    import json

                    json.dump(package_json, f, indent=2)

                # Install dependencies
                result: subprocess.CompletedProcess[str] = subprocess.run(
                    ["npm", "install", "--omit=dev"],
                    cwd=layer_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            elif runtime.startswith("python"):
                # Python layers expect dependencies in python/
                layer_dir = temp_path / "python"
                layer_dir.mkdir()

                # Install Python dependencies
                for package, version in dependencies.items():
                    if version:
                        package_spec: str = f"{package}=={version}"
                    else:
                        package_spec = package

                    result: subprocess.CompletedProcess[str] = subprocess.run(
                        ["pip", "install", package_spec, "-t", str(layer_dir)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

            else:
                raise ValueError(f"Unsupported runtime for layers: {runtime}")

            # Create ZIP file
            with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_path):
                    for file in files:
                        file_path = Path(root) / file
                        archive_path = file_path.relative_to(temp_path)
                        zipf.write(file_path, archive_path)

        size_mb: float = output_file.stat().st_size / (1024 * 1024)
        logger.info(f"Layer package created: {output_file} ({size_mb:.2f} MB)")

        return output_file

    def validate_package(self, package_file: Path) -> bool:
        """Validate a Lambda deployment package.

        Args:
            package_file: Path to the ZIP file

        Returns:
            True if package is valid
        """
        package_file: Path = Path(package_file)

        if not package_file.exists():
            logger.error(f"Package file not found: {package_file}")
            return False

        if not zipfile.is_zipfile(package_file):
            logger.error(f"File is not a valid ZIP: {package_file}")
            return False

        # Check size
        size_mb: float = package_file.stat().st_size / (1024 * 1024)
        if size_mb > 250:
            logger.error(f"Package size ({size_mb:.2f} MB) exceeds Lambda limit")
            return False

        # Check contents
        with zipfile.ZipFile(package_file, "r") as zipf:
            files: List[str] = zipf.namelist()

            # Check for handler file
            has_handler: bool = any(
                f.startswith(("index.", "handler.", "lambda_function.")) for f in files
            )

            if not has_handler:
                logger.warning("No obvious handler file found in package")

        return True

    def extract_package(self, package_file: Path, output_dir: Path) -> Path:
        """Extract a Lambda deployment package for inspection.

        Args:
            package_file: Path to the ZIP file
            output_dir: Directory to extract to

        Returns:
            Path to extraction directory
        """
        package_file: Path = Path(package_file)
        output_dir: Path = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(package_file, "r") as zipf:
            zipf.extractall(output_dir)

        logger.info(f"Package extracted to: {output_dir}")
        return output_dir
