.PHONY: check format run dashboard build

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check
	uv run python -m pytest -q

format:
	uv run ruff check --fix .
	uv run ruff format .

run:
	uv run python -m onespread

dashboard:
	uv run python -m onespread.dashboard

build:
	uv run python scripts/build_dashboard.py
