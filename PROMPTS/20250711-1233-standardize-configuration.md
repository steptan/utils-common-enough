# Standardize Configuration - Critical CLAUDE.md Compliance

**Created**: 2025-07-11 12:33
**Priority**: CRITICAL - BLOCKING
**Status**: Pending

## Problem Statement

The utils project has configuration inconsistencies that violate CLAUDE.md standards:
- **pyproject.toml line length mismatch** with Black configuration (88 vs other values)
- **Inconsistent tool configurations** across development tools
- **Missing configuration sections** for some tools
- **Configuration drift** from CLAUDE.md requirements

These violations are **BLOCKING** per CLAUDE.md: "Consistency Requirements - Across projects, Keep as consistent as possible"

## Research → Plan → Implement Workflow

### 1. Research Phase
First, audit all configuration files and identify inconsistencies:

```bash
cd /Users/sj/projects/analysis/utils

# Examine current pyproject.toml configuration
cat pyproject.toml

# Check for other configuration files
find . -name "*.toml" -o -name "*.cfg" -o -name "*.ini" -o -name ".flake8" -o -name "setup.cfg"

# Compare with project configuration files
ls -la /Users/sj/projects/analysis/fraud-or-not/{pyproject.toml,package.json,tsconfig.json} 2>/dev/null
ls -la /Users/sj/projects/analysis/media-register/{pyproject.toml,package.json,tsconfig.json} 2>/dev/null  
ls -la /Users/sj/projects/analysis/people-cards/{pyproject.toml,package.json,tsconfig.json} 2>/dev/null

# Check current tool configurations
grep -A 10 -B 2 "line-length\|max-line-length\|line_length" pyproject.toml setup.cfg .flake8 2>/dev/null || true
```

### 2. Plan Phase
Standardize all configuration following CLAUDE.md requirements:

**Configuration Standards to Implement:**

1. **Line Length Standardization**:
   - **Black**: 88 characters (industry standard)
   - **Flake8**: 88 characters (match Black)
   - **MyPy**: 88 characters (match Black)
   - **Isort**: Compatible with Black (88 chars)

2. **Tool Configuration Consistency**:
   - All tools should use consistent settings
   - Follow CLAUDE.md TypeScript standards where applicable to Python
   - Ensure compatibility between all development tools

3. **pyproject.toml Structure**:
   - Complete tool configuration in one file
   - Remove redundant configuration files
   - Follow modern Python packaging standards

4. **Cross-Project Alignment**:
   - Ensure utils configuration serves as template
   - Verify compatibility with TypeScript project configs
   - Maintain consistency with CLAUDE.md requirements

### 3. Implementation Commands

Execute these commands in sequence:

```bash
# Step 1: Backup current configuration
cd /Users/sj/projects/analysis/utils
cp pyproject.toml pyproject.toml.backup
cp setup.cfg setup.cfg.backup 2>/dev/null || true
cp .flake8 .flake8.backup 2>/dev/null || true

# Step 2: Create standardized pyproject.toml
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "utils-common-enough"
version = "1.0.0"
description = "Shared utilities for fraud-or-not, media-register, and people-cards projects"
authors = [
    {name = "Project Team"},
]
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "boto3>=1.26.0",
    "click>=8.0.0",
    "pyyaml>=6.0",
    "requests>=2.28.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.10.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "types-requests>=2.28.0",
    "types-PyYAML>=6.0.0",
]

[project.scripts]
utils-cli = "src.cli.__main__:cli"

[project.urls]
Homepage = "https://github.com/steptan/utils-common-enough"
Repository = "https://github.com/steptan/utils-common-enough"

# Tool Configurations - CLAUDE.md Compliant

[tool.black]
line-length = 88
target-version = ['py39']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
  | venv
)/
'''

[tool.isort]
profile = "black"
line_length = 88
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true
src_paths = ["src", "tests"]

[tool.flake8]
max-line-length = 88
extend-ignore = [
    "E203",  # whitespace before ':'
    "E501",  # line too long (handled by black)
    "W503",  # line break before binary operator
]
exclude = [
    ".git",
    "__pycache__",
    "build",
    "dist",
    ".venv",
    "venv",
    ".eggs",
    "*.egg",
]
per-file-ignores = [
    "__init__.py:F401",  # Allow unused imports in __init__.py
]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
show_error_codes = true
show_column_numbers = true
line_length = 88

[[tool.mypy.overrides]]
module = [
    "boto3.*",
    "botocore.*",
]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/test_*",
    "*/__pycache__/*",
    "*/venv/*",
    "*/site-packages/*",
]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
ignore_errors = true
show_missing = true
precision = 2

[tool.coverage.html]
directory = "htmlcov"
EOF

# Step 3: Remove redundant configuration files
rm -f setup.cfg .flake8 setup.py 2>/dev/null || true

# Step 4: Update requirements.txt to match pyproject.toml
cat > requirements.txt << 'EOF'
# Production dependencies - keep in sync with pyproject.toml
boto3>=1.26.0
click>=8.0.0
pyyaml>=6.0
requests>=2.28.0
python-dotenv>=1.0.0

# Development dependencies
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
black>=23.0.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.0.0
types-requests>=2.28.0
types-PyYAML>=6.0.0
EOF

# Step 5: Create .editorconfig for cross-platform consistency
cat > .editorconfig << 'EOF'
# EditorConfig is awesome: https://EditorConfig.org

# top-most EditorConfig file
root = true

# All files
[*]
indent_style = space
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
charset = utf-8

# Python files
[*.py]
indent_size = 4
max_line_length = 88

# YAML files
[*.{yml,yaml}]
indent_size = 2

# JSON files
[*.json]
indent_size = 2

# Markdown files
[*.md]
trim_trailing_whitespace = false

# Makefile
[Makefile]
indent_style = tab
EOF
```

### 4. Cross-Project Configuration Alignment

Ensure consistency across all projects:

```bash
# Step 6: Check TypeScript project configurations for alignment
cd /Users/sj/projects/analysis

# Compare line length settings across projects
echo "=== fraud-or-not configuration ==="
grep -r "printWidth\|max.*length\|lineLength" fraud-or-not/ 2>/dev/null || echo "No config found"

echo "=== media-register configuration ==="  
grep -r "printWidth\|max.*length\|lineLength" media-register/ 2>/dev/null || echo "No config found"

echo "=== people-cards configuration ==="
grep -r "printWidth\|max.*length\|lineLength" people-cards/ 2>/dev/null || echo "No config found"

# Create configuration template for TypeScript projects
mkdir -p utils/templates/typescript
cat > utils/templates/typescript/.eslintrc.js << 'EOF'
module.exports = {
  // ESLint configuration aligned with utils/pyproject.toml standards
  rules: {
    "max-len": ["error", { "code": 88, "tabWidth": 2 }],
    // Other rules...
  }
};
EOF

cat > utils/templates/typescript/.prettierrc << 'EOF'
{
  "printWidth": 88,
  "tabWidth": 2,
  "useTabs": false,
  "semi": true,
  "singleQuote": true,
  "trailingComma": "es5"
}
EOF
```

## Validation Steps

After implementation, verify CLAUDE.md compliance:

```bash
# Verify all tools use consistent configuration
cd /Users/sj/projects/analysis/utils

# Test Black configuration
black --check --config pyproject.toml src/ tests/

# Test Isort configuration  
isort --check --settings-path pyproject.toml src/ tests/

# Test Flake8 configuration
flake8 --config pyproject.toml src/ tests/

# Test MyPy configuration
mypy --config-file pyproject.toml src/

# Test Pytest configuration
pytest --no-cov --collect-only

# Verify line length consistency
grep -n "88" pyproject.toml | wc -l  # Should show multiple matches

# Check for configuration conflicts
python -c "
import configparser
import tomllib

# Verify no conflicting configurations exist
try:
    with open('pyproject.toml', 'rb') as f:
        config = tomllib.load(f)
    
    black_line_length = config['tool']['black']['line-length']
    mypy_line_length = config['tool']['mypy']['line_length']
    
    assert black_line_length == mypy_line_length == 88, 'Line length mismatch'
    print('✅ Configuration consistency verified')
except Exception as e:
    print(f'❌ Configuration error: {e}')
"
```

## Expected Outcomes

After completion:
- **Consistent 88-character line length** across all tools
- **Single pyproject.toml file** with all tool configurations
- **No redundant configuration files** (setup.cfg, .flake8 removed)
- **Cross-platform consistency** with .editorconfig
- **Template configurations** for TypeScript projects
- **Aligned requirements.txt** with pyproject.toml dependencies

## Cross-Project Impact

This standardization should be applied across all projects:
1. **fraud-or-not**: Update ESLint/Prettier to use 88-character line length
2. **media-register**: Update ESLint/Prettier to use 88-character line length
3. **people-cards**: Update ESLint/Prettier to use 88-character line length
4. **Create shared configuration templates** in utils for easy replication

## Critical Note

Configuration consistency is **MANDATORY** per CLAUDE.md. All projects must use the same line length and compatible tool settings to maintain code quality and prevent formatting conflicts during development.