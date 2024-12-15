FROM python:3.8-slim-buster

RUN pip install -U pip
RUN pip install poetry==1.0.5

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-interaction --no-ansi

COPY lang/ /app/lang/

COPY karmabot/ /app/karmabot/
COPY config.yml logging.yml app.py /app/

ENTRYPOINT ["python"]
CMD ["app.py"]
