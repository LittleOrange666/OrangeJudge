FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y

RUN apt-get install -y sudo python3 python3-pip redis

RUN apt-get install -y gosu

COPY testlib /app/testlib

COPY langs /app/langs

COPY static /app/static

COPY templates /app/templates

COPY modules /app/modules

COPY judge /app/judge

COPY main.py tools/requirements.txt tools/entrypoint.sh /app/

RUN useradd orangejudge -u 1500 -m

RUN chown -R orangejudge:orangejudge /app

USER orangejudge

RUN pip3 install -r requirements.txt

CMD python3 main.py