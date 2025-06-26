.PHONY: help install test test-cov lint format clean build run-tests docker-test

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install development dependencies
	uv sync --dev

test:  ## Run tests
	uv run pytest -v

test-cov:  ## Run tests with coverage
	uv run pytest --cov=bdapt --cov-report=html --cov-report=term

lint:  ## Run type checking
	uv run mypy bdapt

format:  ## Format code
	uv run black .
	uv run isort .

format-check:  ## Check code formatting
	uv run black --check .
	uv run isort --check-only .

clean:  ## Clean build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

build:  ## Build the package
	uv build

run-tests:  ## Run tests in Docker container
	./run_tests.sh

docker-test:  ## Run tests in Docker (same as run-tests)
	./run_tests.sh

dev-install:  ## Install in development mode
	uv pip install -e .

# Development aliases
bdapt-dev:  ## Run bdapt in development mode
	uv run python -m bdapt

demo:  ## Show demo commands (requires sudo)
	@echo "Demo commands (run with sudo):"
	@echo "  sudo uv run bdapt new web-stack nginx postgresql redis -d 'Web services'"
	@echo "  sudo uv run bdapt ls"
	@echo "  sudo uv run bdapt show web-stack"
	@echo "  sudo uv run bdapt add web-stack php-fpm"
	@echo "  sudo uv run bdapt rm web-stack redis"
	@echo "  sudo uv run bdapt del web-stack" 