FROM python:3.7-slim-stretch
RUN apt update -y
RUN apt-get install -y sqlite3 libsqlite3-dev --no-install-recommends
RUN apt-get install -y build-essential libssl-dev libffi-dev python3-dev --no-install-recommends

RUN pip install -U pip
RUN pip install pipenv

COPY Pipfile Pipfile.lock /tmp/dependencies/

ENV PIPENV_PIPFILE /tmp/dependencies/Pipfile
RUN pipenv install --system --deploy

COPY karmabot/ /app/karmabot/
COPY app.py /app/
WORKDIR /app

ENTRYPOINT ["python"]
CMD ["app.py"]
