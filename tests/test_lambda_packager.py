"""
Tests for Lambda packaging functionality.
"""

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, call, patch

from typing import Any, Dict, List, Optional, Union

import pytest

from lambda_utils.packager import LambdaPackager


class TestLambdaPackager:
    """Test Lambda packaging functionality."""

    def create_packager(self):
        """Create a Lambda packager instance."""
        return LambdaPackager(Path.cwd())

    def test_package_nodejs_lambda_basic(self, tmp_path) -> None:
        """Test basic Node.js Lambda packaging."""
        packager = self.create_packager()

        # Create test source directory
        source_dir = tmp_path / "lambda-src"
        source_dir.mkdir()

        # Create index.js
        index_js = source_dir / "index.js"
        index_js.write_text(
            """
        exports.handler = async (event) => {
            return {
                statusCode: 200,
                body: JSON.stringify('Hello from Lambda!')
            };
        };
        """
        )

        # Create package.json
        package_json = source_dir / "package.json"
        package_json.write_text(
            json.dumps({"name": "test-lambda", "version": "1.0.0", "main": "index.js"})
        )

        # Package Lambda
        output_path = tmp_path / "lambda.zip"

        with patch("subprocess.run") as mock_run:
            # Mock npm install
            mock_run.return_value = Mock(returncode=0, stderr="")

            result = packager.package_nodejs_lambda(
                source_dir=source_dir,
                output_path=output_path,
                handler="index.handler",
                minify=False,
            )

        # Verify package was created
        assert result == output_path
        assert output_path.exists()

        # Verify zip contents
        with zipfile.ZipFile(output_path, "r") as zf:
            files = zf.namelist()
            assert any("index.js" in f for f in files)

    def test_package_nodejs_lambda_with_typescript(self, tmp_path) -> None:
        """Test Node.js Lambda packaging with TypeScript."""
        packager = self.create_packager()

        # Create test source directory
        source_dir = tmp_path / "lambda-src"
        source_dir.mkdir()

        # Create TypeScript file
        index_ts = source_dir / "index.ts"
        index_ts.write_text(
            """
        export const handler = async (event: any) => {
            return {
                statusCode: 200,
                body: JSON.stringify('Hello from TypeScript Lambda!')
            };
        };
        """
        )

        # Create tsconfig.json
        tsconfig = source_dir / "tsconfig.json"
        tsconfig.write_text(
            json.dumps(
                {
                    "compilerOptions": {
                        "target": "ES2020",
                        "module": "commonjs",
                        "outDir": "./dist",
                    }
                }
            )
        )

        # Create package.json
        package_json = source_dir / "package.json"
        package_json.write_text(json.dumps({"name": "test-lambda", "version": "1.0.0"}))

        output_path = tmp_path / "lambda.zip"

        with patch("subprocess.run") as mock_run:
            # Mock npm install and tsc
            mock_run.return_value = Mock(returncode=0, stderr="")

            # Mock dist directory creation
            with patch("shutil.copytree"), patch("shutil.copy2"):
                result = packager.package_nodejs_lambda(
                    source_dir=source_dir,
                    output_path=output_path,
                    handler="index.handler",
                )

        # Verify TypeScript compilation was called
        calls = mock_run.call_args_list
        assert any("tsc" in str(call) for call in calls)

    def test_package_python_lambda_basic(self, tmp_path) -> None:
        """Test basic Python Lambda packaging."""
        packager = self.create_packager()

        # Create test source directory
        source_dir = tmp_path / "lambda-src"
        source_dir.mkdir()

        # Create handler.py
        handler_py = source_dir / "handler.py"
        handler_py.write_text(
            """
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello from Python Lambda!'
    }
        """
        )

        # Package Lambda
        output_path = tmp_path / "lambda.zip"

        result = packager.package_python_lambda(
            source_dir=source_dir,
            output_path=output_path,
            handler="handler.lambda_handler",
        )

        # Verify package was created
        assert result == output_path
        assert output_path.exists()

        # Verify zip contents
        with zipfile.ZipFile(output_path, "r") as zf:
            files = zf.namelist()
            assert "handler.py" in files

    def test_package_python_lambda_with_requirements(self, tmp_path) -> None:
        """Test Python Lambda packaging with requirements."""
        packager = self.create_packager()

        # Create test source directory
        source_dir = tmp_path / "lambda-src"
        source_dir.mkdir()

        # Create handler.py
        handler_py = source_dir / "handler.py"
        handler_py.write_text(
            """
import requests

def lambda_handler(event, context):
    return {'statusCode': 200}
        """
        )

        # Create requirements.txt
        requirements = source_dir / "requirements.txt"
        requirements.write_text("requests==2.28.0\n")

        output_path = tmp_path / "lambda.zip"

        with patch("subprocess.run") as mock_run:
            # Mock pip install
            mock_run.return_value = Mock(returncode=0, stderr="")

            result = packager.package_python_lambda(
                source_dir=source_dir,
                output_path=output_path,
                handler="handler.lambda_handler",
            )

        # Verify pip install was called
        calls = mock_run.call_args_list
        assert any("pip" in str(call) and "install" in str(call) for call in calls)

    def test_validate_package_valid(self, tmp_path) -> None:
        """Test validating a valid Lambda package."""
        packager = self.create_packager()

        # Create a valid zip file
        zip_path = tmp_path / "lambda.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("index.js", "exports.handler = async () => {};")

        # Validate package
        is_valid = packager.validate_package(
            package_path=zip_path, handler="index.handler", runtime="nodejs20.x"
        )

        assert is_valid is True

    def test_validate_package_missing_handler(self, tmp_path) -> None:
        """Test validating package with missing handler."""
        packager = self.create_packager()

        # Create zip without handler file
        zip_path = tmp_path / "lambda.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("other.js", "// some code")

        # Validate package
        is_valid = packager.validate_package(
            package_path=zip_path, handler="index.handler", runtime="nodejs20.x"
        )

        assert is_valid is False

    def test_validate_package_size_warning(self, tmp_path) -> None:
        """Test package size warning."""
        packager = self.create_packager()

        # Create large zip file (simulate > 50MB)
        zip_path = tmp_path / "lambda.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Add handler
            zf.writestr("handler.py", "def lambda_handler(event, context): pass")
            # Add large file
            zf.writestr("large_file.dat", "x" * (51 * 1024 * 1024))  # 51MB

        with patch("builtins.print") as mock_print:
            is_valid = packager.validate_package(
                package_path=zip_path,
                handler="handler.lambda_handler",
                runtime="python3.11",
            )

        # Should still be valid but with warning
        assert is_valid is True

        # Check for size warning
        warning_printed = any(
            "exceeds 50MB limit" in str(call) for call in mock_print.call_args_list
        )
        assert warning_printed

    def test_minify_javascript(self, tmp_path) -> None:
        """Test JavaScript minification."""
        packager = self.create_packager()

        # Create test directory with JS file
        test_dir = tmp_path / "dist"
        test_dir.mkdir()

        js_file = test_dir / "index.js"
        js_file.write_text(
            """
        // This is a comment
        function hello() {
            const message = "Hello World";
            console.log(message);
        }
        """
        )

        with patch("subprocess.run") as mock_run:
            # Mock terser
            mock_run.return_value = Mock(returncode=0)

            packager._minify_javascript(test_dir)

            # Verify terser was called
            calls = mock_run.call_args_list
            assert any("terser" in str(call) for call in calls)

    def test_create_zip_excludes_unnecessary_files(self, tmp_path) -> None:
        """Test that zip excludes unnecessary files."""
        packager = self.create_packager()

        # Create test directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create various files
        (source_dir / "handler.py").write_text("# handler")
        (source_dir / "__pycache__").mkdir()
        (source_dir / "__pycache__" / "handler.pyc").write_text("compiled")
        (source_dir / ".git").mkdir()
        (source_dir / ".git" / "config").write_text("git config")
        (source_dir / "tests").mkdir()
        (source_dir / "tests" / "test_handler.py").write_text("# test")
        (source_dir / ".DS_Store").write_text("mac file")

        output_path = tmp_path / "lambda.zip"

        packager._create_zip(source_dir, output_path, "handler.lambda_handler")

        # Verify zip contents
        with zipfile.ZipFile(output_path, "r") as zf:
            files = zf.namelist()

            # Should include
            assert "handler.py" in files

            # Should exclude
            assert not any("__pycache__" in f for f in files)
            assert not any(".git" in f for f in files)
            assert not any("tests" in f for f in files)
            assert not any(".DS_Store" in f for f in files)
            assert not any(".pyc" in f for f in files)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
