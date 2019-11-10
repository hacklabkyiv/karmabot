FROM python:3.8-slim-buster
RUN apt update -y
RUN apt-get install -y build-essential libssl-dev libffi-dev python3-dev --no-install-recommends

RUN pip install -U pip
RUN pip install poetry

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

RUN poetry config settings.virtualenvs.create false
RUN poetry install --no-dev --no-interaction --no-ansi

COPY lang/ /app/lang/
RUN pybabel compile -d /app/lang/

COPY karmabot/ /app/karmabot/
COPY config.yml logging.yml app.py /app/

ENTRYPOINT ["python"]
CMD ["app.py"]
