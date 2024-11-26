FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y

RUN apt-get install sudo -y
RUN apt-get install python3 -y
RUN apt-get install python3-pip -y
RUN apt-get install redis -y

RUN useradd orangejudge -u 1500

COPY main.py /app

COPY tools/requirements.txt /app

COPY testlib /app

COPY langs /app

COPY judge /app

COPY static /app

COPY templates /app

COPY modules /app

RUN chown -R orangejudge:orangejudge /app

USER orangejudge

RUN pip3 install -r requirements.txt

CMD python3 main.py