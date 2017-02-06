ARG PYTHON_VERSION=2.7
FROM python:${PYTHON_VERSION}-alpine

RUN pip install --no-cache-dir mongoengine pytest pytest-cov

ARG CELERY_VERSION=3.1.25
RUN pip install --no-cache-dir celery==${CELERY_VERSION}

COPY . /opt/celerybeat-mongo/

WORKDIR /opt/celerybeat-mongo/

RUN pip install .

USER 1000:1000
