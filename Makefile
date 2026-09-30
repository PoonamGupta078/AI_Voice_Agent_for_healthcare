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
	python -m eval.simulator.run --provider mock

eval:
	python -m eval.run_eval --provider mock

eval-real-subset:
	python -m eval.run_eval --provider google --patients 1 --days 1 --seed 42

dashboard:
	streamlit run dashboard/app.py

demo:
	streamlit run dashboard/app.py
