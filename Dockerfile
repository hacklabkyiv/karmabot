FROM python:3.10-slim

RUN pip install -U pip
RUN pip install poetry==1.8.4

WORKDIR /app
COPY pyproject.toml poetry.lock poetry.toml /app/
COPY data karmabot lang /app/

RUN poetry install --without dev --no-interaction --no-ansi

CMD ["karmabot"]
