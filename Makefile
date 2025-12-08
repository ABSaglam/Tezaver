.PHONY: help install install-dev test coverage lint format clean pipeline-full pipeline-fast ui check

help:
	@echo "Tezaver-Mac Makefile Komutları"
	@echo "==============================="
	@echo "make install       - Bağımlılıkları yükle"
	@echo "make install-dev   - Development bağımlılıklarını yükle"
	@echo "make test          - Testleri çalıştır"
	@echo "make coverage      - Test coverage raporu"
	@echo "make lint          - Code linting (flake8)"
	@echo "make format        - Code formatting (black)"
	@echo "make check         - Lint + Test (CI öncesi kontrol)"
	@echo "make clean         - Geçici dosyaları temizle"
	@echo "make pipeline-full - Full pipeline çalıştır"
	@echo "make pipeline-fast - Fast pipeline çalıştır"
	@echo "make ui            - Streamlit UI başlat"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

test:
	PYTHONPATH=src python -m pytest tests -v

coverage:
	PYTHONPATH=src python -m pytest tests --cov=src/tezaver --cov-report=html --cov-report=term
	@echo "\n📊 Coverage raporu: htmlcov/index.html"

lint:
	@echo "🔍 Running flake8..."
	flake8 src tests --max-line-length=120 --extend-ignore=E203,W503

format:
	@echo "✨ Formatting code with black..."
	black src tests --line-length=120

check: lint test
	@echo "\n✅ Code quality checks passed!"

clean:
	@echo "🧹 Cleaning temporary files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage .mypy_cache
	@echo "✨ Clean complete!"

pipeline-full:
	@echo "🚀 Running full pipeline..."
	PYTHONPATH=src python src/tezaver/run_pipeline.py --mode full

pipeline-fast:
	@echo "⚡ Running fast pipeline..."
	PYTHONPATH=src python src/tezaver/run_pipeline.py --mode fast

ui:
	@echo "🎨 Starting Streamlit UI..."
	PYTHONPATH=src streamlit run src/tezaver/ui/main_panel.py
