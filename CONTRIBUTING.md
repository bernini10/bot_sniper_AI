# 🤝 Contributing to bot_sniper_AI

Thank you for considering contributing to bot_sniper_AI! We welcome contributions from everyone.

## 🎯 Code of Conduct
Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## 🚀 Getting Started

### 📋 Prerequisites
- Python 3.8+
- Git
- Basic understanding of algorithmic trading

### 🔧 Development Setup
1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/bot_sniper_AI.git
   cd bot_sniper_AI
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements_dev.txt  # Development dependencies
   ```
5. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```

## 🎯 How to Contribute

### 🐛 Reporting Bugs
1. Check if the bug already exists in [Issues](https://github.com/bernini10/bot_sniper_AI/issues)
2. Use the bug report template
3. Include detailed steps to reproduce
4. Include logs, screenshots, and environment details

### 💡 Suggesting Features
1. Check if the feature already exists in [Issues](https://github.com/bernini10/bot_sniper_AI/issues)
2. Use the feature request template
3. Explain the problem and your proposed solution
4. Consider if you can implement it yourself

### 🔬 Pull Requests
1. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes following our coding standards
3. Add or update tests as needed
4. Update documentation
5. Run tests:
   ```bash
   pytest
   ```
6. Commit with descriptive messages:
   ```bash
   git commit -m "feat: add new feature"
   ```
7. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
8. Create a Pull Request using our template

## 📝 Coding Standards

### 🐍 Python Style
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where appropriate
- Document functions with docstrings
- Keep functions focused and small

### 🏗️ Architecture
- Follow Protocolo Severino methodology
- Maintain separation of concerns
- Write testable code
- Keep dependencies minimal

### 📚 Documentation
- Update README.md for user-facing changes
- Add docstrings for new functions/classes
- Update comments when modifying code
- Keep architecture diagrams current

## 🧪 Testing

### 🔍 Test Types
- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows

### 🏃 Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_brain_integration.py

# Run with coverage
pytest --cov=.

# Run with verbose output
pytest -v
```

## 🏷️ Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: repair bug in scanner
docs: update README
style: format code
refactor: restructure module
test: add integration tests
chore: update dependencies
```

## 🔄 Workflow

1. **Find an issue** or create one
2. **Discuss** the approach in the issue
3. **Implement** your changes
4. **Test** thoroughly
5. **Document** your changes
6. **Submit PR** for review
7. **Address feedback** from maintainers
8. **Merge** when approved

## 🎯 Good First Issues

Look for issues tagged with `good-first-issue`:
- Documentation improvements
- Test additions
- Small bug fixes
- Code cleanup

## ❓ Need Help?

- Check existing documentation
- Search existing issues
- Ask in GitHub Discussions
- Email: bernini10@gmail.com

## 🙏 Thank You!

Your contributions help make bot_sniper_AI better for everyone!
