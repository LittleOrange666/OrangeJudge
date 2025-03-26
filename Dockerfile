FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

COPY tools/requirements.txt /app/

COPY testlib /app/testlib
COPY main.py /app/
COPY templates /app/templates
COPY static /app/static
COPY modules /app/modules

RUN apt-get update &&\
    apt-get -y install sudo python3 python3-pip redis --fix-missing &&\
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip3 install -r requirements.txt

CMD python3 main.py