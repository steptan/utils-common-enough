"""
Comprehensive tests for Lambda packager module.
Tests Lambda function packaging, layer creation, and validation.
"""

import json
import pytest
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

from typing import Any, Dict, List, Optional, Union

from src.lambda_utils.packager import LambdaPackager


class TestLambdaPackager:
    """Test LambdaPackager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_path = Path(self.temp_dir)
        self.packager = LambdaPackager(self.project_path)
        
        # Create sample Lambda function structure
        self.lambda_dir = self.project_path / "lambda"
        self.lambda_dir.mkdir(parents=True)
        
        # Create sample files
        (self.lambda_dir / "index.js").write_text(
            'exports.handler = async (event) => { return { statusCode: 200 }; };'
        )
        (self.lambda_dir / "package.json").write_text(
            json.dumps({
                "name": "test-lambda",
                "version": "1.0.0",
                "dependencies": {
                    "aws-sdk": "^2.1000.0"
                }
            })
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self) -> None:
        """Test packager initialization."""
        packager = LambdaPackager(self.project_path)
        assert packager.project_path == self.project_path

    def test_create_deployment_package_basic(self) -> None:
        """Test basic deployment package creation."""
        output_file = self.project_path / "lambda.zip"
        
        result = self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )

        assert result == output_file
        assert output_file.exists()
        assert zipfile.is_zipfile(output_file)

        # Check contents
        with zipfile.ZipFile(output_file, 'r') as zf:
            files = zf.namelist()
            assert "index.js" in files
            assert "package.json" in files

    @patch('subprocess.run')
    def test_create_deployment_package_with_dependencies(self, mock_run) -> None:
        """Test deployment package creation with dependencies."""
        mock_run.return_value = Mock(returncode=0)
        
        # Create fake node_modules in temp dir
        with tempfile.TemporaryDirectory() as temp_install_dir:
            mock_run.side_effect = lambda *args, **kwargs: self._create_fake_node_modules(
                kwargs.get('cwd', Path(temp_install_dir))
            )
            
            output_file = self.project_path / "lambda.zip"
            
            result = self.packager.create_deployment_package(
                source_dir=self.lambda_dir,
                output_file=output_file,
                include_dependencies=True
            )

            assert result == output_file
            assert output_file.exists()
            
            # Check npm was called
            assert mock_run.called

    def _create_fake_node_modules(self, cwd):
        """Helper to create fake node_modules structure."""
        node_modules = Path(cwd) / "node_modules"
        node_modules.mkdir(exist_ok=True)
        (node_modules / "aws-sdk").mkdir(exist_ok=True)
        (node_modules / "aws-sdk" / "index.js").write_text("// AWS SDK")
        return Mock(returncode=0)

    def test_create_deployment_package_excludes_files(self) -> None:
        """Test that certain files and directories are excluded."""
        # Create files that should be excluded
        (self.lambda_dir / ".git").mkdir()
        (self.lambda_dir / ".git" / "config").write_text("git config")
        (self.lambda_dir / "__pycache__").mkdir()
        (self.lambda_dir / "__pycache__" / "test.pyc").write_text("pyc file")
        (self.lambda_dir / ".DS_Store").write_text("mac file")
        (self.lambda_dir / "test.pyc").write_text("pyc file")
        (self.lambda_dir / "tests").mkdir()
        (self.lambda_dir / "tests" / "test_handler.js").write_text("test file")

        output_file = self.project_path / "lambda.zip"
        
        self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )

        # Check excluded files are not in zip
        with zipfile.ZipFile(output_file, 'r') as zf:
            files = zf.namelist()
            assert ".git/config" not in files
            assert "__pycache__/test.pyc" not in files
            assert ".DS_Store" not in files
            assert "test.pyc" not in files
            assert "tests/test_handler.js" not in files
            # But our main files should be there
            assert "index.js" in files
            assert "package.json" in files

    @patch('src.lambda_utils.packager.logger')
    def test_create_deployment_package_size_warnings(self, mock_logger) -> None:
        """Test package size warnings."""
        # Create a large file
        large_file = self.lambda_dir / "large.bin"
        large_file.write_bytes(b'0' * (51 * 1024 * 1024))  # 51 MB

        output_file = self.project_path / "lambda.zip"
        
        self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )

        # Check warning was logged
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "exceeds recommended limit" in warning_msg

    @patch('src.lambda_utils.packager.logger')
    def test_create_deployment_package_size_error(self, mock_logger) -> None:
        """Test package size error."""
        # Create a very large file (this test is theoretical as we don't want to create 250MB)
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=260 * 1024 * 1024)  # 260 MB
            
            output_file = self.project_path / "lambda.zip"
            
            self.packager.create_deployment_package(
                source_dir=self.lambda_dir,
                output_file=output_file,
                include_dependencies=False
            )

            # Check error was logged
            mock_logger.error.assert_called()
            error_msg = mock_logger.error.call_args[0][0]
            assert "exceeds Lambda limit" in error_msg

    def test_create_deployment_package_creates_parent_dirs(self) -> None:
        """Test that parent directories are created if needed."""
        output_file = self.project_path / "dist" / "functions" / "lambda.zip"
        
        result = self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )

        assert result == output_file
        assert output_file.exists()
        assert output_file.parent.exists()

    @patch('subprocess.run')
    def test_install_production_dependencies_npm(self, mock_run) -> None:
        """Test npm dependency installation."""
        mock_run.return_value = Mock(returncode=0)
        
        # Create package-lock.json
        (self.lambda_dir / "package-lock.json").write_text('{"lockfileVersion": 2}')
        
        with patch('shutil.copytree'):
            self.packager._install_production_dependencies(self.lambda_dir)
        
        # Check npm ci was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        assert call_args == ["npm", "ci", "--omit=dev"]

    @patch('subprocess.run')
    def test_install_production_dependencies_yarn(self, mock_run) -> None:
        """Test yarn dependency installation."""
        mock_run.return_value = Mock(returncode=0)
        
        # Create yarn.lock
        (self.lambda_dir / "yarn.lock").write_text('# yarn lockfile v1')
        
        with patch('shutil.copytree'):
            self.packager._install_production_dependencies(self.lambda_dir)
        
        # Check yarn was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        assert call_args == ["yarn", "install", "--production", "--frozen-lockfile"]

    @patch('subprocess.run')
    def test_install_production_dependencies_no_lock(self, mock_run) -> None:
        """Test dependency installation without lock file."""
        mock_run.return_value = Mock(returncode=0)
        
        with patch('shutil.copytree'):
            self.packager._install_production_dependencies(self.lambda_dir)
        
        # Check npm install was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        assert call_args == ["npm", "install", "--omit=dev"]

    @patch('subprocess.run')
    def test_create_layer_package_nodejs(self, mock_run) -> None:
        """Test Node.js layer package creation."""
        mock_run.return_value = Mock(returncode=0)
        
        dependencies = {
            "lodash": "^4.17.21",
            "moment": "^2.29.4"
        }
        
        output_file = self.project_path / "layer.zip"
        
        # Mock npm install to create fake node_modules
        def create_node_modules(*args, **kwargs):
            cwd = kwargs.get('cwd')
            if cwd:
                node_modules = Path(cwd) / "node_modules"
                node_modules.mkdir()
                (node_modules / "lodash").mkdir()
                (node_modules / "lodash" / "index.js").write_text("// lodash")
            return Mock(returncode=0)
        
        mock_run.side_effect = create_node_modules
        
        result = self.packager.create_layer_package(
            dependencies=dependencies,
            runtime="nodejs20.x",
            output_file=output_file
        )

        assert result == output_file
        assert output_file.exists()
        
        # Check structure
        with zipfile.ZipFile(output_file, 'r') as zf:
            files = zf.namelist()
            assert "nodejs/package.json" in files
            assert any("nodejs/node_modules" in f for f in files)

    @patch('subprocess.run')
    def test_create_layer_package_python(self, mock_run) -> None:
        """Test Python layer package creation."""
        mock_run.return_value = Mock(returncode=0)
        
        dependencies = {
            "requests": "2.28.0",
            "boto3": ""  # No version specified
        }
        
        output_file = self.project_path / "layer.zip"
        
        # Mock pip install to create fake packages
        def create_python_packages(*args, **kwargs):
            target_dir = None
            for i, arg in enumerate(args[0]):
                if arg == "-t":
                    target_dir = Path(args[0][i + 1])
                    break
            
            if target_dir:
                (target_dir / "requests").mkdir(parents=True)
                (target_dir / "requests" / "__init__.py").write_text("# requests")
            return Mock(returncode=0)
        
        mock_run.side_effect = create_python_packages
        
        result = self.packager.create_layer_package(
            dependencies=dependencies,
            runtime="python3.11",
            output_file=output_file
        )

        assert result == output_file
        assert output_file.exists()
        
        # Check pip install calls
        assert mock_run.call_count == 2
        pip_calls = [call[0][0] for call in mock_run.call_args_list]
        assert ["pip", "install", "requests==2.28.0", "-t", mock.ANY] in pip_calls
        assert ["pip", "install", "boto3", "-t", mock.ANY] in pip_calls

    def test_create_layer_package_unsupported_runtime(self) -> None:
        """Test layer package creation with unsupported runtime."""
        output_file = self.project_path / "layer.zip"
        
        with pytest.raises(ValueError) as exc_info:
            self.packager.create_layer_package(
                dependencies={"test": "1.0.0"},
                runtime="ruby2.7",
                output_file=output_file
            )
        
        assert "Unsupported runtime" in str(exc_info.value)

    def test_validate_package_valid(self) -> None:
        """Test package validation with valid package."""
        # Create a valid package
        output_file = self.project_path / "lambda.zip"
        self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )

        result = self.packager.validate_package(output_file)
        assert result is True

    def test_validate_package_not_exists(self) -> None:
        """Test package validation with non-existent file."""
        result = self.packager.validate_package(self.project_path / "missing.zip")
        assert result is False

    def test_validate_package_not_zip(self) -> None:
        """Test package validation with non-zip file."""
        not_zip = self.project_path / "not_zip.txt"
        not_zip.write_text("This is not a zip file")
        
        result = self.packager.validate_package(not_zip)
        assert result is False

    @patch('pathlib.Path.stat')
    def test_validate_package_too_large(self, mock_stat) -> None:
        """Test package validation with oversized package."""
        mock_stat.return_value = Mock(st_size=260 * 1024 * 1024)  # 260 MB
        
        output_file = self.project_path / "lambda.zip"
        self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )
        
        result = self.packager.validate_package(output_file)
        assert result is False

    @patch('src.lambda_utils.packager.logger')
    def test_validate_package_no_handler_warning(self, mock_logger) -> None:
        """Test package validation warns when no handler found."""
        # Create package without handler files
        no_handler_dir = self.project_path / "no_handler"
        no_handler_dir.mkdir()
        (no_handler_dir / "utils.js").write_text("// utilities")
        
        output_file = self.project_path / "lambda.zip"
        self.packager.create_deployment_package(
            source_dir=no_handler_dir,
            output_file=output_file,
            include_dependencies=False
        )
        
        result = self.packager.validate_package(output_file)
        assert result is True  # Still valid, just warns
        
        # Check warning was logged
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "No obvious handler file found" in warning_msg

    def test_extract_package(self) -> None:
        """Test package extraction."""
        # Create a package first
        output_file = self.project_path / "lambda.zip"
        self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )

        # Extract it
        extract_dir = self.project_path / "extracted"
        result = self.packager.extract_package(output_file, extract_dir)

        assert result == extract_dir
        assert extract_dir.exists()
        assert (extract_dir / "index.js").exists()
        assert (extract_dir / "package.json").exists()

    def test_extract_package_creates_dir(self) -> None:
        """Test package extraction creates output directory."""
        output_file = self.project_path / "lambda.zip"
        self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False
        )

        # Extract to non-existent directory
        extract_dir = self.project_path / "new" / "extract" / "dir"
        result = self.packager.extract_package(output_file, extract_dir)

        assert result == extract_dir
        assert extract_dir.exists()
        assert (extract_dir / "index.js").exists()

    def test_handler_info_parameter(self) -> None:
        """Test handler_info parameter (currently unused but in signature)."""
        output_file = self.project_path / "lambda.zip"
        handler_info = {
            "handler": "index.handler",
            "runtime": "nodejs20.x"
        }
        
        result = self.packager.create_deployment_package(
            source_dir=self.lambda_dir,
            output_file=output_file,
            include_dependencies=False,
            handler_info=handler_info
        )

        assert result == output_file
        assert output_file.exists()