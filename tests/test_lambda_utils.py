"""
Comprehensive tests for Lambda utilities including building and packaging.
"""

import pytest
import os
import json
import zipfile
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

from lambda_utils.builder import LambdaBuilder
from lambda_utils.nodejs_builder import NodeJSBuilder
from lambda_utils.packager import LambdaPackager
from lambda_utils.typescript_compiler import TypeScriptCompiler
from config import ProjectConfig


class TestLambdaBuilder:
    """Test base Lambda builder functionality."""
    
    @pytest.fixture
    def basic_config(self):
        """Create a basic project configuration."""
        return ProjectConfig(
            name="test-project",
            display_name="Test Project",
            aws_region="us-east-1",
            lambda_runtime="nodejs18.x"
        )
    
    @pytest.fixture
    def builder(self, basic_config):
        """Create a LambdaBuilder instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            return LambdaBuilder(
                function_path=Path(tmpdir) / "lambda",
                output_path=Path(tmpdir) / "dist",
                config=basic_config
            )
    
    def test_initialization(self, builder):
        """Test LambdaBuilder initialization."""
        assert builder.function_path.name == "lambda"
        assert builder.output_path.name == "dist"
        assert builder.runtime == "nodejs18.x"
    
    def test_validate_function_path(self, builder):
        """Test function path validation."""
        # Non-existent path should fail
        assert not builder.validate_function_path()
        
        # Create the path
        builder.function_path.mkdir(parents=True)
        assert builder.validate_function_path()
    
    def test_prepare_output_directory(self, builder):
        """Test output directory preparation."""
        builder.prepare_output_directory()
        
        assert builder.output_path.exists()
        assert builder.output_path.is_dir()
    
    def test_copy_source_files(self, builder):
        """Test copying source files."""
        # Create source files
        builder.function_path.mkdir(parents=True)
        (builder.function_path / "index.js").write_text("console.log('test');")
        (builder.function_path / "package.json").write_text('{"name":"test"}')
        
        # Create a node_modules directory that should be ignored
        (builder.function_path / "node_modules").mkdir()
        (builder.function_path / "node_modules" / "module.js").write_text("module")
        
        builder.prepare_output_directory()
        builder.copy_source_files()
        
        # Check files were copied
        assert (builder.output_path / "index.js").exists()
        assert (builder.output_path / "package.json").exists()
        
        # Check node_modules was not copied
        assert not (builder.output_path / "node_modules").exists()
    
    def test_get_builder_for_runtime(self):
        """Test getting appropriate builder for runtime."""
        # Node.js runtime
        node_builder = LambdaBuilder.get_builder_for_runtime(
            "nodejs18.x",
            Path("/tmp/func"),
            Path("/tmp/out")
        )
        assert isinstance(node_builder, NodeJSBuilder)
        
        # Python runtime (when implemented)
        with pytest.raises(ValueError, match="Unsupported runtime"):
            LambdaBuilder.get_builder_for_runtime(
                "python3.11",
                Path("/tmp/func"),
                Path("/tmp/out")
            )


class TestNodeJSBuilder:
    """Test Node.js Lambda builder functionality."""
    
    @pytest.fixture
    def builder(self):
        """Create a NodeJSBuilder instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            return NodeJSBuilder(
                function_path=Path(tmpdir) / "lambda",
                output_path=Path(tmpdir) / "dist"
            )
    
    def test_detect_package_manager(self, builder):
        """Test package manager detection."""
        builder.function_path.mkdir(parents=True)
        
        # Test npm detection
        (builder.function_path / "package-lock.json").touch()
        assert builder.detect_package_manager() == "npm"
        
        # Test yarn detection
        (builder.function_path / "package-lock.json").unlink()
        (builder.function_path / "yarn.lock").touch()
        assert builder.detect_package_manager() == "yarn"
        
        # Test pnpm detection
        (builder.function_path / "yarn.lock").unlink()
        (builder.function_path / "pnpm-lock.yaml").touch()
        assert builder.detect_package_manager() == "pnpm"
        
        # Default to npm
        (builder.function_path / "pnpm-lock.yaml").unlink()
        assert builder.detect_package_manager() == "npm"
    
    def test_install_dependencies_npm(self, builder):
        """Test npm dependency installation."""
        builder.output_path.mkdir(parents=True)
        (builder.output_path / "package.json").write_text(json.dumps({
            "name": "test-function",
            "dependencies": {
                "aws-sdk": "^2.1000.0"
            }
        }))
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            result = builder.install_dependencies()
            
            assert result is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "npm"
            assert "install" in args
            assert "--production" in args
    
    def test_install_dependencies_yarn(self, builder):
        """Test yarn dependency installation."""
        builder.output_path.mkdir(parents=True)
        (builder.output_path / "package.json").write_text('{"name":"test"}')
        (builder.output_path / "yarn.lock").touch()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            # Override package manager detection
            with patch.object(builder, 'detect_package_manager', return_value='yarn'):
                result = builder.install_dependencies()
            
            assert result is True
            args = mock_run.call_args[0][0]
            assert args[0] == "yarn"
            assert "install" in args
            assert "--production" in args
    
    def test_build_typescript(self, builder):
        """Test TypeScript compilation."""
        builder.function_path.mkdir(parents=True)
        builder.output_path.mkdir(parents=True)
        
        # Create TypeScript files
        (builder.function_path / "index.ts").write_text(
            'export const handler = async () => ({ statusCode: 200 });'
        )
        (builder.function_path / "tsconfig.json").write_text(json.dumps({
            "compilerOptions": {
                "target": "es2020",
                "module": "commonjs",
                "outDir": "./dist"
            }
        }))
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            result = builder.build_typescript()
            
            assert result is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "tsc" in args[0] or args[0] == "npx"
    
    def test_build_process(self, builder):
        """Test complete build process."""
        # Setup
        builder.function_path.mkdir(parents=True)
        (builder.function_path / "index.js").write_text('exports.handler = async () => {};')
        (builder.function_path / "package.json").write_text(json.dumps({
            "name": "test-function",
            "dependencies": {"aws-sdk": "^2.1000.0"}
        }))
        
        with patch.object(builder, 'install_dependencies', return_value=True):
            result = builder.build()
            
            assert result is True
            assert builder.output_path.exists()
            assert (builder.output_path / "index.js").exists()
            assert (builder.output_path / "package.json").exists()


class TestLambdaPackager:
    """Test Lambda packaging functionality."""
    
    @pytest.fixture
    def packager(self):
        """Create a LambdaPackager instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            return LambdaPackager(
                build_path=Path(tmpdir) / "dist",
                output_file=Path(tmpdir) / "function.zip"
            )
    
    def test_initialization(self, packager):
        """Test LambdaPackager initialization."""
        assert packager.build_path.name == "dist"
        assert packager.output_file.name == "function.zip"
    
    def test_create_deployment_package(self, packager):
        """Test creating deployment package."""
        # Create build directory with files
        packager.build_path.mkdir(parents=True)
        (packager.build_path / "index.js").write_text('exports.handler = async () => {};')
        (packager.build_path / "package.json").write_text('{"name":"test"}')
        
        # Create nested directory
        (packager.build_path / "lib").mkdir()
        (packager.build_path / "lib" / "helper.js").write_text('module.exports = {};')
        
        result = packager.create_package()
        
        assert result is True
        assert packager.output_file.exists()
        
        # Verify zip contents
        with zipfile.ZipFile(packager.output_file, 'r') as zf:
            files = zf.namelist()
            assert "index.js" in files
            assert "package.json" in files
            assert "lib/helper.js" in files
    
    def test_validate_package_size(self, packager):
        """Test package size validation."""
        packager.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a small file
        with open(packager.output_file, 'wb') as f:
            f.write(b'x' * 1024 * 1024)  # 1 MB
        
        assert packager.validate_package_size() is True
        
        # Create a large file (over 250 MB unzipped limit)
        with open(packager.output_file, 'wb') as f:
            f.write(b'x' * 260 * 1024 * 1024)  # 260 MB
        
        assert packager.validate_package_size() is False
    
    def test_add_file_to_zip(self, packager):
        """Test adding individual files to zip."""
        packager.build_path.mkdir(parents=True)
        packager.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        test_file = packager.build_path / "test.txt"
        test_file.write_text("test content")
        
        with zipfile.ZipFile(packager.output_file, 'w') as zf:
            packager.add_file_to_zip(zf, test_file, "test.txt")
        
        # Verify file was added
        with zipfile.ZipFile(packager.output_file, 'r') as zf:
            assert "test.txt" in zf.namelist()
            assert zf.read("test.txt").decode() == "test content"
    
    def test_package_with_layers(self, packager):
        """Test packaging with Lambda layers (excludes dependencies)."""
        packager.build_path.mkdir(parents=True)
        (packager.build_path / "index.js").write_text('exports.handler = async () => {};')
        
        # Dependencies that should be excluded when using layers
        (packager.build_path / "node_modules").mkdir()
        (packager.build_path / "node_modules" / "aws-sdk").mkdir()
        (packager.build_path / "node_modules" / "aws-sdk" / "index.js").write_text('module.exports = {};')
        
        result = packager.create_package(exclude_dependencies=True)
        
        assert result is True
        
        # Verify node_modules was excluded
        with zipfile.ZipFile(packager.output_file, 'r') as zf:
            files = zf.namelist()
            assert "index.js" in files
            assert not any("node_modules" in f for f in files)


class TestTypeScriptCompiler:
    """Test TypeScript compilation functionality."""
    
    @pytest.fixture
    def compiler(self):
        """Create a TypeScriptCompiler instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            return TypeScriptCompiler(
                source_path=Path(tmpdir) / "src",
                output_path=Path(tmpdir) / "dist"
            )
    
    def test_initialization(self, compiler):
        """Test TypeScriptCompiler initialization."""
        assert compiler.source_path.name == "src"
        assert compiler.output_path.name == "dist"
    
    def test_check_typescript_available(self, compiler):
        """Test TypeScript availability check."""
        with patch('subprocess.run') as mock_run:
            # TypeScript is available
            mock_run.return_value.returncode = 0
            assert compiler.check_typescript_available() is True
            
            # TypeScript is not available
            mock_run.return_value.returncode = 1
            assert compiler.check_typescript_available() is False
    
    def test_create_default_tsconfig(self, compiler):
        """Test creating default tsconfig.json."""
        compiler.source_path.mkdir(parents=True)
        
        compiler.create_default_tsconfig()
        
        tsconfig_path = compiler.source_path / "tsconfig.json"
        assert tsconfig_path.exists()
        
        # Verify config contents
        with open(tsconfig_path) as f:
            config = json.load(f)
        
        assert config["compilerOptions"]["target"] == "es2020"
        assert config["compilerOptions"]["module"] == "commonjs"
        assert config["compilerOptions"]["strict"] is True
    
    def test_compile_typescript(self, compiler):
        """Test TypeScript compilation."""
        compiler.source_path.mkdir(parents=True)
        compiler.output_path.mkdir(parents=True)
        
        # Create TypeScript file
        (compiler.source_path / "handler.ts").write_text("""
            interface Event {
                body: string;
            }
            
            export const handler = async (event: Event) => {
                return {
                    statusCode: 200,
                    body: JSON.stringify({ message: 'Hello' })
                };
            };
        """)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            result = compiler.compile()
            
            assert result is True
            mock_run.assert_called_once()
    
    def test_compile_with_errors(self, compiler):
        """Test compilation with TypeScript errors."""
        compiler.source_path.mkdir(parents=True)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "error TS2322: Type 'string' is not assignable to type 'number'"
            
            result = compiler.compile()
            
            assert result is False
    
    def test_watch_mode(self, compiler):
        """Test TypeScript watch mode."""
        compiler.source_path.mkdir(parents=True)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            compiler.compile(watch=True)
            
            args = mock_run.call_args[0][0]
            assert "--watch" in args or "-w" in args


class TestLambdaBuilderIntegration:
    """Integration tests for Lambda building process."""
    
    def test_build_nodejs_function(self):
        """Test building a complete Node.js function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            func_path = Path(tmpdir) / "function"
            func_path.mkdir()
            
            # Create function files
            (func_path / "index.js").write_text("""
                exports.handler = async (event) => {
                    return {
                        statusCode: 200,
                        body: JSON.stringify({ message: 'Hello from Lambda!' })
                    };
                };
            """)
            
            (func_path / "package.json").write_text(json.dumps({
                "name": "test-function",
                "version": "1.0.0",
                "description": "Test Lambda function",
                "main": "index.js"
            }))
            
            # Build
            output_path = Path(tmpdir) / "dist"
            builder = NodeJSBuilder(func_path, output_path)
            
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                result = builder.build()
            
            assert result is True
            assert output_path.exists()
            assert (output_path / "index.js").exists()
            assert (output_path / "package.json").exists()
            
            # Package
            zip_file = Path(tmpdir) / "function.zip"
            packager = LambdaPackager(output_path, zip_file)
            result = packager.create_package()
            
            assert result is True
            assert zip_file.exists()
            assert zip_file.stat().st_size > 0
    
    def test_build_typescript_function(self):
        """Test building a TypeScript Lambda function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            func_path = Path(tmpdir) / "function"
            func_path.mkdir()
            
            # Create TypeScript function
            (func_path / "handler.ts").write_text("""
                import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
                
                export const handler = async (
                    event: APIGatewayProxyEvent
                ): Promise<APIGatewayProxyResult> => {
                    return {
                        statusCode: 200,
                        body: JSON.stringify({
                            message: 'Hello from TypeScript Lambda!',
                            input: event,
                        }),
                    };
                };
            """)
            
            (func_path / "package.json").write_text(json.dumps({
                "name": "typescript-function",
                "version": "1.0.0",
                "main": "dist/handler.js",
                "scripts": {
                    "build": "tsc"
                },
                "devDependencies": {
                    "@types/aws-lambda": "^8.10.0",
                    "typescript": "^5.0.0"
                }
            }))
            
            (func_path / "tsconfig.json").write_text(json.dumps({
                "compilerOptions": {
                    "target": "es2020",
                    "module": "commonjs",
                    "lib": ["es2020"],
                    "outDir": "./dist",
                    "rootDir": "./",
                    "strict": true,
                    "esModuleInterop": true,
                    "skipLibCheck": true,
                    "forceConsistentCasingInFileNames": true
                },
                "exclude": ["node_modules", "dist"]
            }))
            
            output_path = Path(tmpdir) / "dist"
            builder = NodeJSBuilder(func_path, output_path)
            
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                
                # First detect TypeScript
                with patch.object(builder, 'is_typescript_project', return_value=True):
                    result = builder.build()
            
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=lambda_utils", "--cov-report=term-missing"])