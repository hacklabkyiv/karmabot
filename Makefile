install:
	poetry install

test:
	poetry run pytest -vv tests/

lint:
	ruff check .
	ruff format .

types:
	mypy .

all: install lint types test
