"""TypeScript compiler for Lambda functions."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TypeScriptCompiler:
    """Compile TypeScript Lambda functions."""

    def __init__(self, project_path: Path):
        """Initialize the TypeScript compiler.

        Args:
            project_path: Path to the project root
        """
        self.project_path = Path(project_path)

    def check_typescript_installed(self, lambda_path: Path) -> bool:
        """Check if TypeScript is installed in the project.

        Args:
            lambda_path: Path to check for TypeScript

        Returns:
            True if TypeScript is available
        """
        # Check local installation
        local_tsc = lambda_path / "node_modules" / ".bin" / "tsc"
        if local_tsc.exists():
            return True

        # Check global installation
        try:
            subprocess.run(["tsc", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_tsconfig(self, lambda_path: Path) -> Dict[str, Any]:
        """Load TypeScript configuration.

        Args:
            lambda_path: Path to the Lambda function

        Returns:
            TypeScript configuration dictionary
        """
        tsconfig_path = lambda_path / "tsconfig.json"

        if not tsconfig_path.exists():
            # Return default configuration
            return {
                "compilerOptions": {
                    "target": "ES2022",
                    "module": "commonjs",
                    "lib": ["ES2022"],
                    "outDir": "./dist",
                    "rootDir": "./src",
                    "strict": True,
                    "esModuleInterop": True,
                    "skipLibCheck": True,
                    "forceConsistentCasingInFileNames": True,
                    "resolveJsonModule": True,
                    "removeComments": True,
                    "sourceMap": True,
                },
                "exclude": [
                    "node_modules",
                    "dist",
                    "tests",
                    "**/*.test.ts",
                    "**/*.spec.ts",
                ],
            }

        with open(tsconfig_path) as f:
            return json.load(f)

    def compile(self, lambda_path: Path, output_dir: Optional[Path] = None) -> Path:
        """Compile TypeScript files.

        Args:
            lambda_path: Path to the Lambda function source
            output_dir: Output directory for compiled files

        Returns:
            Path to compiled output directory
        """
        lambda_path = Path(lambda_path)

        # Check if TypeScript is installed
        if not self.check_typescript_installed(lambda_path):
            raise RuntimeError(
                "TypeScript is not installed. Run 'npm install --save-dev typescript' "
                "in the Lambda function directory."
            )

        # Determine output directory from tsconfig or use default
        tsconfig = self.get_tsconfig(lambda_path)
        compiler_options = tsconfig.get("compilerOptions", {})

        if not output_dir:
            output_dir = compiler_options.get("outDir", "./dist")
            if not Path(output_dir).is_absolute():
                output_dir = lambda_path / output_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Compiling TypeScript files from {lambda_path}")

        # Determine tsc command
        local_tsc = lambda_path / "node_modules" / ".bin" / "tsc"
        tsc_cmd = str(local_tsc) if local_tsc.exists() else "tsc"

        # Create temporary tsconfig if needed
        temp_tsconfig = None
        if not (lambda_path / "tsconfig.json").exists():
            temp_tsconfig = lambda_path / "tsconfig.temp.json"
            logger.info("Creating temporary tsconfig.json")

            # Update outDir to be relative to lambda_path
            tsconfig["compilerOptions"]["outDir"] = str(
                output_dir.relative_to(lambda_path)
            )

            with open(temp_tsconfig, "w") as f:
                json.dump(tsconfig, f, indent=2)

        try:
            # Run TypeScript compiler
            cmd = [tsc_cmd]
            if temp_tsconfig:
                cmd.extend(["-p", str(temp_tsconfig)])
            else:
                cmd.extend(["-p", str(lambda_path)])

            result = subprocess.run(
                cmd, cwd=lambda_path, capture_output=True, text=True
            )

            if result.returncode != 0:
                logger.error(f"TypeScript compilation failed: {result.stderr}")
                raise RuntimeError(f"TypeScript compilation failed: {result.stderr}")

            logger.info("TypeScript compilation successful")

            # Copy package.json to output directory (needed for dependencies)
            package_json_src = lambda_path / "package.json"
            if package_json_src.exists():
                package_json_dst = output_dir / "package.json"
                shutil.copy2(package_json_src, package_json_dst)

                # Update package.json to remove dev dependencies and scripts
                with open(package_json_dst) as f:
                    package_data = json.load(f)

                # Remove dev dependencies and scripts for production
                package_data.pop("devDependencies", None)
                package_data.pop("scripts", None)

                with open(package_json_dst, "w") as f:
                    json.dump(package_data, f, indent=2)

            return output_dir

        finally:
            # Clean up temporary tsconfig
            if temp_tsconfig and temp_tsconfig.exists():
                temp_tsconfig.unlink()

    def get_source_files(self, lambda_path: Path) -> List[Path]:
        """Get list of TypeScript source files.

        Args:
            lambda_path: Path to the Lambda function

        Returns:
            List of TypeScript file paths
        """
        ts_files = []

        # Get file patterns from tsconfig
        tsconfig = self.get_tsconfig(lambda_path)
        exclude_patterns = tsconfig.get("exclude", ["node_modules", "dist"])

        # Find all .ts files
        for ts_file in lambda_path.rglob("*.ts"):
            # Skip excluded paths
            relative_path = ts_file.relative_to(lambda_path)
            if not any(pattern in str(relative_path) for pattern in exclude_patterns):
                ts_files.append(ts_file)

        return ts_files

    def validate_types(self, lambda_path: Path) -> bool:
        """Run TypeScript type checking without emitting files.

        Args:
            lambda_path: Path to the Lambda function

        Returns:
            True if type checking passes
        """
        lambda_path = Path(lambda_path)

        if not self.check_typescript_installed(lambda_path):
            logger.warning("TypeScript not installed, skipping type validation")
            return True

        logger.info("Running TypeScript type checking")

        # Determine tsc command
        local_tsc = lambda_path / "node_modules" / ".bin" / "tsc"
        tsc_cmd = str(local_tsc) if local_tsc.exists() else "tsc"

        try:
            subprocess.run(
                [tsc_cmd, "--noEmit", "-p", str(lambda_path)],
                cwd=lambda_path,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("Type checking passed")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Type checking failed: {e.stderr}")
            return False
