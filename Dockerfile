FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y

RUN apt-get install -y sudo python3 python3-pip redis

COPY testlib /app/testlib

COPY langs /app/langs

COPY static /app/static

COPY templates /app/templates

COPY modules /app/modules

COPY judge /app/judge

COPY main.py tools/requirements.txt /app/

RUN pip3 install -r requirements.txt

CMD python3 main.py