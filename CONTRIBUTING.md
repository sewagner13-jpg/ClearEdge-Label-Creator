# Contributing to CLEAR EDGE Label Pipeline

## Development Setup

1. Clone the repository
2. Create a virtual environment: `python3.11 -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dev dependencies: `pip install -r requirements.txt`
5. Install pre-commit hooks (if available): `pre-commit install`

## Code Standards

### Python Style
- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use docstrings for all modules, classes, and public functions

### Imports
- Standard library first
- Third-party packages second
- Local imports last
- Use absolute imports

### Testing
- Write tests for all new features
- Maintain >80% code coverage
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Write code and tests
3. Run tests: `pytest`
4. Update documentation if needed
5. Commit with clear messages
6. Push and create PR
7. Ensure CI passes
8. Request review

## Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `chore`: Maintenance

Example: `feat: add DOT pictogram overlap detection`

## Testing Guidelines

### Unit Tests
- Test individual functions/methods
- Mock external dependencies
- Fast execution (< 1s each)

### Integration Tests
- Test component interactions
- Use test fixtures
- Can be slower but < 10s each

### Running Tests
```bash
# All tests
pytest

# Specific file
pytest tests/test_schema.py

# With coverage
pytest --cov=app

# Verbose
pytest -v
```

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No secrets in code
- [ ] Error handling implemented
- [ ] Logging appropriate
- [ ] Performance considered

## Questions?

Open an issue or contact the maintainers.
