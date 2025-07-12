# Fix Test Coverage Violations - Critical CLAUDE.md Compliance

**Created**: 2025-07-11 12:31
**Priority**: CRITICAL - BLOCKING
**Status**: Pending

## Problem Statement

The utils project has critical test coverage violations that directly violate CLAUDE.md standards:
- **Current coverage: 3%** (Target: 80% minimum per CLAUDE.md)
- **35 failing tests** across the test suite
- **Missing test files** for many modules
- **Inadequate test patterns** not following CLAUDE.md standards

These violations are **BLOCKING** per CLAUDE.md: "Test Coverage Requirements - MINIMUM coverage thresholds - NO EXCEPTIONS: Statements: 80%, Branches: 80%, Functions: 80%, Lines: 80%"

## Research → Plan → Implement Workflow

### 1. Research Phase
First, understand the current test state and coverage gaps:

```bash
cd /Users/sj/projects/analysis/utils

# Get detailed coverage report
pytest --cov=src --cov-report=html --cov-report=term-missing --cov-report=json

# Identify failing tests
pytest -v --tb=short > test-failures.txt

# List all Python modules that need tests
find src/ -name "*.py" -type f | grep -v __pycache__ | sort > modules-list.txt

# Check which modules lack test coverage
grep -f modules-list.txt tests/ -R || echo "Missing test files identified"
```

### 2. Plan Phase
Create a systematic approach to achieve 80% coverage:

1. **Fix Existing Failing Tests (35 failures)**:
   - Analyze test failure reasons
   - Fix import issues
   - Mock external dependencies properly
   - Update test data and fixtures

2. **Create Missing Test Files**:
   - Follow CLAUDE.md test structure standards
   - Use proper Arrange/Act/Assert pattern
   - Test both success and error cases

3. **Modules Requiring New Tests** (based on current gaps):
   - `src/config.py`
   - `src/cli/` modules (cloudformation, database, deploy, etc.)
   - `src/cloudformation/` modules
   - `src/deployment/` modules  
   - `src/lambda_utils/` modules
   - `src/security/` modules
   - `src/cost/` modules

4. **Test Coverage Strategy**:
   - Unit tests for individual functions
   - Integration tests for module interactions
   - Mock AWS services and external dependencies
   - Test error conditions and edge cases

### 3. Implementation Commands

Execute these commands in sequence:

```bash
# Step 1: Fix existing failing tests
pytest tests/ -v --tb=long --no-cov

# Step 2: Create test files for uncovered modules
# Follow CLAUDE.md test structure:
cat > tests/test_template.py << 'EOF'
"""
✅ CLAUDE.md Compliant Test Structure Template
"""
import pytest
from unittest.mock import Mock, patch

from src.module_name import ClassOrFunction


class TestClassName:
    """Test class following CLAUDE.md standards."""
    
    def test_method_should_handle_valid_input_correctly(self):
        """Test valid input case."""
        # Arrange
        input_data = {"key": "value"}
        expected = {"processed": True}
        
        # Act
        result = ClassOrFunction(input_data)
        
        # Assert
        assert result == expected
    
    def test_method_should_handle_error_cases(self):
        """Test error scenarios explicitly."""
        # Arrange
        invalid_input = None
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            ClassOrFunction(invalid_input)
        
        assert "Input cannot be None" in str(exc_info.value)
    
    @patch('src.module_name.external_dependency')
    def test_method_with_mocked_dependencies(self, mock_dependency):
        """Test with properly mocked external dependencies."""
        # Arrange
        mock_dependency.return_value = {"mocked": "response"}
        
        # Act
        result = ClassOrFunction()
        
        # Assert
        mock_dependency.assert_called_once()
        assert result["mocked"] == "response"
EOF

# Step 3: Create comprehensive test suite
# For each major module, create corresponding test file
python -c "
import os
modules = [
    'config', 'cli/cloudformation', 'cli/database', 'cli/deploy',
    'cloudformation/stack_manager', 'deployment/base_deployer',
    'lambda_utils/packager', 'security/audit', 'cost/analyzer'
]
for module in modules:
    test_file = f'tests/test_{module.replace(\"/\", \"_\")}.py'
    if not os.path.exists(test_file):
        print(f'Creating {test_file}')
        # Create test file based on template
"

# Step 4: Run tests incrementally and fix issues
pytest tests/ --cov=src --cov-report=term --cov-fail-under=80

# Step 5: Add integration tests
mkdir -p tests/integration
# Create integration test files for end-to-end workflows
```

### 4. Test File Creation Strategy

For each major module, create tests covering:

```python
# ✅ ALWAYS: Test structure per CLAUDE.md
def test_function_name_should_describe_expected_behavior():
    """Clear test description."""
    # Arrange - Set up test data
    # Act - Execute the function
    # Assert - Verify results

# ✅ ALWAYS: Test error cases
def test_function_name_should_handle_invalid_input():
    """Test error handling."""
    with pytest.raises(ExpectedError):
        function_call_with_invalid_input()

# ✅ ALWAYS: Mock external dependencies
@patch('module.external_service')
def test_function_with_external_dependencies(mock_service):
    """Test with mocked external calls."""
    mock_service.return_value = test_data
    # Test logic here
```

## Validation Steps

After implementation, verify CLAUDE.md compliance:

```bash
# MANDATORY: Must achieve 80% minimum coverage
pytest --cov=src --cov-report=html --cov-report=term --cov-fail-under=80

# Verify no failing tests
pytest tests/ -v

# Check coverage details
coverage report --show-missing --fail-under=80

# Verify test quality (no skipped/disabled tests)
grep -r "skip\|xit\|it\.skip" tests/ && echo "❌ Found disabled tests" || echo "✅ No disabled tests"
```

## Expected Outcomes

After completion:
- **80%+ test coverage** (up from 3%)
- **0 failing tests** (down from 35)
- **Complete test suite** for all major modules
- **CLAUDE.md compliant test structure** throughout
- **Proper error case testing**
- **Mocked external dependencies**

## Cross-Project Impact

This improvement should be replicated across all projects:
1. **fraud-or-not**: Verify TypeScript test coverage meets 80%
2. **media-register**: Verify TypeScript test coverage meets 80%
3. **people-cards**: Verify TypeScript test coverage meets 80%
4. **Standardize test patterns** across all projects

## Critical Note

**NO EXCEPTIONS** to the 80% coverage requirement per CLAUDE.md. This is not a suggestion but a mandatory standard that must be achieved before any other development work continues.