install:
	poetry install

test:
	poetry run pytest -vv tests/

lint:
	ruff check .
	ruff format .

all: install lint test
