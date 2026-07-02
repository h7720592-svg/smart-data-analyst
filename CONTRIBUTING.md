# Contributing to Smart Data Analyst

Thanks for your interest in contributing! 🎉

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/smart-data-analyst.git`
3. Create a virtual environment: `python -m venv venv && source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Create a branch: `git checkout -b feature/your-feature`

## Development

### Running the app

```bash
streamlit run app.py
```

### Running tests

```bash
pytest tests/ -v
```

### Code style

This project uses [Ruff](https://github.com/astral-sh/ruff) for linting:

```bash
ruff check src/ pages/ tests/
ruff format src/ pages/ tests/
```

## Project Structure

See [README.md](README.md) for the full project structure.

## Adding Features

- **New chart types**: Add to `src/viz/chart_registry.py` and update prompts in `src/llm/prompts.py`
- **New LLM providers**: Add to `PROVIDER_CONFIGS` in `src/llm/client.py`
- **New export formats**: Add to `src/export/`

## Pull Request Guidelines

1. Keep PRs focused on a single feature or fix
2. Add tests for new functionality
3. Update the README if needed
4. Ensure CI passes before requesting review

## Questions?

Open an issue on GitHub!
