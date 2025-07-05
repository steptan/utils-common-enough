# Unified Permissions Tests

This directory contains tests for the unified user permissions management system.

## Test Files

### test_unified_permissions.py

Comprehensive unit tests using pytest framework:

- **TestPolicyGenerator**: Tests policy generation logic
- **TestUnifiedPermissionManager**: Tests user management and policy operations
- **TestCLICommands**: Tests CLI command handling
- **TestErrorHandling**: Tests error scenarios

### test_unified_permissions_integration.py

Integration tests that can run without pytest:

- Policy generation validation
- Project detection logic
- Unified policy generation for multiple projects
- Policy size limit warnings

### test_unified_cli.py

CLI functionality tests:

- Help command validation
- Command argument parsing
- Error handling for invalid inputs
- JSON output validation

## Running Tests

### With pytest (if available):

```bash
pytest tests/test_unified_permissions.py -v
```

### Without pytest:

```bash
# Run integration tests
python tests/test_unified_permissions_integration.py

# Run CLI tests
python tests/test_unified_cli.py
```

### Run all tests:

```bash
python tests/test_unified_permissions_integration.py && python tests/test_unified_cli.py
```

## Test Coverage

The tests cover:

1. **Policy Generation**: Validates that all required AWS permissions are included
2. **Project Detection**: Tests automatic project detection from user names
3. **Multi-Project Support**: Verifies unified policies work for multiple projects
4. **CLI Interface**: Tests all CLI commands and options
5. **Error Handling**: Validates graceful handling of errors
6. **Policy Size**: Warns about AWS policy size limits

## Known Issues

- Policy size exceeds AWS managed policy limit (6144 chars) when including all permissions
- This is expected as the unified policy combines multiple project permissions
- In production, consider using managed policies or splitting permissions
