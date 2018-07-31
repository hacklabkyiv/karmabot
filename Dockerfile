FROM python:3.6-slim-stretch
RUN apt-get update -y
RUN apt-get install -y sqlite3 libsqlite3-dev

RUN pip install -U pip
RUN pip install pipenv

COPY . /app/
WORKDIR /app

RUN pipenv install --system --deploy

ENTRYPOINT ["python"]
CMD ["app.py"]
