# Test Suite Documentation

This directory contains the automated test suite for the backend application.

## Test Structure

```
tests/
├── unit/              # Unit tests for individual components
│   ├── test_core_logic.py    # Core business logic tests
│   ├── test_serializers.py   # API serializer validation tests
│   └── test_services.py      # Service layer tests (to be added)
├── api/               # API endpoint tests
│   ├── test_auth.py          # Authentication & authorization tests
│   ├── test_posts.py         # Posts API tests (to be added)
│   └── test_products.py      # Products API tests (to be added)
└── conftest.py        # Shared fixtures and test configuration
```

## Testing Approach

### Unit Tests
- **Focus**: Individual components in isolation
- **Scope**: Core business logic, serializers, services
- **Characteristics**:
  - Fast execution
  - No external dependencies
  - Test deterministic behavior only (no LLM calls)
  - Mock external services

### API Tests
- **Focus**: HTTP endpoints and integration
- **Scope**: Authentication, CRUD operations, permissions
- **Characteristics**:
  - Test complete request/response cycles
  - Validate HTTP status codes
  - Test authentication and authorization
  - Verify data transformations

### Out of Scope
- Django ORM internals
- Wagtail CMS internal behavior
- HTML templates and styling
- Third-party SDKs (only mocked)

## Running Tests

### Basic Test Execution
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=backend --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_core_logic.py

# Run specific test class
pytest tests/unit/test_core_logic.py::TestCoreLogic

# Run specific test method
pytest tests/unit/test_core_logic.py::TestCoreLogic::test_merge_related_products_basic
```

### Test Configuration
- **Framework**: pytest with pytest-django
- **Coverage**: Minimum 70% required (configured in pytest.ini)
- **Fixtures**: Shared test data in conftest.py
- **Mocking**: Use `responses` for HTTP mocking, `unittest.mock` for general mocking

## Writing Tests

### Best Practices
1. **Test Naming**: Use descriptive names that explain what is being tested
2. **Test Isolation**: Each test should be independent
3. **Arrange-Act-Assert**: Follow the AAA pattern
4. **Test Data**: Use factories for complex test data
5. **Edge Cases**: Test boundary conditions and error cases
6. **Performance**: Keep tests fast and focused

### Example Test Structure
```python
def test_feature_description():
    # Arrange - Set up test data
    input_data = {...}
    expected_result = {...}

    # Act - Execute the code under test
    result = function_under_test(input_data)

    # Assert - Verify the outcome
    assert result == expected_result
    assert some_condition_is_true
```

## Fixtures Available

- `api_client`: Unauthenticated API client
- `auth_client`: Authenticated API client (regular user)
- `admin_client`: Authenticated API client (admin user)
- `user`: Regular test user
- `admin_user`: Admin test user
- `auth_headers`: Authentication headers
- `admin_auth_headers`: Admin authentication headers
- `user_factory`: Factory for creating test users

## Test Coverage Goals

1. **Unit Tests**: 80%+ coverage of core business logic
2. **API Tests**: 90%+ coverage of all endpoints
3. **Edge Cases**: Comprehensive error condition testing
4. **Integration**: Key workflows and service interactions

## Continuous Integration

Tests are configured to run automatically in CI/CD pipelines with:
- Test execution on every push
- Coverage reporting
- Quality gates (minimum coverage requirements)
- Test result notifications
