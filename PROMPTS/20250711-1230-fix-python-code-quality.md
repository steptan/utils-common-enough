# Fix Python Code Quality Violations - Critical CLAUDE.md Compliance

**Created**: 2025-07-11 12:30
**Priority**: CRITICAL - BLOCKING
**Status**: Pending

## Problem Statement

The utils project has critical Python code quality violations that directly violate CLAUDE.md standards:
- **561 MyPy type errors** across multiple modules
- **Black formatting violations** (line length inconsistencies)
- **Isort import ordering violations** 
- **Flake8 style violations** (unused imports, long lines, etc.)

These violations are **BLOCKING** per CLAUDE.md: "ALL hook issues are BLOCKING - EVERYTHING must be ✅ GREEN!"

## Research → Plan → Implement Workflow

### 1. Research Phase
First, understand the current state and scope of violations:

```bash
cd /Users/sj/projects/analysis/utils

# Get detailed MyPy report
mypy src/ --show-error-codes --show-column-numbers > mypy-report.txt

# Check Black formatting issues
black src/ tests/ --check --diff > black-issues.txt

# Check import ordering
isort src/ tests/ --check --diff > isort-issues.txt

# Get detailed Flake8 report
flake8 src/ tests/ --statistics --show-source > flake8-report.txt
```

### 2. Plan Phase
Create a systematic approach to fix all violations:

1. **Fix MyPy Type Errors (561 errors)**:
   - Add missing type annotations
   - Fix incorrect type usage
   - Add proper return type annotations
   - Resolve Union type issues
   - Fix Optional type handling

2. **Fix Black Formatting**:
   - Standardize line length to 88 characters
   - Fix string quote consistency
   - Correct indentation issues

3. **Fix Isort Import Ordering**:
   - Separate standard library, third-party, and local imports
   - Sort imports alphabetically within sections
   - Remove unused imports

4. **Fix Flake8 Style Issues**:
   - Remove unused variables and imports
   - Fix line length violations
   - Correct naming conventions

### 3. Implementation Commands

Execute these commands in sequence:

```bash
# Step 1: Fix import ordering first (affects other tools)
isort src/ tests/ --profile black

# Step 2: Apply Black formatting
black src/ tests/

# Step 3: Fix MyPy issues systematically by module
# Start with core modules, then work outward
mypy src/config.py --show-error-codes
# Fix issues in config.py, then move to next module

# Step 4: Fix remaining Flake8 issues
flake8 src/ tests/ --show-source

# Step 5: Verify all fixes
python -m pytest tests/ --cov=src --cov-report=html --cov-fail-under=80
mypy src/ tests/
black src/ tests/ --check
isort src/ tests/ --check
flake8 src/ tests/
```

## Validation Steps

After implementation, verify CLAUDE.md compliance:

```bash
# MANDATORY: All these must return exit code 0 (✅ GREEN)
pytest tests/ && echo "✅ Tests pass"
black src/ tests/ --check && echo "✅ Black formatting"
isort src/ tests/ --check && echo "✅ Import ordering"
mypy src/ && echo "✅ Type checking"
flake8 src/ && echo "✅ Style compliance"

# Coverage check (80% minimum per CLAUDE.md)
pytest --cov=src --cov-report=term --cov-fail-under=80
```

## Expected Outcomes

After completion:
- **0 MyPy errors** (down from 561)
- **✅ Black formatting compliance**
- **✅ Isort import ordering compliance**
- **✅ Flake8 style compliance**
- **Maintain 80%+ test coverage**

## Cross-Project Impact

This fix may reveal similar issues in the three main projects. After completing utils fixes:
1. Check fraud-or-not for similar TypeScript violations
2. Check media-register for similar TypeScript violations  
3. Check people-cards for similar TypeScript violations
4. Update shared coding standards documentation

## Critical Note

**DO NOT PROCEED** with any other development tasks until ALL Python code quality issues are resolved and verified. This is a blocking requirement per CLAUDE.md standards.