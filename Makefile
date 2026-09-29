.PHONY: setup test lint format sim eval dashboard demo

setup:
	pip install -e ".[dev]"

test:
	pytest tests/

lint:
	ruff check .
	mypy .

format:
	ruff format .

sim:
	python -m eval.simulator.run

eval:
	python -m eval.run_eval

dashboard:
	streamlit run dashboard/app.py

demo:
	streamlit run dashboard/app.py
