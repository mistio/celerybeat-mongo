#!/bin/bash

set -eu

PYTHON_VERSION=2.7
CELERY_VERSION=3.1.25
USAGE="$0 [-h] [-p PYTHON_VERSION] [-c CELERY_VERSION]

Run tests.

Options:
    -h                  Display this help message and exit.
    -p PYTHON_VERSION   Python version to test. Defaults to $PYTHON_VERSION.
    -c CELERY_VERSION   Celery version to test. Defaults to $CELERY_VERSION.
"

while getopts "hp:c:" opt; do
    case "$opt" in
        h)
            echo "$USAGE"
            exit
            ;;
        p)
            PYTHON_VERSION=$OPTARG
            ;;
        c)
            CELERY_VERSION=$OPTARG
            ;;
        \?)
            echo "$USAGE"
            echo
            echo "ERROR: Invalid option: -$OPTARG" >&2
            exit 1
    esac
done

set -x

docker-compose down -v
docker build -t celerybeat-mongo \
    --build-arg PYTHON_VERSION=$PYTHON_VERSION \
    --build-arg CELERY_VERSION=$CELERY_VERSION \
    .
docker-compose up -d
docker-compose run test \
    py.test -v --cov-report term-missing --cov=celerybeatmongo tests/test.py
docker-compose down -v
