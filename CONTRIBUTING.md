# Contributing to Impressox Agent

## Contribution Process

1. Fork repository
2. Create new branch for feature/fix
3. Commit changes
4. Push to fork
5. Create Pull Request

## Development

### Environment Setup

1. Clone repository:
```bash
git clone https://github.com/your-username/impressox-agent
cd impressox-agent
```

2. Install dependencies:
```bash
# App core
cd app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Web client
cd ../clients/web
npm install

# Smart contracts
cd ../contracts
npm install
```

3. Setup environment:
```bash
cp .env.example .env
# Update necessary environment variables
```

### Coding Standards

#### Python
- Follow PEP 8
- Docstrings for classes and functions
- Type hints
- Unit tests for new logic
- Maximum line length: 100 characters

#### TypeScript/JavaScript
- ESLint configuration
- Prettier formatting
- JSDoc comments
- Unit tests with Jest
- Maximum line length: 100 characters

#### Solidity
- Solidity style guide
- NatSpec documentation
- Unit tests for contracts
- Gas optimization
- Security best practices

### Testing

```bash
# App core tests
cd app
pytest

# Web client tests
cd clients/web
npm test

# Contract tests
cd contracts
npx hardhat test
```

## Pull Request Process

1. Ensure PR focuses on a single feature/fix
2. Update documentation if needed
3. Add tests for new code
4. Ensure all tests pass
5. Code review from at least 1 maintainer

## Commit Messages

Format:
```
type(scope): subject

body (optional)

footer (optional)
```

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes
- refactor: Code refactoring
- test: Add/update tests
- chore: Maintenance tasks

Example:
```
feat(web-client): add real-time chat interface

- Implement WebSocket connection
- Add message components
- Handle reconnection logic

Closes #123
```

## Branch Naming

Format: `type/description`

Examples:
- `feat/realtime-chat`
- `fix/memory-leak`
- `docs/api-guide`

## Issue Reporting

1. Use issue templates
2. Provide steps to reproduce
3. Expected vs actual behavior
4. Screenshots/logs if applicable
5. Environment details

## Code Review

### Reviewer Guide
- Check coding standards
- Verify tests
- Review documentation
- Security considerations
- Performance impact

### Author Guide
- Respond to feedback
- Update code as needed
- Keep PR scope focused
- Be receptive to suggestions

## Development Workflow

1. **Planning**
   - Issue discussion
   - Technical approach
   - Task breakdown

2. **Development**
   - Local development
   - Testing
   - Documentation

3. **Review**
   - Code review
   - Updates based on feedback
   - Final approval

4. **Deployment**
   - Merge to main
   - Deploy changes
   - Monitor results

## Release Process

1. Version bump
2. Changelog update
3. Tag release
4. Deploy to staging
5. Testing
6. Deploy to production

## Support

- GitHub Issues
- Discord channel
- Documentation
- Community forums
