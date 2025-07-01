#!/usr/bin/env python3
"""Lambda management CLI commands."""

import click
import sys
from pathlib import Path
import json
import subprocess

from lambda_utils.builder import LambdaBuilder
from lambda_utils.nodejs_builder import NodeJSBuilder
from lambda_utils.typescript_compiler import TypeScriptCompiler
from lambda_utils.packager import LambdaPackager
from config import get_project_config


@click.group()
def main():
    """Lambda function management commands."""
    pass


@main.command()
@click.option('--function', '-f', required=True, help='Lambda function directory')
@click.option('--output', '-o', help='Output directory for built artifacts')
@click.option('--runtime', '-r', help='Lambda runtime (auto-detected if not specified)')
@click.option('--install-deps/--no-install-deps', default=True, help='Install dependencies')
@click.option('--minify/--no-minify', default=False, help='Minify code')
@click.option('--source-map/--no-source-map', default=True, help='Generate source maps')
def build(function, output, runtime, install_deps, minify, source_map):
    """Build Lambda function for deployment."""
    try:
        function_path = Path(function).resolve()
        
        if not function_path.exists():
            click.echo(f"Error: Function directory not found: {function}", err=True)
            sys.exit(1)
        
        click.echo(f"🔨 Building Lambda function: {function_path.name}")
        
        # Detect runtime if not specified
        if not runtime:
            if (function_path / "package.json").exists():
                runtime = "nodejs"
            elif (function_path / "requirements.txt").exists():
                runtime = "python"
            else:
                click.echo("Error: Could not detect runtime. Please specify with --runtime", err=True)
                sys.exit(1)
        
        # Build based on runtime
        if runtime.startswith("nodejs"):
            builder = NodeJSBuilder()
            result_path = builder.build(
                function_path,
                output_dir=Path(output) if output else None,
                install_dependencies=install_deps,
                minify=minify,
                source_maps=source_map
            )
        elif runtime.startswith("python"):
            builder = LambdaBuilder()
            result_path = builder.build_lambda(
                function_path,
                Path(output) if output else function_path / "dist"
            )
        else:
            click.echo(f"Error: Unsupported runtime: {runtime}", err=True)
            sys.exit(1)
        
        click.echo(f"✅ Build complete: {result_path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--function', '-f', required=True, help='Lambda function directory')
@click.option('--output', '-o', help='Output path for zip file')
@click.option('--exclude', '-e', multiple=True, help='Patterns to exclude')
def package(function, output, exclude):
    """Package Lambda function into deployment zip."""
    try:
        function_path = Path(function).resolve()
        
        if not function_path.exists():
            click.echo(f"Error: Function directory not found: {function}", err=True)
            sys.exit(1)
        
        click.echo(f"📦 Packaging Lambda function: {function_path.name}")
        
        packager = LambdaPackager()
        
        # Determine output path
        if output:
            output_path = Path(output)
        else:
            output_path = function_path.parent / f"{function_path.name}.zip"
        
        # Package
        result = packager.create_deployment_package(
            function_path,
            output_path,
            exclude_patterns=list(exclude)
        )
        
        click.echo(f"✅ Package created: {result}")
        
        # Show package info
        info = packager.get_package_info(result)
        click.echo(f"   Size: {info['size_mb']:.2f} MB")
        click.echo(f"   Files: {info['file_count']}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--function', '-f', required=True, help='Lambda function directory')
@click.option('--watch/--no-watch', default=False, help='Watch for changes')
def compile(function, watch):
    """Compile TypeScript Lambda functions."""
    try:
        function_path = Path(function).resolve()
        
        if not function_path.exists():
            click.echo(f"Error: Function directory not found: {function}", err=True)
            sys.exit(1)
        
        click.echo(f"🔄 Compiling TypeScript: {function_path.name}")
        
        compiler = TypeScriptCompiler()
        
        if watch:
            # Watch mode
            click.echo("👀 Watching for changes... (Press Ctrl+C to stop)")
            compiler.watch(function_path)
        else:
            # Single compilation
            result = compiler.compile(function_path)
            click.echo(f"✅ Compilation complete: {result}")
        
    except KeyboardInterrupt:
        click.echo("\n⏹️  Watch mode stopped")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--output', '-o', help='Output directory')
@click.option('--parallel/--sequential', default=True, help='Build in parallel')
def build_all(project, output, parallel):
    """Build all Lambda functions in the project."""
    try:
        project_root = Path.cwd()
        lambda_dir = project_root / "src" / "lambda"
        
        if not lambda_dir.exists():
            click.echo(f"Error: Lambda directory not found: {lambda_dir}", err=True)
            sys.exit(1)
        
        # Find all Lambda functions
        functions = []
        for item in lambda_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                if (item / "package.json").exists() or (item / "index.ts").exists() or (item / "index.js").exists():
                    functions.append(item)
        
        if not functions:
            click.echo("No Lambda functions found")
            return
        
        click.echo(f"🚀 Building {len(functions)} Lambda functions")
        
        # Build each function
        builder = NodeJSBuilder()
        failed = []
        
        for func in functions:
            try:
                click.echo(f"\n📦 Building {func.name}...")
                output_dir = Path(output) / func.name if output else None
                result = builder.build(func, output_dir=output_dir)
                click.echo(f"✅ {func.name} built successfully")
            except Exception as e:
                click.echo(f"❌ {func.name} failed: {e}", err=True)
                failed.append(func.name)
        
        # Summary
        click.echo(f"\n{'='*50}")
        click.echo(f"Built: {len(functions) - len(failed)}/{len(functions)}")
        
        if failed:
            click.echo(f"\nFailed functions:")
            for name in failed:
                click.echo(f"  - {name}")
            sys.exit(1)
        else:
            click.echo("\n✅ All functions built successfully!")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--function', '-f', required=True, help='Lambda function directory')
@click.option('--event', '-e', help='Event JSON file or inline JSON')
@click.option('--env-file', help='Environment variables file')
@click.option('--timeout', '-t', default=3, help='Timeout in seconds')
def local_test(function, event, env_file, timeout):
    """Test Lambda function locally."""
    try:
        function_path = Path(function).resolve()
        
        if not function_path.exists():
            click.echo(f"Error: Function directory not found: {function}", err=True)
            sys.exit(1)
        
        click.echo(f"🧪 Testing Lambda function: {function_path.name}")
        
        # Load event
        event_data = {}
        if event:
            if event.startswith('{'):
                # Inline JSON
                event_data = json.loads(event)
            else:
                # File path
                with open(event, 'r') as f:
                    event_data = json.load(f)
        
        # Set up environment
        env = {}
        if env_file:
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env[key] = value
        
        # Find the handler file
        handler_file = None
        for name in ['index.js', 'handler.js', 'index.py', 'handler.py']:
            if (function_path / name).exists():
                handler_file = name
                break
        
        if not handler_file:
            click.echo("Error: No handler file found", err=True)
            sys.exit(1)
        
        # Test based on runtime
        if handler_file.endswith('.js'):
            # Node.js test
            test_script = f"""
const handler = require('./{handler_file}');
const event = {json.dumps(event_data)};
const context = {{
    functionName: '{function_path.name}',
    requestId: 'test-request-id',
    invokedFunctionArn: 'arn:aws:lambda:us-west-1:123456789012:function:{function_path.name}'
}};

handler.handler(event, context, (err, result) => {{
    if (err) {{
        console.error('ERROR:', err);
        process.exit(1);
    }} else {{
        console.log('RESULT:', JSON.stringify(result, null, 2));
    }}
}});
"""
            
            # Write test script
            test_file = function_path / '_test_runner.js'
            test_file.write_text(test_script)
            
            try:
                # Run test
                result = subprocess.run(
                    ['node', str(test_file)],
                    cwd=function_path,
                    env={**env, 'NODE_ENV': 'test'},
                    timeout=timeout,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    click.echo("\n✅ Test passed!")
                    click.echo(result.stdout)
                else:
                    click.echo("\n❌ Test failed!", err=True)
                    click.echo(result.stderr, err=True)
                    sys.exit(1)
                    
            finally:
                test_file.unlink()
                
        else:
            click.echo("Python Lambda testing not yet implemented", err=True)
            sys.exit(1)
        
    except subprocess.TimeoutExpired:
        click.echo(f"Error: Function exceeded timeout of {timeout} seconds", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--runtime', '-r', default='nodejs18.x', help='Lambda runtime version')
@click.option('--memory', '-m', default=512, help='Memory in MB')
@click.option('--timeout', '-t', default=30, help='Timeout in seconds')
def validate_config(project, runtime, memory, timeout):
    """Validate Lambda configuration."""
    try:
        issues = []
        
        # Validate runtime
        valid_runtimes = [
            'nodejs18.x', 'nodejs16.x', 'nodejs14.x',
            'python3.11', 'python3.10', 'python3.9',
            'java17', 'java11', 'dotnet6', 'go1.x'
        ]
        
        if runtime not in valid_runtimes:
            issues.append(f"Invalid runtime: {runtime}")
            click.echo(f"Valid runtimes: {', '.join(valid_runtimes)}")
        
        # Validate memory
        if memory < 128 or memory > 10240:
            issues.append(f"Memory must be between 128 and 10240 MB (got {memory})")
        elif memory % 64 != 0:
            issues.append(f"Memory must be a multiple of 64 MB (got {memory})")
        
        # Validate timeout
        if timeout < 1 or timeout > 900:
            issues.append(f"Timeout must be between 1 and 900 seconds (got {timeout})")
        
        # Check Lambda functions
        lambda_dir = Path.cwd() / "src" / "lambda"
        if lambda_dir.exists():
            for func_dir in lambda_dir.iterdir():
                if func_dir.is_dir():
                    # Check for handler
                    has_handler = any(
                        (func_dir / name).exists() 
                        for name in ['index.js', 'handler.js', 'index.ts', 'handler.ts']
                    )
                    if not has_handler:
                        issues.append(f"No handler found in {func_dir.name}")
                    
                    # Check package.json for Node.js
                    if runtime.startswith('nodejs'):
                        pkg_file = func_dir / 'package.json'
                        if pkg_file.exists():
                            with open(pkg_file) as f:
                                pkg = json.load(f)
                                if 'aws-sdk' in pkg.get('dependencies', {}):
                                    issues.append(f"{func_dir.name}: aws-sdk should be in devDependencies")
        
        # Report results
        if issues:
            click.echo("❌ Validation failed:")
            for issue in issues:
                click.echo(f"  - {issue}")
            sys.exit(1)
        else:
            click.echo("✅ Lambda configuration is valid")
            click.echo(f"  Runtime: {runtime}")
            click.echo(f"  Memory: {memory} MB")
            click.echo(f"  Timeout: {timeout} seconds")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()