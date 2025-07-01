#!/usr/bin/env python3
"""
Build Lambda functions - Python replacement for scripts/build-lambdas.sh

Builds TypeScript Lambda functions and creates deployment packages.
"""

import sys
import os
import shutil
import zipfile
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lambda_utils.nodejs_builder import NodeJSLambdaBuilder
from lambda_utils.packager import LambdaPackager


def main():
    """Build Lambda functions."""
    parser = argparse.ArgumentParser(
        description="Build Lambda functions for deployment"
    )
    parser.add_argument(
        "--source",
        default="src/lambda",
        help="Source directory for Lambda functions (default: src/lambda)"
    )
    parser.add_argument(
        "--output",
        default="dist/lambda",
        help="Output directory for built functions (default: dist/lambda)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean output directory before building"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Get project root (assume we're in utils/src/scripts)
    project_root = Path(__file__).parent.parent.parent.parent
    source_dir = project_root / args.source
    output_dir = project_root / args.output
    
    if not source_dir.exists():
        print(f"Error: Source directory {source_dir} not found", file=sys.stderr)
        sys.exit(1)
    
    # Clean output directory if requested
    if args.clean and output_dir.exists():
        if args.verbose:
            print(f"Cleaning {output_dir}")
        shutil.rmtree(output_dir)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize builder
    builder = NodeJSLambdaBuilder()
    packager = LambdaPackager()
    
    # Find all TypeScript Lambda functions
    lambda_files = list(source_dir.glob("*.ts"))
    
    if not lambda_files:
        print(f"No TypeScript files found in {source_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Building {len(lambda_files)} Lambda functions...")
    
    success_count = 0
    for lambda_file in lambda_files:
        if lambda_file.name == "tsconfig.json":
            continue
            
        function_name = lambda_file.stem
        print(f"\nBuilding {function_name}...")
        
        try:
            # Build the function
            build_dir = output_dir / function_name
            build_dir.mkdir(exist_ok=True)
            
            # Copy source file
            shutil.copy(lambda_file, build_dir / lambda_file.name)
            
            # Copy package.json and package-lock.json if they exist
            for pkg_file in ["package.json", "package-lock.json"]:
                pkg_path = source_dir / pkg_file
                if pkg_path.exists():
                    shutil.copy(pkg_path, build_dir / pkg_file)
            
            # Build TypeScript
            if args.verbose:
                print(f"  Compiling TypeScript...")
            
            result = builder.build(
                source_dir=str(build_dir),
                output_dir=str(build_dir / "dist"),
                tsconfig_path=str(source_dir / "tsconfig.json") if (source_dir / "tsconfig.json").exists() else None
            )
            
            if not result:
                print(f"  ❌ Failed to build {function_name}")
                continue
            
            # Create deployment package
            if args.verbose:
                print(f"  Creating deployment package...")
            
            zip_path = output_dir / f"{function_name}.zip"
            package_result = packager.create_package(
                source_dir=str(build_dir),
                output_path=str(zip_path),
                include_dev_dependencies=False
            )
            
            if package_result:
                print(f"  ✅ Built {function_name} -> {zip_path}")
                success_count += 1
            else:
                print(f"  ❌ Failed to package {function_name}")
            
            # Clean up build directory
            if not args.verbose:
                shutil.rmtree(build_dir)
                
        except Exception as e:
            print(f"  ❌ Error building {function_name}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
    
    print(f"\n{'='*50}")
    print(f"Build complete: {success_count}/{len(lambda_files)} functions built successfully")
    
    if success_count < len(lambda_files):
        sys.exit(1)


if __name__ == "__main__":
    main()