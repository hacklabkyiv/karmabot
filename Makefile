install:
	poetry install
	poetry shell

test:
	poetry run pytest -vv tests/

lint:
	ruff check .
	ruff format .

types:
	mypy .

build:
	poetry build

all: install lint types test
