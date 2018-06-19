FROM python:3.6-slim-stretch
RUN apt-get update -y
RUN apt-get install -y sqlite3 libsqlite3-dev

RUN pip install -U pip
RUN pip install pipenv

COPY Pipfile .
COPY Pipfile.lock .
RUN pipenv install --system

COPY ./*.py /app/
WORKDIR /app
CMD ["python3", "karmabot.py"]
