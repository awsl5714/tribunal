.PHONY: install test lint typecheck demo all

install:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check src tests

typecheck:
	mypy src

demo:
	python examples/demo.py

all: lint typecheck test
