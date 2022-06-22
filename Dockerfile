FROM python:3.6.5-stretch

MAINTAINER Sebastian Bassi

RUN pip install allofplos

RUN python -m allofplos.update
