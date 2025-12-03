.PHONY: help install install-dev clean test lint format data train mlflow

help:
	@echo "Available commands:"
	@echo "  install       Install dependencies"
	@echo "  install-dev   Install with development dependencies"
	@echo "  clean         Clean generated files"
	@echo "  test          Run tests"
	@echo "  lint          Run linting"
	@echo "  format        Format code"
	@echo "  data          Collect and preprocess data"
	@echo "  train         Train model"
	@echo "  mlflow        Start MLflow UI"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/

test:
	pytest tests/ -v --cov=src --cov-report=html

lint:
	ruff check src/ scripts/
	mypy src/

format:
	black src/ scripts/ tests/
	isort src/ scripts/ tests/

data:
	python scripts/collect_data.py
	python scripts/preprocess_data.py

train:
	python scripts/train.py

mlflow:
	mlflow ui --backend-store-uri ./logs/mlruns

dvc-init:
	dvc init
	dvc remote add -d storage ./dvc-storage

dvc-add-data:
	dvc add data/raw/merged_data.parquet
	dvc add data/processed/processed_data.parquet
